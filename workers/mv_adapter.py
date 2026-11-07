from common import *
from texture_mesh import prepare_mesh
import time
from PIL import Image
import numpy as np
import torch,types,gc
from diffusers import DDPMScheduler
repo=RUNTIME/'repos/mv-adapter';sys.path.insert(0,str(repo))
# Import upstream cameras without importing the CUDA-only rendering/baking modules.
pkg=types.ModuleType('mvadapter.utils.mesh_utils');pkg.__path__=[str(repo/'mvadapter/utils/mesh_utils')];sys.modules[pkg.__name__]=pkg
from mvadapter.pipelines.pipeline_mvadapter_i2mv_sd import MVAdapterI2MVSDPipeline
from mvadapter.models.attention_processor import DecoupledMVRowColSelfAttnProcessor2_0
from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler
from mvadapter.utils.mesh_utils.camera import get_orthogonal_camera
from hy3dpaint_mlx.raster import cr_raster
from hy3dpaint_mlx.mesh_render import mean_vertex_normals,MeshRender
job,cfg,image=context();R=512;STEPS=40;out=stage_dir(job,'mv');start=time.monotonic()
event('Preparing UVs and six geometry-guided views',.01)
source=job/('source-mesh.glb' if cfg.get('texture_only') else 'untextured.glb')
d=prepare_mesh(source);np.savez_compressed(out/'prepared.npz',**d)
v=d['vertices'];v=np.stack([v[:,0],-v[:,2],v[:,1]],1);center=(v.min(0)+v.max(0))/2;scale=1/(v.max(0)-v.min(0)).max();v=(v-center)*scale;f=d['faces']
cams=get_orthogonal_camera(elevation_deg=[0,0,0,0,89.99,-89.99],distance=[1.8]*6,left=-.55,right=.55,bottom=-.55,top=.55,azimuth_deg=[-90,0,90,180,90,90],device='cpu')
norm=mean_vertex_normals(len(v),f,MeshRender._face_normals(v,f));controls=[];masks=[]
for i,mvp in enumerate(cams.mvp_mtx.numpy()):
    clip=np.c_[v,np.ones(len(v))]@mvp.T;fi,ba=cr_raster.rasterize_backend(clip.astype(np.float32),f,R,backend='auto');mask=fi>0
    pos=cr_raster.interpolate(v.astype(np.float32),fi,ba,f);n=cr_raster.interpolate(norm,fi,ba,f)
    n=n/np.clip(np.linalg.norm(n,axis=-1,keepdims=True),1e-8,None);n[~mask]=0
    c=np.concatenate([np.clip(pos+.5,0,1),np.clip(n*.5+.5,0,1)],axis=-1);controls.append(c);masks.append(mask)
    Image.fromarray(np.uint8(c[:,:,:3]*255)).save(out/f'position-{i}.png');Image.fromarray(np.uint8(c[:,:,3:]*255)).save(out/f'normal-{i}.png')
np.savez_compressed(out/'cameras.npz',mvp=cams.mvp_mtx.numpy(),vertices=v,faces=f,center=center,scale=scale)
# Query chunking bounds attention allocation without changing attention weights.
import torch.nn.functional as F
sdpa=F.scaled_dot_product_attention
def bounded(q,k,v,*args,**kw):
    if q.shape[-2]>128 and not args and kw.get('attn_mask') is None:
        return torch.cat([sdpa(q[...,s:s+128,:],k,v,**kw) for s in range(0,q.shape[-2],128)],dim=-2)
    return sdpa(q,k,v,*args,**kw)
F.scaled_dot_product_attention=bounded
torch.set_num_threads(4);torch.mps.set_per_process_memory_fraction(.85)
pipe=MVAdapterI2MVSDPipeline.from_pretrained(RUNTIME/'weights/sd21',torch_dtype=torch.float16,safety_checker=None,requires_safety_checker=False,local_files_only=True)
pipe.scheduler=ShiftSNRScheduler.from_scheduler(pipe.scheduler,shift_mode='interpolated',shift_scale=8.,scheduler_class=DDPMScheduler)
pipe.init_custom_adapter(num_views=6,self_attn_processor=DecoupledMVRowColSelfAttnProcessor2_0)
pipe.load_custom_adapter(str(RUNTIME/'weights/mv-adapter'),weight_name='mvadapter_ig2mv_sd21.safetensors')
pipe.to(device='mps',dtype=torch.float16);pipe.cond_encoder.to(device='mps',dtype=torch.float16);pipe.enable_vae_slicing();pipe.enable_vae_tiling()
ref=Image.open(image).convert('RGBA');bbox=ref.getchannel('A').getbbox();ref=ref.crop(bbox);ref.thumbnail((int(R*.9),int(R*.9)),Image.Resampling.LANCZOS);bg=Image.new('RGB',(R,R),(128,128,128));bg.paste(ref,((R-ref.width)//2,(R-ref.height)//2),ref.getchannel('A'))
ctrl=torch.tensor(np.stack(controls)).permute(0,3,1,2).to('mps',dtype=torch.float16)
def progress(pipe,i,t,kwargs):event('Generating six MV-Adapter views',.1+.85*(i+1)/STEPS,i+1,STEPS);return kwargs
with torch.no_grad():
    views=pipe('high quality',height=R,width=R,num_inference_steps=STEPS,guidance_scale=3.,num_images_per_prompt=6,control_image=ctrl,control_conditioning_scale=1.,reference_image=bg,reference_conditioning_scale=1.,negative_prompt='watermark, ugly, deformed, noisy, blurry, low contrast',generator=torch.Generator(device='cpu').manual_seed(cfg['seed']),callback_on_step_end=progress).images
for i,im in enumerate(views):im.save(out/f'view-{i}.png')
Image.fromarray(np.concatenate([np.asarray(im) for im in views],1)).save(out/'views.png')
(out/'generation.json').write_text(json.dumps(dict(method='MV-Adapter SD2.1 image + geometry',steps=STEPS,resolution=R,seed=cfg['seed'],seconds=time.monotonic()-start,port='Upstream neural model on MPS; Metal control rasterization; query-chunked attention; common calibrated bake replaces CUDA postprocessing'),indent=2))
event('Native MV-Adapter views saved',1)
