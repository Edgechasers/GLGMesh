"""Visibility-tested multiview texture projection from original IDOL renders."""
import local_env
import argparse,json,time
import numpy as np
from numba import njit
from scipy.ndimage import map_coordinates,binary_dilation,distance_transform_edt
from PIL import Image
ROOT=local_env.ROOT
@njit(cache=True)
def raster(v,n,c,f,uv,S):
    pos=np.zeros((S,S,3),np.float32);norm=np.zeros_like(pos);color=np.zeros_like(pos);mask=np.zeros((S,S),np.bool_)
    for t in f:
        q=uv[t].copy();q[:,0]*=S-1;q[:,1]=(1-q[:,1])*(S-1)
        x0=max(0,int(np.floor(q[:,0].min())));x1=min(S-1,int(np.ceil(q[:,0].max())))
        y0=max(0,int(np.floor(q[:,1].min())));y1=min(S-1,int(np.ceil(q[:,1].max())))
        ax,ay=q[0];bx,by=q[1];cx,cy=q[2];den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(den)<1e-10:continue
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                a=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/den;b=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/den;d=1-a-b
                if min(a,b,d)<-1e-5:continue
                for k in range(3):
                    pos[y,x,k]=a*v[t[0],k]+b*v[t[1],k]+d*v[t[2],k]
                    norm[y,x,k]=a*n[t[0],k]+b*n[t[1],k]+d*n[t[2],k]
                    color[y,x,k]=a*c[t[0],k]+b*c[t[1],k]+d*c[t[2],k]
                mask[y,x]=True
    return pos,norm,color,mask
def main():
    ap=argparse.ArgumentParser();ap.add_argument('method');ap.add_argument('--size',type=int,default=4096);args=ap.parse_args()
    start=time.monotonic();folder=ROOT/'results'/args.method;d=np.load(folder/'mesh-uv.npz');S=args.size
    pos,norm,texture,mask=raster(d['vertices'],d['normals'],d['colors'],d['triangles'],d['uv'],S)
    points=pos[mask];normals=norm[mask];del pos,norm
    normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-8)
    acc=np.zeros_like(points);weight=np.zeros(len(points),np.float32)
    print('UV TEXELS',len(points),flush=True)
    cameras=json.loads((ROOT/'inputs/cameras.json').read_text())
    for i,cam in enumerate(cameras):
        data=np.load(ROOT/'inputs/rendered'/(cam['img_name']+'.npz'));rgb=data['rgb'].astype(np.float32)/255;dep=data['depth'];alpha=data['alpha'].astype(np.float32)
        R=np.array(cam['rotation'],np.float32);center=np.array(cam['position'],np.float32);H,W=dep.shape
        for lo in range(0,len(points),250000):
            hi=min(lo+250000,len(points));p=points[lo:hi];view=center-p
            cosine=np.sum(view*normals[lo:hi],1)/np.maximum(np.linalg.norm(view,axis=1),1e-8)
            idx=np.flatnonzero(cosine>.65)
            if not len(idx):continue
            pc=(p[idx]-center)@R;x=pc[:,0]/pc[:,2]*cam['fx']+W/2-.5;y=pc[:,1]/pc[:,2]*cam['fy']+H/2-.5
            inside=(x>=0)&(x<W-1)&(y>=0)&(y<H-1)&(pc[:,2]>0)
            idx=idx[inside];x=x[inside];y=y[inside];z=pc[inside,2]
            coords=np.array([y,x]);sd=map_coordinates(dep,coords,order=1,mode='nearest');sa=map_coordinates(alpha,coords,order=1,mode='nearest')
            visible=(sa>.9)&(np.abs(sd-z)<.015)
            ids=lo+idx[visible]
            if not len(ids):continue
            coords=coords[:,visible];w=cosine[idx[visible]]**32
            sample=np.stack([map_coordinates(rgb[:,:,ch],coords,order=1,mode='nearest') for ch in range(3)],1)
            acc[ids]+=sample*w[:,None];weight[ids]+=w
        if i%12==0:print('PROJECTED',i,round(time.monotonic()-start,1),flush=True)
    covered=weight>1e-9;fallback=texture[mask];fallback[covered]=acc[covered]/weight[covered,None];texture[mask]=fallback
    # Six-pixel gutters protect bilinear filtering at UV chart edges.
    gutter=binary_dilation(mask,iterations=6)&~mask
    _,nearest=distance_transform_edt(~mask,return_indices=True)
    texture[gutter]=texture[nearest[0][gutter],nearest[1][gutter]]
    Image.fromarray(np.uint8(np.clip(texture,0,1)*255)).save(folder/'basecolor.png')
    report=dict(texture_size=[S,S],source='Original IDOL splat, 98 calibrated renders',seconds=time.monotonic()-start,
        texels=int(mask.sum()),projected_fraction=float(covered.mean()),unseen='Retained reconstruction vertex colors',
        angle_weight_power=32,depth_tolerance=.015,alpha_threshold=.9,uv_gutter_pixels=6)
    (folder/'texture.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
if __name__=='__main__':main()
