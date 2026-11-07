"""Explicit download/setup path. Inference itself is offline."""
import hashlib,json,os,platform,subprocess,sys
from .config import ROOT,RUNTIME,MODES,REPOS,python,resolve_texture

def invoke(args):
 print('+ '+' '.join(map(str,args)),flush=True)
 subprocess.run(list(map(str,args)),check=True)

def patch(repo,path):
 if subprocess.run(['git','-C',str(repo),'apply','--reverse','--check',str(path)],capture_output=True).returncode==0:return
 invoke(['git','-C',repo,'apply','--check',path]);invoke(['git','-C',repo,'apply',path])

def setup_paint():
 req=ROOT/'requirements-paint.txt';stamp=RUNTIME/'paint-dependencies.sha256'
 digest=hashlib.sha256(req.read_bytes()).hexdigest()
 (RUNTIME/'paint.ready').unlink(missing_ok=True)
 if not stamp.exists() or stamp.read_text()!=digest:
  invoke([python('hunyuan'),'-m','pip','install','--disable-pip-version-check','-r',req]);stamp.write_text(digest)
 invoke([python('hunyuan'),ROOT/'workers/download.py','hunyuan-paint'])
 invoke([python('hunyuan'),'-c',"import xatlas,mlx.core,numpy,scipy,cv2,trimesh"])
 (RUNTIME/'paint.ready').write_text('hunyuan3d-paint-v2-0 MLX RGB')

def setup_mv():
 # Reuse GLGMesh's pinned base packages without installing into either base env.
 executable=python('mv')
 if not executable.exists():invoke([sys.executable,'-m','venv',executable.parents[1]])
 sites=[]
 for env in ['torch','hunyuan']:
  sites.append(subprocess.check_output([str(python(env)),'-c','import sysconfig;print(sysconfig.get_paths()["purelib"])'],text=True).strip())
 site=subprocess.check_output([str(executable),'-c','import sysconfig;print(sysconfig.get_paths()["purelib"])'],text=True).strip()
 from pathlib import Path
 (Path(site)/'glgmesh-base-runtimes.pth').write_text('\n'.join(sites)+'\n')
 req=ROOT/'requirements-mv.txt';stamp=RUNTIME/'mv-dependencies.sha256'
 digest=hashlib.sha256(req.read_bytes()).hexdigest()
 (RUNTIME/'mv.ready').unlink(missing_ok=True)
 if not stamp.exists() or stamp.read_text()!=digest:
  invoke([executable,'-m','pip','install','--disable-pip-version-check','--no-deps','-r',req]);stamp.write_text(digest)
 invoke([executable,ROOT/'workers/download.py','mv-adapter','sd21'])
 invoke([executable,ROOT/'workers/check_mv.py'])
 (RUNTIME/'mv.ready').write_text('MV-Adapter SD2.1 MPS · 512px / 40 steps / 2K atlas')

def setup(mode,texture='auto'):
 selected=list(MODES) if mode=='all' else [mode]
 if texture not in ['auto','none','rgb','mv']:raise ValueError('Invalid texture setting')
 textures=set()
 for m in selected:
  choice=texture
  if mode=='all' and ((texture=='rgb' and m not in ['fast','medium']) or (texture=='mv' and m not in ['medium','production'])):choice='none'
  textures.add(resolve_texture(m,choice))
 if platform.system()!='Darwin' or platform.machine()!='arm64':raise RuntimeError('This release targets Apple Silicon macOS.')
 for env in sorted({e for m in selected for e in MODES[m]['envs']} | ({'torch','hunyuan'} if 'mv' in textures else set())):
  executable=python(env);req=ROOT/'locks'/f'{env}.txt'
  if not req.exists():req=ROOT/f'requirements-{env}.txt'
  stamp=executable.parents[1]/'glgmesh-requirements.sha256';digest=hashlib.sha256(req.read_bytes()).hexdigest()
  if not executable.exists():invoke([sys.executable,'-m','venv',executable.parents[1]])
  if not stamp.exists() or stamp.read_text()!=digest:
   invoke([executable,'-m','pip','install','--disable-pip-version-check','-r',req]);stamp.write_text(digest)
 for name in sorted({n for m in selected for n in MODES[m]['repos']} | ({'mv-adapter','hunyuan'} if 'mv' in textures else set())):
  url,rev=REPOS[name];repo=RUNTIME/'repos'/name
  if not (repo/'.git').exists():invoke(['git','clone','--no-checkout',url,repo])
  head=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
  if head!=rev or not (repo/'.git/index').exists():invoke(['git','-C',repo,'checkout',rev])
  if name=='trellis':
   official=repo/'TRELLIS.2'
   if not (official/'.git').exists():invoke(['git','clone','https://github.com/microsoft/TRELLIS.2.git',official]);invoke(['git','-C',official,'checkout','75fbf0183001ed9876c8dbb35de6b68552ee08bd'])
   patch(official,ROOT/'patches/trellis-official.patch')
   if not (repo/'.glgmesh-compat').exists():
    invoke([python('torch'),repo/'patches/mps_compat.py'])
    invoke([python('torch'),'-c',"import sys;sys.path.insert(0,sys.argv[1]);from backends.stubs import install_stubs;install_stubs(sys.argv[2])",repo,repo/'stubs'])
    (repo/'.glgmesh-compat').touch()
   patch(official,ROOT/'patches/trellis-official.patch')
  if (ROOT/'patches'/f'{name}.patch').exists():patch(repo,ROOT/'patches'/f'{name}.patch')
 if 'production-textured' in selected:
  req=ROOT/'requirements-gaustudio.txt';stamp=RUNTIME/'gaustudio-dependencies.sha256'
  digest=hashlib.sha256(req.read_bytes()).hexdigest()
  (RUNTIME/'production-textured.ready').unlink(missing_ok=True)
  if not stamp.exists() or stamp.read_text()!=digest:
   invoke([python('torch'),'-m','pip','install','--disable-pip-version-check','-r',req]);stamp.write_text(digest)
  invoke([python('torch'),ROOT/'workers/check_gaustudio.py'])
 names=sorted({w for m in selected for w in MODES[m]['weights']})
 env='torch' if any(m in selected for m in ['high','production','production-textured']) else 'hunyuan'
 invoke([python(env),ROOT/'workers/download.py',*names])
 invoke([python(env),'-c',"import os,sys;os.environ['U2NET_HOME']=sys.argv[1];from rembg import new_session;new_session('u2net',providers=['CPUExecutionProvider'])",RUNTIME/'weights/background'])
 for m in selected:
  (RUNTIME/f'{m}.ready').write_text(json.dumps({'mode':m,'weights':MODES[m]['weights'],'version':1}))
 if 'rgb' in textures:setup_paint()
 if 'mv' in textures:setup_mv()
 print('SETUP_COMPLETE',','.join(selected),flush=True)
