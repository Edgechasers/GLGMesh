"""Apply the existing Hi3D native postprocessor to its saved dense mesh."""
from common import *
import time
import bootstrap
import numpy as np,trimesh
from mlx_vlm.models.hi3d.mesh import postprocess
job,cfg,_=context();out=stage_dir(job,'hi3d');start=time.monotonic()
source=out/'extracted-raw.glb';mesh=trimesh.load(source,force='mesh',process=False)
event('Reusing saved Hi3D geometry; no splat or inference rerun',.05)
v,f=postprocess(mesh.vertices,mesh.faces,cfg['triangles'])
if not np.isfinite(v).all() or not 0<len(f)<=cfg['triangles']:raise RuntimeError('Hi3D reduction did not meet the requested budget')
model=trimesh.Trimesh(vertices=v,faces=f,process=False)
model.visual=trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name='Neutral geometry',baseColorFactor=[170,175,180,255],roughnessFactor=.86,metallicFactor=0))
model.export(job/('untextured.glb' if cfg.get('texture')=='mv' else 'model.glb'),include_normals=True)
(out/'resample.json').write_text(json.dumps({'method':'Hi3D native postprocess','source_triangles':len(mesh.faces),'target':cfg['triangles'],'triangles':len(f),'seconds':time.monotonic()-start,'inference_rerun':False,'splat_regenerated':False},indent=2))
event('Reduced Hi3D mesh ready',1)
