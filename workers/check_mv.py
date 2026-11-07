"""Setup-time import and device check, without loading inference weights."""
from common import *
import types
from texture_mesh import prepare_mesh
import torch,mlx.core,xatlas,accelerate,peft,omegaconf,sentencepiece,psutil
repo=RUNTIME/'repos/mv-adapter';sys.path.insert(0,str(repo))
pkg=types.ModuleType('mvadapter.utils.mesh_utils');pkg.__path__=[str(repo/'mvadapter/utils/mesh_utils')];sys.modules[pkg.__name__]=pkg
from mvadapter.pipelines.pipeline_mvadapter_i2mv_sd import MVAdapterI2MVSDPipeline
from mvadapter.utils.mesh_utils.camera import get_orthogonal_camera
from hy3dpaint_mlx.raster import cr_raster
assert torch.backends.mps.is_available(), 'MV-Adapter requires Apple MPS'
print('MV_ADAPTER_READY · MPS inference / Metal projection')
