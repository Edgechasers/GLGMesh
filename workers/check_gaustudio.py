"""Compile and check the Metal depth backend during explicit setup."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['GLGMESH_GAUS_ROOT']=str(ROOT/'runtime/validation/gaustudio-check')
sys.path.insert(0,str(Path(__file__).parent/'gaustudio_support'))
import local_env
local_env.patch_linker()
import open3d,xatlas,numpy,torch
from metal_gauss import metal_backend
assert torch.backends.mps.is_available(),'Metal/MPS GPU is unavailable'
backend=metal_backend._load()
assert hasattr(backend,'median_forward'),'GauStudio median-depth patch missing'
print('GAUSTUDIO_RUNTIME_READY',open3d.__version__,flush=True)
