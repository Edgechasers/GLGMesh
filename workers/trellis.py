import os,sys,time,json,gc
from pathlib import Path
from common import *
job,settings,image_path=context();tmp=stage_dir(job,'trellis');repo=RUNTIME/'repos/trellis'
os.environ.update(SPARSE_ATTN_BACKEND='sdpa',SPARSE_CONV_BACKEND='none')
sys.path.insert(0,str(repo/'TRELLIS.2'));sys.path.append(str(repo/'stubs'));sys.path.insert(0,str(repo))
import torch,numpy as np,trimesh
from PIL import Image
from phase3_mps import enable
enable()
from trellis2 import models
from trellis_bounded_conv import install
install()
from trellis2.pipelines.trellis2_image_to_3d import Trellis2ImageTo3DPipeline
from trellis2.pipelines import samplers
from trellis2.modules.image_feature_extractor import DinoV3FeatureExtractor
start=time.perf_counter();out=tmp
cfg=json.loads((RUNTIME/'weights/trellis/pipeline.json').read_text())['args']
# Keep only the components for the supported 512-resolution pipeline.
cfg['models']={k:v for k,v in cfg['models'].items() if '1024' not in k and '1536' not in k}
for key,value in cfg['models'].items():
 if 'ss_dec' in value:cfg['models'][key]=str(RUNTIME/'weights/trellis-ss/ckpts/ss_dec_conv3d_16l8_fp16')
 else:cfg['models'][key]=str(RUNTIME/'weights/trellis'/value)
event('Loading TRELLIS.2 local 512 pipeline',.01)
for p in (RUNTIME/'weights/trellis/ckpts').glob('*.json'):
 d=json.loads(p.read_text())
 if d['args'].get('dtype')=='bfloat16':d['args']['dtype']='float16';p.write_text(json.dumps(d))
class LazyModel:
 def __init__(self,path):object.__setattr__(self,'path',path);object.__setattr__(self,'model',None);object.__setattr__(self,'pending',{})
 def load(self):
  if self.model is None:
   event('Loading '+Path(self.path).name)
   print('LOAD_STAGE',self.path,time.perf_counter()-start,flush=True)
   m=models.from_pretrained(self.path).eval().requires_grad_(False)
   for k,v in self.pending.items():setattr(m,k,v)
   object.__setattr__(self,'model',m)
  return self.model
 def __getattr__(self,k):return getattr(self.load(),k)
 def __setattr__(self,k,v):
  if k in ['path','model','pending']:object.__setattr__(self,k,v)
  else:
   self.pending[k]=v
   if self.model is not None:setattr(self.model,k,v)
 def eval(self):return self
 def to(self,*args,**kwargs):self.load().to(*args,**kwargs);return self
 def cpu(self):
  print('UNLOAD_STAGE',self.path,time.perf_counter()-start,flush=True);object.__setattr__(self,'model',None);gc.collect();torch.mps.empty_cache();return self
 def __getitem__(self,index):
  if index!=0:raise IndexError(index)
  return self
 def __call__(self,*args,**kwargs):return self.load()(*args,**kwargs)
model_map={k:LazyModel(v if v.startswith('/') else str(RUNTIME/'weights/trellis'/v)) for k,v in cfg['models'].items()}
args={'models':model_map,'image_cond_model':DinoV3FeatureExtractor(str(RUNTIME/'weights/dino-l')),'rembg_model':None,'low_vram':True,'default_pipeline_type':'512','shape_slat_normalization':cfg['shape_slat_normalization'],'tex_slat_normalization':cfg['tex_slat_normalization']}
for name in ['sparse_structure','shape_slat','tex_slat']:
 c=cfg[name+'_sampler'];args[name+'_sampler']=getattr(samplers,c['name'])(**c['args']);args[name+'_sampler_params']=c['params']
pipe=Trellis2ImageTo3DPipeline(**args);pipe.to(torch.device('mps'))
image=Image.open(image_path).convert('RGBA')
if image.getchannel('A').getextrema()[0]<255:image=pipe.preprocess_image(image)
else:image=image.convert('RGB').resize((512,512),Image.Resampling.LANCZOS)
image.save(out/'input.png')
# Wrap the sampler's real step function: no time-based percentage simulation.
for ordinal,name in enumerate(['sparse_structure','shape_slat','tex_slat']):
 sampler=args[name+'_sampler'];original_step=sampler.sample_once
 def install_progress(sampler,original_step,ordinal,name):
  counter=[0]
  def wrapped(*a,**kw):
   result=original_step(*a,**kw);counter[0]+=1
   event(name.replace('_',' ')+' sampling',.06+.65*(ordinal+min(counter[0]/12,1))/3,counter[0],12)
   return result
  sampler.sample_once=wrapped
 install_progress(sampler,original_step,ordinal,name)
from trellis2.modules.sparse import SparseTensor
def checkpoint(method,name):
 def wrapped(*a,**kw):
  path=tmp/('trellis-'+name+'.pt')
  if path.exists():
   saved=torch.load(path,weights_only=False);torch.set_rng_state(saved['cpu_rng']);torch.mps.set_rng_state(saved['mps_rng'])
   print('RESUME',name,flush=True)
   return SparseTensor(saved['feats'].to('mps'),saved['coords'].to('mps')) if 'feats' in saved else saved['tensor'].to('mps')
  value=method(*a,**kw)
  saved={'cpu_rng':torch.get_rng_state(),'mps_rng':torch.mps.get_rng_state()}
  if isinstance(value,SparseTensor):saved.update(feats=value.feats.cpu(),coords=value.coords.cpu())
  else:saved['tensor']=value.cpu()
  atomic_torch_save(torch,saved,path);print('CHECKPOINT',name,flush=True);return value
 return wrapped
for name in ['sample_sparse_structure','sample_shape_slat','sample_tex_slat']:
 setattr(pipe,name,checkpoint(getattr(pipe,name),name))
print('PIPELINE_READY',time.perf_counter()-start,flush=True)
with torch.no_grad():result=pipe.run(image,seed=settings['seed'],pipeline_type='512',preprocess_image=False)
m=result[0];verts=m.vertices.cpu().numpy();faces=m.faces.cpu().numpy()
assert np.isfinite(verts).all() and len(faces)>0
trimesh.Trimesh(vertices=verts,faces=faces,process=False).export(out/'raw-geometry.glb')
np.savez_compressed(tmp/'trellis-output.npz',vertices=verts,faces=faces,attrs=m.attrs.cpu().numpy(),coords=m.coords.cpu().numpy(),origin=m.origin.cpu().numpy(),voxel_size=m.voxel_size)
print('MESH_READY',len(verts),len(faces),time.perf_counter()-start,flush=True)
from backends.texture_baker import uv_unwrap,bake_texture,export_glb_with_texture
bv,bf=verts,faces
event('Reducing raw geometry to the configured target',.80)
from budget import reduce_geometry
bv,bf=reduce_geometry(verts,faces,out/'reduction.json',target=settings['triangles'])
event('Unwrapping and baking texture locally',.88)
v,f,uv,vmapping=uv_unwrap(bv,bf)
color,mr,mask=bake_texture(v,f,uv,m.coords.cpu().float().numpy(),m.attrs.cpu().float().numpy(),m.origin.cpu().float().numpy(),m.voxel_size,texture_size=1024)
color=np.flipud(color).copy();mr=np.flipud(mr).copy() # Match glTF bottom-origin UVs to top-origin texture pixels.
# Convert native Z-up positions to the GLB Y-up convention after baking.
v=np.stack([v[:,0],v[:,2],-v[:,1]],axis=-1)
export_glb_with_texture(v,f,uv,color,mr,str(job/'model.glb'));Image.fromarray(color).save(out/'basecolor.png')
metrics={'generation_seconds':time.perf_counter()-start,'backend':'PyTorch 2.5.1 MPS; pure PyTorch sparse convolutions; CPU mesh extraction and KDTree texture bake','export_orientation':'native Z-up to glTF Y-up: rotation X -90 degrees','pipeline_resolution':512,'texture_resolution':1024,'seed':settings['seed'],'steps_per_stage':12,'raw_triangles':len(faces),'export_triangles':len(f),'compatibility':'Stage-by-stage loading/unloading; BF16 flow torso converted to FP16 for macOS 14.3; equivalent real RoPE; query-chunked attention; supplied RGBA; Apple-port decode mesh cleanup bypasses retained.'}
(out/'runtime.json').write_text(json.dumps(metrics,indent=2));print(metrics,flush=True)

event('TRELLIS.2 mesh and texture saved',1)
