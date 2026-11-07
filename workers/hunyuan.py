import common
from common import *
import gc
import mlx.core as mx
import numpy as np
sys.path.insert(0,str(RUNTIME/'repos/hunyuan/python/shape'))
import hy3dmlx.pipeline as pipeline
job,cfg,image=context();out=stage_dir(job,'hunyuan');name='hunyuan-mini' if cfg['mode']=='fast' else 'hunyuan-21'
weights=RUNTIME/'weights'/name
folder=next(weights.glob('hunyuan3d-*'))
converted=folder/'model.fp16.safetensors'
if not converted.exists():
 event('Converting the Hunyuan 2.1 checkpoint for MLX (one time)')
 import torch
 from safetensors.torch import save_file
 raw=torch.load(folder/'model.fp16.ckpt',map_location='cpu',weights_only=True,mmap=True)
 tensors={}
 if 'state_dict' in raw:raw=raw['state_dict']
 for k,v in raw.items():
  if isinstance(v,dict):
   for key,value in v.items():
    if torch.is_tensor(value):tensors[k+'.'+key]=(value.half() if value.is_floating_point() else value).contiguous()
  elif torch.is_tensor(v):tensors[k]=(v.half() if v.is_floating_point() else v).contiguous()
 pending=converted.with_suffix('.pending');save_file(tensors,str(pending));pending.replace(converted)
 del raw,tensors
 for temporary in ['v','value']:globals().pop(temporary,None)
 gc.collect()
mx.set_cache_limit(256*1024**2);mx.set_memory_limit(10*1024**3)
original=pipeline.denoise
def denoise(*a,**kw):
 kw['progress']=lambda i,n:event('Sampling shape',.10+.65*i/n,i,n)
 result=original(*a,**kw);event('Decoding geometry and extracting surface',.76);return result
pipeline.denoise=denoise
event('Loading local '+name+' weights',.01)
pipe=pipeline.Hunyuan3DShapePipeline.from_pretrained(str(folder),dtype=mx.float16,quantize=8)
gc.collect();mx.clear_cache();event('Encoding input image',.07)
mesh=pipe.generate(str(image),num_inference_steps=30 if name=='hunyuan-mini' else 50,guidance_scale=5,octree_resolution=256,seed=cfg['seed'],octree_decode=True,num_chunks=4096)
assert len(mesh.faces)>0 and np.isfinite(mesh.vertices).all()
mesh.export(out/'raw.glb')
(out/'metrics.json').write_text(json.dumps({'triangles':len(mesh.faces),'mlx_peak_gib':mx.get_peak_memory()/1024**3,'seed':cfg['seed'],'steps':30 if name=='hunyuan-mini' else 50},indent=2))
event('Shape generated',1)
