"""98 calibrated IDOL views in its exported PLY coordinate frame."""
import local_env
import json,math,shutil
import numpy as np
ROOT=local_env.ROOT
def prepare():
    source=ROOT.parent/'idol';out=ROOT/'inputs';out.mkdir(parents=True,exist_ok=True)
    with np.load(source/'gaussians.npz') as data:
        assert all(np.isfinite(data[k]).all() for k in data.files),'Nonfinite splat'
        active=data['opacity'].reshape(-1)>.01
        points=data['xyz'][active].astype(float);scales=data['scaling'][active]
    assert len(points)>0 and (scales>0).all(),'Invalid or empty splat'
    support=3*scales.max(axis=1)
    lower=(points-support[:,None]).min(0);upper=(points+support[:,None]).max(0)
    target=(lower+upper)/2;radius=float(np.linalg.norm(upper-lower)*2.5)
    assert np.isfinite(radius) and radius>0
    native=json.loads((source/'camera.json').read_text());yaw=float(native['yaw'])
    width,height=1024,1280
    specs=[(f'train_{r:02}_{a:02}',yaw+a*math.tau/24,math.radians(p))
           for r,p in enumerate([-65,-25,15,55]) for a in range(24)]
    specs += [('train_bottom',yaw,math.radians(-88)),('train_top',yaw,math.radians(88))]
    poses=[];limits=[]
    for name,yaw,pitch in specs:
        direction=np.array([math.sin(yaw)*math.cos(pitch),math.cos(yaw)*math.cos(pitch),math.sin(pitch)])
        center=target+direction*radius;forward=-direction
        right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right)
        down=np.cross(forward,right);w2c=np.stack([right,down,forward])
        pos=(points-center)@w2c.T;near=pos[:,2]-support
        assert (near>0).all()
        extent=(np.abs(pos[:,:2])+support[:,None])/near[:,None]
        limits.append(min(width*.43/extent[:,0].max(),height*.43/extent[:,1].max()))
        poses.append((name,center,w2c))
    focal=float(min(limits));M=np.array([[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
    cameras=[dict(id=i,img_name=n,width=width,height=height,position=(M@c).tolist(),
                  rotation=(M@R.T).tolist(),fx=focal,fy=focal,cx=width/2,cy=height/2)
             for i,(n,c,R) in enumerate(poses)]
    (out/'cameras.json').write_text(json.dumps(cameras,indent=2))
    shutil.copy2(source/'splat.ply',out/'splat.ply')
    (ROOT/'manifest.json').write_text(json.dumps(dict(native_to_ply=M.tolist(),cameras=98,
        source=f"IDOL {json.loads((ROOT.parent/'config.json').read_text()).get('idol_steps',50)}-step splat",local_adaptation='GauStudio median depth with Metal rendering and Open3D CPU TSDF replacing VDBFusion'),indent=2))
if __name__=='__main__':prepare()
