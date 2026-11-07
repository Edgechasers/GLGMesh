import os,sys,time,json,gc,hashlib,math,importlib.metadata
from pathlib import Path
from common import *
import bootstrap
import mlx.core as mx
import numpy as np
from PIL import Image
import trimesh
from mlx_vlm.models.hi3d.config import ModelConfig
from mlx_vlm.models.hi3d.vision import Conditioner,prepare_image
from mlx_vlm.models.hi3d.transformer import Hi3DTransformer
from mlx_vlm.models.hi3d.decoder import VAE
from mlx_vlm.models.hi3d.sparse import Grid
from mlx_vlm.models.hi3d.pipeline import sample,decode
from mlx_vlm.models.hi3d.voxelize import adaptive_voxelize
from mlx_vlm.models.hi3d.mesh import decoded_mesh,fill_holes,grid_matrix,postprocess,write_obj
job,settings,image_path=context();tmp=stage_dir(job,'hi3d');weights=RUNTIME/'weights/hi3d';name='mesh';out=tmp
mx.set_memory_limit(10*1024**3);mx.set_cache_limit(256*1024**2)
config=ModelConfig.load(weights/'config.json');index=json.loads((weights/'model.safetensors.index.json').read_text())['weight_map'];t=time.perf_counter();timings={}
def report(message):print(f'{time.perf_counter()-t:.1f}s {message} [peak {mx.get_peak_memory()/1024**3:.2f} GiB]',flush=True)
def load_stage(module,prefix):
 event('Loading Hi3D '+prefix+' weights')
 stage=[]
 for filename in sorted({file for key,file in index.items() if key.startswith(prefix+'.')}):
  tensors=mx.load(str(weights/filename))
  stage.extend((key[len(prefix)+1:],value) for key,value in tensors.items() if key.startswith(prefix+'.') and not key.endswith('inv_grid_coord'))
  del tensors
 module.load_weights(stage,strict=True);module.freeze();module.eval();mx.eval(module.parameters());del stage;gc.collect();mx.clear_cache();report('LOADED '+prefix);return module
input_path=job/'intermediate-10k.glb';mesh=trimesh.load(input_path,force='mesh',process=False)
vertices=np.asarray(mesh.vertices,np.float32);faces=np.asarray(mesh.faces,np.int64)
assert len(faces)>0 and np.isfinite(vertices).all()
# All inputs are already in the port's +Y-up, +Z-facing frame.
event('Voxelizing the 10k intermediate mesh',.02)
coords=adaptive_voxelize(vertices,faces,config.structure_resolutions[0],config.pass_budgets[0]);np.save(out/'input-voxel-coordinates.npy',coords);report(f'INPUT {len(vertices)} verts {len(faces)} tris; {len(coords)} support voxels')
condition_path=tmp/'conditioning.npy'
if condition_path.exists():cond=mx.array(np.load(condition_path));report('REUSED identical-image conditioning')
else:
 start=time.perf_counter();encoder=load_stage(Conditioner(config),'conditioner');prepared=prepare_image(Image.open(image_path));prepared.save(out/'conditioned-image.png');cond=encoder(prepared);mx.eval(cond);atomic_numpy_save(np,condition_path,np.array(cond));del encoder;gc.collect();mx.clear_cache();timings['conditioning']=time.perf_counter()-start;report('CONDITIONING_COMPLETE')
grid=Grid(mx.array(coords),config.structure_resolutions[0]);latent_path=tmp/(name+'-latents.npy')
if latent_path.exists():latents=mx.array(np.load(latent_path));report('RESUME current-task sampled latents')
else:
 start=time.perf_counter();transformer=load_stage(Hi3DTransformer(config.transformer_512),'transformer_512');key=mx.random.key(settings['refiner_seed']);key,subkey=mx.random.split(key);noise=mx.random.normal((1,len(grid),transformer.config.in_channels),key=subkey)
 latents=sample(transformer,cond,grid,noise,25,config.sigma_min,config.time_rescale_factor,lambda i,n:event('Hi3D refinement',.2+.55*i/n,i,n));mx.eval(latents);atomic_numpy_save(np,latent_path,np.array(latents));timings['sampling_including_load']=time.perf_counter()-start;del transformer,noise;gc.collect();mx.clear_cache();report('SAMPLING_COMPLETE')
del cond;gc.collect();mx.clear_cache()
event('Decoding refined geometry',.78)
start=time.perf_counter();vae=load_stage(VAE(config.decoder),'vae');sign,feats,decoded=decode(vae,latents,grid);decode_coords=np.array(decoded.coords);decode_resolution=decoded.resolution;np.savez_compressed(tmp/(name+'-decoded.npz'),sign=sign,feats=feats,coords=decode_coords,resolution=decode_resolution);del vae,latents,decoded,grid;gc.collect();mx.clear_cache();report(f'DECODE_COMPLETE {len(decode_coords)} voxels')
v,f=decoded_mesh(sign,feats,decode_coords,decode_resolution,grid_matrix(coords));f=fill_holes(v,f);timings['decode_extract_including_load']=time.perf_counter()-start;report(f'EXTRACTED {len(v)} verts {len(f)} triangles')
raw_triangles=len(f)
trimesh.Trimesh(vertices=v,faces=f,process=False).export(out/'extracted-raw.glb')
event('Hi3D native triangle reduction',.95)
start=time.perf_counter();v,f=postprocess(v,f,settings['triangles']);timings['postprocess']=time.perf_counter()-start
assert np.isfinite(v).all() and len(f)>0
refined=trimesh.Trimesh(vertices=v,faces=f,process=False)
refined.visual=trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name='Neutral geometry review',baseColorFactor=[170,175,180,255],roughnessFactor=.86,metallicFactor=0))
refined.export(job/('untextured.glb' if settings.get('texture')=='mv' else 'model.glb'),include_normals=True);write_obj(str(out/'refined.obj'),v,f)
metrics={'model':'Hi3D v1.0 unofficial MLX port','mlx_version':importlib.metadata.version('mlx'),'finite_checked_each_step':True,'input':str(input_path),'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'input_triangles':len(faces),'input_voxels':len(coords),'raw_extracted_triangles':raw_triangles,'output_vertices':len(v),'output_triangles':len(f),'structure_grid_resolution':config.structure_resolutions[0],'requested_resolution':512,'extraction_grid_resolution':decode_resolution,'steps':25,'seed':settings['refiner_seed'],'generation_seconds':time.perf_counter()-t,'timings':timings,'mlx_peak_active_gib':mx.get_peak_memory()/1024**3,'memory_limit_gib':10,'cache_limit_mib':256,'execution':'Same MLX port math and released dtypes; staged loading with run-local conditioning and latent checkpoints','output_scope':'Geometry only; native Hi3D postprocessing to the configured triangle budget'}
(out/'runtime.json').write_text(json.dumps(metrics,indent=2));report('COMPLETE '+json.dumps(metrics))

event('Hi3D mesh saved',1)
