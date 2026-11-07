"""Optional Hunyuan3D-Paint-v2-0 RGB stage, entirely local MLX inference.

Uses the pinned upstream RGB workflow, six 384px views, 20 UniPC steps and
2048px atlas. Evaluates VAE views individually and releases models before bake.
Geometry and triangle order are retained; only UV seam vertices are split.
"""
from common import *
import gc,time
import numpy as np
import mlx.core as mx
import trimesh,xatlas
from texture_mesh import prepare_mesh,export_mesh
from PIL import Image
sys.path.insert(0,str(RUNTIME/'repos/hunyuan/python/paint'))
from hy3dpaint_mlx.vae import AutoencoderKL
from hy3dpaint_mlx.unet2p5d import UNet2p5DConditionModel
from hy3dpaint_mlx.scheduler import UniPCScheduler
from hy3dpaint_mlx.mesh_render import MeshRender
from hy3dpaint_mlx.convert import load_torch_weights

job,cfg,image=context();out=stage_dir(job,'paint');t0=time.monotonic()
R=384;STEPS=20;TEX=2048;SF=.18215
AZIMS=[0,90,180,270,0,180];ELEVS=[0,0,0,0,90,-90]
W=RUNTIME/'weights/hunyuan-paint/hunyuan3d-paint-v2-0'
mx.set_cache_limit(256*1024**2);mx.set_memory_limit(11*1024**3)
source=job/('source-mesh.glb' if cfg.get('texture_only') else 'untextured.glb')
event('Unwrapping existing mesh; geometry is preserved',.02)
d=prepare_mesh(source);V,F,uvs=d['vertices'],d['faces'],d['uv']
rend=MeshRender();rend.load_mesh(V,F);rend.set_uv(uvs,F)
ctrl=[rend.render_control(e,a,R) for e,a in zip(ELEVS,AZIMS)]
Image.fromarray((np.concatenate([c[0] for c in ctrl],1)*255).astype(np.uint8)).save(out/'normals.png')
ref=Image.open(image).convert('RGBA').resize((R,R),Image.Resampling.LANCZOS)
bg=Image.new('RGB',ref.size,'white');bg.paste(ref,mask=ref.getchannel('A'));ref=np.asarray(bg,np.float32)/255

def finite(value,label):
 if not bool(mx.all(mx.isfinite(value)).item()):raise RuntimeError('Non-finite '+label)

def load_vae():
 model=AutoencoderKL.from_config(json.loads((W/'vae/config.json').read_text()))
 load_torch_weights(model,mx.load(str(W/'vae/diffusion_pytorch_model.safetensors')),renames=[('.to_out.0.','.to_out.')])
 return model

event('Loading MLX RGB Paint and encoding reference',.08)
vae=load_vae()
def encode(imgs):
 result=[]
 for img in imgs:
  value=vae.encode_mean(mx.array(img[None])*2-1)*SF;mx.eval(value);finite(value,'encoded image');result.append(value)
 return mx.concatenate(result,axis=0)
nlat=encode([c[0] for c in ctrl])[None];plat=encode([c[1] for c in ctrl])[None];rlat=encode([ref])[None]
mx.eval(nlat,plat,rlat);del vae;gc.collect();mx.clear_cache()
unet=UNet2p5DConditionModel(json.loads((W/'unet/config.json').read_text()))
load_torch_weights(unet,mx.load(str(W/'unet/diffusion_pytorch_model.safetensors')),renames=[('transformer_blocks.0.transformer.','transformer_blocks.0.')])
cam_gen=mx.array(np.arange(6,dtype=np.int32)[None]);cam_ref=mx.array([[0]],dtype=mx.int32)
gen_text=unet.unet.learned_text_clip_gen;neg_text=mx.zeros_like(gen_text);zero_ref=mx.zeros_like(rlat)
ced=unet.compute_condition_embed(rlat);mx.eval(ced)
sched=UniPCScheduler();sched.set_timesteps(STEPS);mx.random.seed(cfg['seed'])
latents=mx.random.normal((1,6,R//8,R//8,4))*sched.init_noise_sigma()
for i,t in enumerate(sched.timesteps):
 ti=int(t)
 vc=unet(latents,ti,gen_text,nlat,plat,rlat,cam_gen,cam_ref,mva_scale=1.,ref_scale=1.,condition_embed_dict=ced);mx.eval(vc)
 vu=unet(latents,ti,neg_text,nlat,plat,zero_ref,cam_gen,cam_ref,mva_scale=1.,ref_scale=0.,condition_embed_dict=None);mx.eval(vu)
 latents=sched.step(vu+2*(vc-vu),ti,latents);mx.eval(latents);finite(latents,'paint sample')
 event('Generating six RGB views',.15+.65*(i+1)/STEPS,i+1,STEPS)
del unet,ced,vc,vu,gen_text,neg_text,nlat,plat,rlat,zero_ref,sched;gc.collect();mx.clear_cache()
vae=load_vae();views=[]
for k in range(6):
 value=vae.decode(latents[0,k:k+1]/SF);mx.eval(value);finite(value,'decoded view')
 views.append(np.clip((np.asarray(value[0])+1)/2,0,1))
del vae,latents,value;gc.collect();mx.clear_cache()
Image.fromarray((np.concatenate(views,1)*255).astype(np.uint8)).save(out/'views.png')
event('Baking RGB views to a 2K UV atlas',.85)
texture,covered=rend.bake(views,ELEVS,AZIMS,texture_size=TEX,weights=[1.,.1,.5,.1,.05,.05])
if not covered.any():raise RuntimeError('No texture coverage')
texture=rend.inpaint(texture,covered)
if not np.isfinite(texture).all():raise RuntimeError('Non-finite texture')
export_mesh(job,d,texture,'Hunyuan_RGB')
metrics={'model':'hunyuan3d-paint-v2-0','backend':'MLX','view_resolution':R,'views':6,'steps':STEPS,'scheduler':'UniPC','texture_size':TEX,'super_resolution':False,'seed':cfg['seed'],'seconds':time.monotonic()-t0,'mlx_peak_gib':mx.get_peak_memory()/1024**3,'triangles':len(F),'geometry_preserved':True,'atlas_covered_fraction_before_fill':float(covered.mean()),'material':'RGB base color, constant roughness 0.85 and metallic 0; no generated PBR maps'}
(out/'metrics.json').write_text(json.dumps(metrics,indent=2));event('RGB textured mesh ready',1)
