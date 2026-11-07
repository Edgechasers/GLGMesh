"""Equivalent submanifold convolution with CPU neighbor indices and bounded gathers."""
import numpy as np
import torch

def sparse_conv3d_forward(self,x):
    Co,Kd,Kh,Kw,Ci=self.weight.shape
    key=f'bounded_neighbors_{Kd}_{Kh}_{Kw}_{self.dilation}'
    pairs=x.get_spatial_cache(key)
    if pairs is None:
        coords=x.coords.cpu().numpy().astype(np.int64)
        lower=coords.min(0);upper=coords.max(0);sizes=upper-lower+1
        strides=np.array([sizes[1]*sizes[2]*sizes[3],sizes[2]*sizes[3],sizes[3],1],dtype=np.int64)
        hashes=(coords-lower)@strides;order=np.argsort(hashes);sorted_hash=hashes[order]
        pairs=[]
        for kz in range(Kd):
            for ky in range(Kh):
                for kx in range(Kw):
                    delta=np.array([0,(kz-Kd//2)*self.dilation[0],(ky-Kh//2)*self.dilation[1],(kx-Kw//2)*self.dilation[2]])
                    target=np.flatnonzero(np.all((coords+delta>=lower)&(coords+delta<=upper),axis=1))
                    wanted=hashes[target]+delta@strides;idx=np.searchsorted(sorted_hash,wanted)
                    good=idx<len(hashes);target=target[good];wanted=wanted[good];idx=idx[good]
                    good=sorted_hash[idx]==wanted
                    pairs.append((order[idx[good]].astype(np.int32),target[good].astype(np.int32)))
        x.register_spatial_cache(key,pairs)
        print('CONV_NEIGHBORS',len(coords),'voxels',flush=True)
    weight=self.weight.reshape(Co,Kd*Kh*Kw,Ci).permute(1,2,0)
    out=torch.zeros(len(x.feats),Co,device=x.feats.device,dtype=x.feats.dtype)
    for k,(source,target) in enumerate(pairs):
        for start in range(0,len(source),8192):
            si=torch.as_tensor(source[start:start+8192].astype(np.int64),device=out.device)
            ti=torch.as_tensor(target[start:start+8192].astype(np.int64),device=out.device)
            # Each target is unique within a kernel offset, so indexed assignment equals scatter-add.
            out[ti]=out[ti]+x.feats[si]@weight[k]
    if self.bias is not None:out=out+self.bias
    return x.replace(out)

def install():
    from trellis2.modules.sparse.conv import conv_none
    conv_none.sparse_conv3d_forward=sparse_conv3d_forward
