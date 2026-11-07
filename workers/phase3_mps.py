"""Memory-bounded exact query chunking for noncausal inference attention on MPS."""
import torch
import torch.nn.functional as F
original_sdpa=F.scaled_dot_product_attention

def bounded_sdpa(q,k,v,attn_mask=None,dropout_p=0.0,is_causal=False,**kw):
    if q.device.type!='mps' or q.shape[-2]<=1024 or is_causal or dropout_p:
        return original_sdpa(q,k,v,attn_mask=attn_mask,dropout_p=dropout_p,is_causal=is_causal,**kw)
    pieces=[]
    for i in range(0,q.shape[-2],512):
        mask=attn_mask
        if mask is not None and mask.shape[-2]>1:mask=mask[...,i:i+512,:]
        pieces.append(original_sdpa(q[...,i:i+512,:],k,v,attn_mask=mask,**kw))
    return torch.cat(pieces,dim=-2)

def enable():
    F.scaled_dot_product_attention=bounded_sdpa
    torch.set_num_threads(8)
    torch.mps.set_per_process_memory_fraction(0.85)
