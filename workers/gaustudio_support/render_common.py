import local_env
local_env.patch_linker()
import json, time
import numpy as np
import torch
from PIL import Image
from metal_gauss.io import load_ply
from metal_gauss import metal_backend
ROOT=local_env.ROOT

def matrices(camera,scale=1):
    W,H=round(camera['width']*scale),round(camera['height']*scale)
    K=np.array([[camera['fx']*scale,0,camera['cx']*scale],
                [0,camera['fy']*scale,camera['cy']*scale],[0,0,1]],dtype=np.float32)
    c2w=np.eye(4);c2w[:3,:3]=camera['rotation'];c2w[:3,3]=camera['position']
    return W,H,torch.from_numpy(K),torch.from_numpy(np.linalg.inv(c2w).astype(np.float32))

class Renderer:
    def __init__(self,path=None):
        self.s=load_ply(path or ROOT/'inputs/splat.ply',device='mps')
    @torch.no_grad()
    def render(self,camera,scale=1,median=False):
        W,H,K,V=matrices(camera,scale)
        s=self.s
        rgb,a,info=metal_backend.render(s.means,s.quats,s.scales,s.opacities,s.sh,K,V,W,H,sh_degree=s.sh_degree)
        depth=None
        if median:
            depth=metal_backend._load().median_forward(info['uv'].contiguous(),info['conic'].contiguous(),
                s.opacities.contiguous(),info['depth'].contiguous(),info['gauss_ids'].contiguous(),
                info['tile_offsets'].contiguous(),W,H,16,info['tiles_x']).cpu().numpy()
        return np.clip(rgb.cpu().numpy(),0,1),a.cpu().numpy(),depth

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=0);ap.add_argument('--scale',type=float,default=1)
    args=ap.parse_args()
    cameras=json.loads((ROOT/'inputs/cameras.json').read_text())
    if args.limit:cameras=cameras[:args.limit]
    out=ROOT/'inputs/rendered';out.mkdir(exist_ok=True)
    r=Renderer();start=time.monotonic()
    for i,c in enumerate(cameras):
        dest=out/(c['img_name']+'.npz')
        # Regenerate frames on stage retry; never trust partial view files.
        rgb,alpha,depth=r.render(c,args.scale,median=True)
        np.savez_compressed(dest,rgb=np.uint8(rgb*255),alpha=alpha.astype(np.float16),depth=depth)
        Image.fromarray(np.uint8(rgb*255)).save(out/(c['img_name']+'.png'))
        print(i,c['img_name'],round(time.monotonic()-start,2),flush=True)
