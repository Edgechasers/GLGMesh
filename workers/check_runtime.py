"""Import and GPU check without downloading or sampling."""
from common import *
mode=sys.argv[1]
if mode=='hi3d':
 import bootstrap
 from mlx_vlm.models.hi3d.config import ModelConfig
 from mlx_vlm.models.hi3d.vision import Conditioner
 from mlx_vlm.models.hi3d.pipeline import sample,decode
 import pyfqmr
 import mlx.core as mx
 assert bool(mx.all(mx.isfinite(mx.ones((4,4))@mx.ones((4,4)))).item())
elif mode=='idol':
 sys.path.insert(0,str(RUNTIME/'repos/idol'))
 from idol.conditioning import ImageEncoder
 from idol.models import LatentSeqMMFlowModel,GaussianFixedlenDecoder,OctreeProbabilityFixedlenDecoder
 from idol.sampler import sample_flow
 import torch
 assert torch.backends.mps.is_available()
elif mode=='trellis':
 repo=RUNTIME/'repos/trellis'
 os.environ.update(SPARSE_ATTN_BACKEND='sdpa',SPARSE_CONV_BACKEND='none')
 sys.path[:0]=[str(repo),str(repo/'TRELLIS.2')];sys.path.append(str(repo/'stubs'))
 from phase3_mps import enable
 enable()
 from trellis_bounded_conv import install
 install()
 from trellis2.pipelines.trellis2_image_to_3d import Trellis2ImageTo3DPipeline
 from backends.texture_baker import uv_unwrap,bake_texture
else:raise ValueError(mode)
print('LOCAL_RUNTIME_OK',mode,flush=True)
