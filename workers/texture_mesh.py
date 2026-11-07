"""Geometry-preserving preparation/export shared by local texture workers."""
from common import *
import numpy as np
import trimesh,xatlas
from PIL import Image
sys.path.insert(0,str(RUNTIME/'repos/hunyuan/python/paint'))

def prepare_mesh(source):
 mesh=trimesh.load(source,force='mesh',process=False)
 v=np.asarray(mesh.vertices);f=np.asarray(mesh.faces)
 if not len(f) or not np.isfinite(v).all() or np.ptp(v,axis=0).max()<=0:raise ValueError('Invalid source mesh')
 # Weld coincident seam vertices for chart construction only; retain face positions.
 unique,inverse=np.unique(v,axis=0,return_inverse=True)
 mapping,faces,uv=xatlas.parametrize(unique,inverse[f].astype(np.uint32))
 vertices=unique[mapping];faces=faces.astype(np.int64)
 if not np.array_equal(vertices[faces],v[f]):raise RuntimeError('UV unwrap changed geometry')
 q=uv[faces];bad=np.flatnonzero(np.abs(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]))<2e-12)
 if len(bad):
  # Give collapsed thin UV triangles individual patches without editing geometry.
  uv[:,1]=.1+.9*uv[:,1];cols=int(np.ceil(np.sqrt(len(bad)*10)));rows=int(np.ceil(len(bad)/cols))
  cw,ch=1/cols,.1/rows;margin=min(2/2048,cw*.15,ch*.15)
  extra=[];extra_uv=[]
  for i,face in enumerate(bad):
   x,y=(i%cols)*cw,(i//cols)*ch
   extra.extend(vertices[faces[face]]);extra_uv.extend([[x+margin,y+margin],[x+cw-margin,y+margin],[x+margin,y+ch-margin]])
   faces[face]=np.arange(len(vertices)+3*i,len(vertices)+3*i+3)
  vertices=np.concatenate([vertices,extra]);uv=np.concatenate([uv,extra_uv])
 if not np.array_equal(vertices[faces],v[f]):raise RuntimeError('UV repair changed geometry')
 return dict(vertices=vertices,faces=faces,uv=uv,double_sided=bool(getattr(getattr(mesh.visual,'material',None),'doubleSided',False)),repaired_uv_faces=len(bad))

def export_mesh(job,data,texture,method):
 if not np.isfinite(texture).all():raise RuntimeError('Non-finite texture')
 tex=Image.fromarray(np.uint8(np.clip(texture,0,1)*255));tex.save(job/'basecolor.png')
 mat=trimesh.visual.material.PBRMaterial(name='M_'+method,baseColorTexture=tex,metallicFactor=0.,roughnessFactor=.85,doubleSided=bool(data['double_sided']))
 mesh=trimesh.Trimesh(vertices=data['vertices'],faces=data['faces'],process=False,visual=trimesh.visual.TextureVisuals(uv=data['uv'],material=mat))
 pending=job/'texture-pending.glb';mesh.export(pending)
 check=trimesh.load(pending,force='mesh',process=False)
 if len(check.faces)!=len(data['faces']) or not np.allclose(check.vertices[check.faces],data['vertices'][data['faces']],rtol=1e-6,atol=2e-7):raise RuntimeError('Texture export changed geometry')
 if check.visual.material.baseColorTexture.size!=(2048,2048):raise RuntimeError('Missing embedded 2K texture')
 pending.replace(job/'model.glb')
