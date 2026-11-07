"""Local image-to-mesh pipelines; no inference services are used."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
RUNS = ROOT / 'runs'
BLENDER = os.environ.get('GLGMESH_BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
MODES = {
 'fast': {'name':'Fast prototype','minutes':3,'triangles':10000,'envs':['hunyuan'], 'weights':['hunyuan-mini'], 'repos':['hunyuan'], 'stages':[('hunyuan','Hunyuan Mini',85),('reduce','Blender reduction',10),('review','Review & export',5)]},
 'medium': {'name':'Medium quality','minutes':20,'triangles':10000,'envs':['hunyuan'], 'weights':['hunyuan-21'], 'repos':['hunyuan'], 'stages':[('hunyuan','Hunyuan 2.1',90),('reduce','Blender reduction',7),('review','Review & export',3)]},
 'high': {'name':'High quality','minutes':15,'triangles':200000,'envs':['torch'], 'weights':['trellis','trellis-ss','dino-l'], 'repos':['trellis'], 'stages':[('trellis','TRELLIS.2 shape & texture',97),('review','Review & export',3)]},
 'production': {'name':'Production V1','minutes':130,'triangles':10000,'envs':['torch','hi3d'], 'weights':['idol','dino-h','flux','hi3d'], 'repos':['idol','hi3d'], 'stages':[('idol','IDOL · 50 sampling steps',86),('surface','Gaussian to mesh',3),('reduce','Blender · 10k intermediate',1),('hi3d','Hi3D · native target',9),('review','Review & export',1)]},
 'production-textured': {'name':'Production V2','minutes':120,'triangles':10000,'envs':['torch'], 'weights':['idol','dino-h','flux'], 'repos':['idol','gaustudio','metal-gauss'], 'stages':[('idol','IDOL · 50 sampling steps',85),('gaustudio','GauStudio · textured mesh',8),('texture_reduce','Target reduction & texture bake',5),('review','Review & export',2)]},
}
TEXTURE_DEFAULTS = {'fast':'rgb','medium':'mv','production':'mv'}
TEXTURE_CHOICES = ['auto','none','rgb','mv']
def resolve_texture(mode, texture='auto'):
 if mode not in MODES:raise ValueError('Unknown mode')
 if texture not in TEXTURE_CHOICES:raise ValueError('Texture must be auto, none, rgb or mv')
 if texture=='auto':texture=TEXTURE_DEFAULTS.get(mode,'none')
 if texture=='rgb' and mode not in ['fast','medium']:raise ValueError('Hunyuan Paint is available for Prototype and Medium')
 if texture=='mv' and mode not in ['medium','production']:raise ValueError('MV-Adapter is available for Medium and Production V1')
 return texture

REPOS = {
 'mv-adapter': ('https://github.com/huanngzh/MV-Adapter.git','4277e0018232bac82bb2c103caf0893cedb711be'),
 'gaustudio': ('https://github.com/GAP-LAB-CUHK-SZ/gaustudio.git','132d749d863f11a6f158aa10c617ea4afc5b7268'),
 'metal-gauss': ('https://github.com/nandometzger/metal-gauss.git','e2405889cf600e8fdeb605c0e48ddbe3ca2fedca'),
 'hunyuan': ('https://github.com/ZimengXiong/Hunyuan3D-Swift.git','292331f4d26ddb80b9dcea6bcb5629ff82f12b82'),
 'trellis': ('https://github.com/apetersson/TRELLIS.2-apple-silicon.git','6a6ec6b3feeb3aead04e37be80eca0538258d1d1'),
 'idol': ('https://github.com/speridlabs/idol-sdk.git','4702a7f00850e34b6e83a2170cc123c3e9570744'),
 'hi3d': ('https://github.com/cguldogan/mlx-vlm.git','ec824bbc06f950cb1dac0505e7233a65f404620e'),
}
def stages(cfg):
 texture=cfg.get('texture','none')  # Historical jobs keep their recorded behavior.
 tail=([('paint','Hunyuan Paint 2.0 · 2K texture',95)] if texture=='rgb' else
       [('mv_adapter','MV-Adapter SD2.1 · six views',85),('mv_bake','MV-Adapter · 2K texture bake',10)] if texture=='mv' else [])
 if cfg.get('texture_only'):return tail+[('review','Review & export',5)]
 if cfg.get('resample_only'):
  plan=([('hi3d_reduce','Hi3D native polygon reduction',90)] if cfg['mode']=='production' else
        [('texture_reduce','Blender reduction & 4K rebake',90)])+[('review','Review & export',10)]
 else:plan=[(s,f"IDOL · {cfg.get('idol_steps',50)} sampling steps" if s=='idol' else n,w) for s,n,w in MODES[cfg['mode']]['stages']]
 if not tail:return plan
 shape=plan[:-1];total=sum(w for _,_,w in shape)
 # The shape process exits before texturing starts to release unified memory.
 return [(s,n,w*50/total) for s,n,w in shape]+[(s,n,w*45/95) for s,n,w in tail]+[('review','Review & export',5)]

def settings(mode, triangles=None, seed=42, refiner_seed=0, texture='auto', idol_steps=None):
 texture=resolve_texture(mode,texture)
 target=MODES[mode]['triangles'] if triangles is None else int(triangles)
 if not 100 <= target <= 2000000: raise ValueError('Triangle target must be 100–2,000,000')
 if not 0 <= int(seed) < 2**32 or not 0 <= int(refiner_seed) < 2**32: raise ValueError('Seeds must be unsigned 32-bit integers')
 cfg=dict(mode=mode,triangles=target,seed=int(seed),refiner_seed=int(refiner_seed),texture=texture)
 if mode in ['production','production-textured']:
  idol_steps=50 if idol_steps is None else idol_steps
  if isinstance(idol_steps,bool) or not isinstance(idol_steps,int) or not 50<=idol_steps<=400:raise ValueError('IDOL steps must be an integer from 50 to 400')
  cfg['idol_steps']=idol_steps
 elif idol_steps is not None:raise ValueError('IDOL steps are available only for Production pipelines')
 return cfg
def python(env): return RUNTIME/'envs'/env/'bin/python'
