import sys,types
from pathlib import Path
from common import RUNTIME
repo=RUNTIME/'repos/hi3d'
for name,rel in [('mlx_vlm','mlx_vlm'),('mlx_vlm.models','mlx_vlm/models'),('mlx_vlm.models.llava','mlx_vlm/models/llava'),('mlx_vlm.models.sam3d_objects','mlx_vlm/models/sam3d_objects')]:
 m=types.ModuleType(name);m.__path__=[str(repo/rel)];sys.modules[name]=m

import mlx.core as mx
assert hasattr(mx, 'searchsorted')
