import json,os,sys,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'
# Inference workers cannot make IP connections. Setup is a separate process.
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',PYTORCH_ENABLE_MPS_FALLBACK='1',ATTN_BACKEND='sdpa')
def deny_connect(*args,**kwargs): raise RuntimeError('Network access is disabled during local inference. Run setup first.')
socket.socket.connect=deny_connect
socket.socket.connect_ex=deny_connect
socket.create_connection=deny_connect

def event(message, fraction=None, step=None, total=None):
 print('\nGLGMESH_EVENT '+json.dumps(dict(message=message,fraction=fraction,step=step,total=total)),flush=True)
def context():
 job=Path(sys.argv[-1]).resolve()
 cfg=json.loads((job/'config.json').read_text())
 return job,cfg,job/'input.png'
def stage_dir(job,name):
 p=job/name;p.mkdir(exist_ok=True);return p


def atomic_torch_save(torch,value,path):
 path=Path(path);pending=path.with_suffix(path.suffix+'.pending')
 torch.save(value,pending);pending.replace(path)

def atomic_numpy_save(np,path,value):
 path=Path(path);pending=path.with_suffix(path.suffix+'.pending')
 with open(pending,'wb') as f:np.save(f,value)
 pending.replace(path)
