import os,sys,time,json,gc
from pathlib import Path
from common import *
job,settings,image_path=context();tmp=stage_dir(job,'idol');out=tmp;repo=RUNTIME/'repos/idol'
sys.path.insert(0,str(repo))
import torch,numpy as np
from PIL import Image
from safetensors.torch import load_file
from tensordict import TensorDict
from phase3_mps import enable
enable()
from idol.conditioning import ImageEncoder
from idol.preprocess import preprocess_image
from idol.models import LatentSeqMMFlowModel,GaussianFixedlenDecoder,OctreeProbabilityFixedlenDecoder
from idol.models.layers import RePo3DRotaryEmbedding
from idol.sampler import sample_flow
from idol.camera import decode_camera
cfg=json.loads((RUNTIME/'weights/idol/config.json').read_text());start=time.perf_counter();device='mps'
cond_file=tmp/'idol-condition.pt';sample_file=tmp/'idol-sample.pt'
steps=settings.get('idol_steps',50)
from idol_checkpoint import check_schedule
check_schedule(tmp,steps)
sampled_driver_peak=0
last_step_time=None
def clear():gc.collect();torch.mps.empty_cache()
def checkpoint(step,sample):
 global sampled_driver_peak,last_step_time
 torch.mps.synchronize()
 if not all(torch.isfinite(v).all().item() for v in sample.values()):
  raise RuntimeError(f'Nonfinite IDOL sample at step {step}; stopping before saving a corrupt checkpoint')
 now=time.perf_counter();driver=torch.mps.driver_allocated_memory()/1024**3
 sampled_driver_peak=max(sampled_driver_peak,driver)
 progress={'step':step,'steps':steps,'elapsed_seconds':now-start,'step_seconds':None if last_step_time is None else now-last_step_time,'mps_current_allocated_gib':torch.mps.current_allocated_memory()/1024**3,'mps_driver_allocated_gib':driver}
 (out/'progress.json').write_text(json.dumps(progress,indent=2))
 event('Sampling IDOL splat',.1+.78*step/steps,step,steps)
 if step%5==0:
  target=tmp/'idol-progress.pt';pending=tmp/'idol-progress.tmp'
  torch.save({'step':step,'sample':sample.cpu(non_blocking=False)},pending);pending.replace(target)
 last_step_time=now

def load(cls,name):
 print('LOAD',name,time.perf_counter()-start,flush=True)
 model=cls(**cfg[name]['args']);model.load_state_dict(load_file(str(RUNTIME/'weights/idol'/f'{name}.safetensors')),strict=True)
 for mod in model.modules():
  if isinstance(mod,RePo3DRotaryEmbedding):mod.real_valued=True
 return model.eval().requires_grad_(False).to(device)
with torch.no_grad():
 if not cond_file.exists():
  event('Loading DINOv3 and FLUX VAE locally',.01)
  enc=ImageEncoder(str(RUNTIME/'weights/dino-h'),str(RUNTIME/'weights/flux'),dinov3_dtype='fp32',device=device)
  image=preprocess_image(Image.open(image_path),None,image_size=1024,crop_margin=1.2);image.save(out/'input.png')
  pixels=torch.from_numpy(np.array(image)).permute(2,0,1).float().div(255)[None].to(device)
  torch.manual_seed(settings['seed'])
  print('ENCODING',time.perf_counter()-start,flush=True)
  cond=enc(pixels)
  # TensorDict defaults to asynchronous leaf copies. Torch 2.5 does not include
  # MPS in its generic device synchronizer, so serialization can race the copy.
  cond_cpu=cond.cpu(non_blocking=False)
  if not all(torch.isfinite(v).all().item() and v.abs().max().item()>0 for v in cond_cpu.values()):
   raise RuntimeError('Invalid IDOL image conditioning; refusing to start sampling')
  atomic_torch_save(torch,{'condition':cond_cpu,'mps_rng':torch.mps.get_rng_state(),'cpu_rng':torch.get_rng_state()},cond_file)
  del cond_cpu
  del enc,pixels,cond;clear();print('ENCODED',time.perf_counter()-start,flush=True)
 cache=torch.load(cond_file,weights_only=False)
 if not all(torch.isfinite(v).all().item() and v.abs().max().item()>0 for v in cache['condition'].values()):
  raise RuntimeError('Invalid cached IDOL image conditioning; start a fresh job')
 cond=cache['condition'].to(device,non_blocking=False)
 if not sample_file.exists():
  model=load(LatentSeqMMFlowModel,'denoiser');torch.set_rng_state(cache['cpu_rng']);torch.mps.set_rng_state(cache['mps_rng'])
  noise=TensorDict({'latent':torch.randn(1,model.q_token_length,model.in_channels,device=device),'camera':torch.randn(1,1,model.cam_channels,device=device)},batch_size=1,device=device)
  resume_step=0
  if (tmp/'idol-progress.pt').exists():
   progress=torch.load(tmp/'idol-progress.pt',weights_only=False)
   if not all(torch.isfinite(v).all().item() for v in progress['sample'].values()):
    raise RuntimeError('Invalid IDOL sampling checkpoint; start a fresh job')
   noise=progress['sample'].to(device,non_blocking=False);resume_step=progress['step'];del progress
  print('SAMPLING',time.perf_counter()-start,'resume_step',resume_step,flush=True)
  sample=sample_flow(model,noise,cond,cond.apply(torch.zeros_like),steps=steps,rescale_t=3,cfg_strength=3,verbose=True,batch_cfg=False,step_callback=checkpoint,start_step=resume_step)
  assert all(torch.isfinite(v).all() for v in sample.values()),'Nonfinite diffusion sample'
  atomic_torch_save(torch,sample.cpu(non_blocking=False),sample_file);del model,sample,noise;clear()
 del cond,cache;clear();sample=torch.load(sample_file,weights_only=False).to(device,non_blocking=False)
 decoder=load(OctreeProbabilityFixedlenDecoder,'decoder');event('Decoding spatial anchors',.90)
 anchors=OctreeProbabilityFixedlenDecoder.sample(decoder,sample['latent'],num_points=262144//cfg['decoder_gs']['args']['representation_config']['num_gaussians'],level=cfg['max_voxel_level'])
 del decoder;clear()
 decoder=load(GaussianFixedlenDecoder,'decoder_gs');event('Decoding Gaussians',.94)
 gaussian=decoder.to_representation(anchors,decoder(anchors,sample['latent']))[0]
 gaussian.save_ply(str(out/'splat.ply'))
 data={k:getattr(gaussian,k).cpu().numpy() for k in ['xyz','features_dc','scaling','rotation','opacity']}
 assert all(np.isfinite(x).all() for x in data.values()),'Nonfinite Gaussian parameters'
 np.savez_compressed(out/'gaussians.npz',**data);camera=decode_camera(sample['camera'][0,0]);(out/'camera.json').write_text(json.dumps(camera,indent=2))
 metrics={'generation_seconds':time.perf_counter()-start,'backend':'PyTorch 2.5.1 MPS, staged encoder/denoiser/decoder loading','seed':settings['seed'],'steps':steps,'cfg_strength':3,'num_gaussians':len(data['xyz']),'sampled_driver_allocated_gib_max':sampled_driver_peak,'memory_note':'Driver allocations sampled after each denoising step; not a continuous peak measurement.','output_type':'3D Gaussian splat, not mesh','compatibility':'FP32 DINO and FLUX VAE because macOS 14.3 lacks BF16 MPS; FP16 model blocks retained; exact real RoPE; query-chunked attention; no compilation; supplied alpha mask.'}
 (out/'runtime.json').write_text(json.dumps(metrics,indent=2));print(metrics,flush=True)

event('Splat saved',1)
