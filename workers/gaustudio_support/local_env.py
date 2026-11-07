"""Task-local GauStudio adaptation, sharing GLGMesh's persistent Metal cache."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import RUNTIME
ROOT=Path(os.environ['GLGMESH_GAUS_ROOT']).resolve()
for key,sub in {'TORCH_EXTENSIONS_DIR':'metal-extensions','NUMBA_CACHE_DIR':'numba',
                'MPLCONFIGDIR':'matplotlib','XDG_CACHE_HOME':'xdg'}.items():
    p=RUNTIME/'cache'/sub;p.mkdir(parents=True,exist_ok=True);os.environ[key]=str(p)
os.environ.setdefault('MAX_JOBS','4')
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
sys.path.insert(0,str(RUNTIME/'repos/metal-gauss'))
def patch_linker():
    import shlex
    import torch.utils.cpp_extension as ce
    original=ce._prepare_ldflags
    if getattr(original,'_glgmesh',False):return
    def wrapped(*args,**kwargs):
        return [shlex.quote(x) if x.startswith('-L') and ' ' in x else x for x in original(*args,**kwargs)]
    wrapped._glgmesh=True;ce._prepare_ldflags=wrapped
