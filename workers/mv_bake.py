from common import *
from texture_mesh import export_mesh
import time
import numpy as np
from PIL import Image
from hy3dpaint_mlx.raster import cr_raster
from hy3dpaint_mlx.mesh_render import MeshRender,mean_vertex_normals
import torch,types
repo=RUNTIME/'repos/mv-adapter';sys.path.insert(0,str(repo))
pkg=types.ModuleType('mvadapter.utils.mesh_utils');pkg.__path__=[str(repo/'mvadapter/utils/mesh_utils')];sys.modules[pkg.__name__]=pkg
from mvadapter.utils.mesh_utils.camera import get_orthogonal_camera
job,cfg,_=context();out=stage_dir(job,'mv');start=time.monotonic();d=np.load(out/'prepared.npz');data=np.load(out/'cameras.npz');v=data['vertices'];f=data['faces']
cams=get_orthogonal_camera(elevation_deg=[0,0,0,0,89.99,-89.99],distance=[1.8]*6,left=-.55,right=.55,bottom=-.55,top=.55,azimuth_deg=[-90,0,90,180,90,90],device='cpu')
r=MeshRender();r.load_mesh(d['vertices'],d['faces']);r.set_uv(d['uv'],d['faces']);r.vtx_pos=v;r.face_world_normals=r._face_normals(v,f)
event('Projecting native views onto the 2K UV atlas',.1)
TEX=2048;P,N,mask=r.uv_rasterize(TEX);Pw=np.c_[P[mask],np.ones(mask.sum())];N=N[mask]
def run(views,dest,details,alphas=None):
    acc=np.zeros((len(Pw),3));ws=np.zeros((len(Pw),1))
    for i,(im,mvp,w2c) in enumerate(zip(views,cams.mvp_mtx.numpy(),cams.w2c.numpy())):
        H,W=im.shape[:2];clip=np.c_[v,np.ones(len(v))]@mvp.T;fi,ba=cr_raster.rasterize_backend(clip.astype(np.float32),f,H,backend='auto')
        z=(np.c_[v,np.ones(len(v))]@w2c.T)[:,2:3];depth=cr_raster.interpolate(z.astype(np.float32),fi,ba,f)[...,0]
        ndc=Pw@mvp.T;ndc=ndc[:,:2]/ndc[:,3:4];cf=(ndc[:,0]*.5+.5)*(W-1)+.5;rf=(ndc[:,1]*.5+.5)*(H-1)+.5
        ri=np.clip(rf.astype(int),0,H-1);ci=np.clip(cf.astype(int),0,W-1)
        valid=(rf>=0)&(rf<H)&(cf>=0)&(cf<W)&(fi[ri,ci]>0)&(np.abs((Pw@w2c.T)[:,2]-depth[ri,ci])<.015)
        cos=(N@w2c[:3,:3].T)[:,2]/np.clip(np.linalg.norm(N,axis=1),1e-8,None)
        if bool(d['double_sided']):cos=np.abs(cos)
        wt=(valid*np.clip(cos,0,1)**4)[:,None]
        col=r._bilinear(im,np.clip(rf,0,H-1),np.clip(cf,0,W-1))
        if alphas is not None:
            aa=r._bilinear(alphas[i],np.clip(rf,0,H-1),np.clip(cf,0,W-1))
            wt*=aa[:,:1]>.05
            col=np.clip(col-(1-aa),0,1);acc+=col*wt;ws+=wt*aa[:,:1]
        else:acc+=col*wt;ws+=wt
    tex=np.zeros((TEX,TEX,3),np.float32);cov=np.zeros((TEX,TEX),bool);tex[mask]=acc/np.clip(ws,1e-8,None);cov[mask]=ws[:,0]>1e-6
    if not cov.any():raise RuntimeError('No MV-Adapter texture coverage')
    export_mesh(job,d,r.inpaint(tex,cov),'MV_Adapter_SD21')
    metrics=dict(coverage_before_fill=float(cov.mean()),two_sided_bake=bool(d['double_sided']),bake='Calibrated visibility and angle-weighted CPU/Metal projection',**details,
                 triangles=len(f),geometry_preserved=True,texture_size=2048,repaired_uv_faces=int(d['repaired_uv_faces']),bake_seconds=time.monotonic()-start)
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2))
    event('MV-Adapter textured mesh ready',1)

native=[np.asarray(Image.open(out/f'view-{i}.png'),np.float32)/255 for i in range(6)]
run(native,out,dict(**json.loads((out/'generation.json').read_text()),view_source='Native AI multiview'))

