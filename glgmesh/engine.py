"""Shared CLI/UI job runner. One local model job at a time, durable stage checkpoints."""
import contextlib,fcntl,hashlib,json,os,re,shutil,signal,struct,subprocess,sys,threading,time,uuid
from pathlib import Path
from .config import ROOT,RUNTIME,RUNS,BLENDER,MODES,settings,python,stages,resolve_texture,TEXTURE_DEFAULTS

def atomic(path,data):
 pending=path.with_suffix(path.suffix+'.tmp');pending.write_text(json.dumps(data,indent=2));pending.replace(path)
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def fingerprint():
 h=hashlib.sha256()
 for directory in ['glgmesh','workers','patches','locks']:
  for p in sorted((ROOT/directory).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':h.update(str(p.relative_to(ROOT)).encode());h.update(p.read_bytes())
 for p in sorted(ROOT.glob('requirements-*.txt')):h.update(p.read_bytes())
 h.update((ROOT/'weights.json').read_bytes())
 return h.hexdigest()
def glb_stats(path):
 with open(path,'rb') as f:
  magic,version,length=struct.unpack('<4sII',f.read(12))
  if magic!=b'glTF' or version!=2 or length!=path.stat().st_size:raise ValueError('Invalid GLB output')
  n,kind=struct.unpack('<II',f.read(8));doc=json.loads(f.read(n))
 tris=0
 for mesh in doc['meshes']:
  for p in mesh['primitives']:
   if p.get('mode',4)!=4:raise ValueError('Expected triangle mesh')
   tris+=doc['accessors'][p['indices']]['count']//3 if 'indices' in p else doc['accessors'][p['attributes']['POSITION']]['count']//3
 if tris<1:raise ValueError('Empty mesh')
 return {'triangles':tris,'meshes':len(doc['meshes']),'bytes':length,'sha256':digest(path),
         'embedded_images':sum('bufferView' in image for image in doc.get('images',[])),
         'unlit_materials':sum('KHR_materials_unlit' in m.get('extensions',{}) for m in doc.get('materials',[]))}
def paint_ready():
 spec=json.loads((ROOT/'weights.json').read_text())['hunyuan-paint']
 stamp=RUNTIME/'paint-dependencies.sha256'
 return ((RUNTIME/'paint.ready').is_file() and stamp.is_file() and stamp.read_text()==digest(ROOT/'requirements-paint.txt') and
         all((RUNTIME/'weights/hunyuan-paint'/f).is_file() and (RUNTIME/'weights/hunyuan-paint'/f).stat().st_size for f in spec['files']))

def mv_ready():
 stamp=RUNTIME/'mv-dependencies.sha256'
 if not ((RUNTIME/'mv.ready').is_file() and python('mv').exists() and
         stamp.is_file() and stamp.read_text()==digest(ROOT/'requirements-mv.txt')):return False
 if not all(python(e).exists() for e in ['torch','hunyuan']):return False
 if not all((RUNTIME/'repos'/r/'.git').exists() for r in ['mv-adapter','hunyuan']):return False
 specs=json.loads((ROOT/'weights.json').read_text())
 return all((RUNTIME/'weights'/name/f).is_file() and (RUNTIME/'weights'/name/f).stat().st_size for name in ['mv-adapter','sd21'] for f in specs[name]['files'])

def texture_ready(texture):
 return paint_ready() if texture=='rgb' else mv_ready() if texture=='mv' else True

def doctor():
 weights=json.loads((ROOT/'weights.json').read_text())
 def installed(mode):
  if not (RUNTIME/f'{mode}.ready').exists():return False
  for env in MODES[mode]['envs']:
   if not python(env).exists():return False
  if not (RUNTIME/'weights/background/u2net.onnx').exists():return False
  if mode=='production-textured':
   stamp=RUNTIME/'gaustudio-dependencies.sha256'
   if not stamp.exists() or stamp.read_text()!=digest(ROOT/'requirements-gaustudio.txt'):return False
   if any(not (RUNTIME/'repos'/name/'.git').exists() for name in MODES[mode]['repos']):return False
  for name in MODES[mode]['weights']:
   folder=RUNTIME/'weights'/name;spec=weights[name]
   files=spec.get('files',[])
   if name=='hi3d':
    index=folder/'model.safetensors.index.json'
    if not index.exists():return False
    files=['config.json',*set(json.loads(index.read_text())['weight_map'].values())]
   if any(not (folder/f).is_file() or (folder/f).stat().st_size==0 for f in files):return False
  return True
 busy=False
 if (RUNTIME/'active.lock').exists():
  with open(RUNTIME/'active.lock','a') as f:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:busy=True
 return {'texture_rgb_ready':bool(paint_ready()),'texture_mv_ready':bool(mv_ready()),'busy':busy,'blender':Path(BLENDER).exists(),'platform':'Apple Silicon macOS','modes':{name:{'ready':installed(name),'name':mode['name'],'default_triangles':mode['triangles'],'estimated_minutes':mode['minutes'],'default_texture':TEXTURE_DEFAULTS.get(name,'none')} for name,mode in MODES.items()}}
@contextlib.contextmanager
def machine_lock():
 RUNTIME.mkdir(exist_ok=True)
 with open(RUNTIME/'active.lock','a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('Another GLGMesh generation or setup is active. Wait for it or cancel it first.')
  yield

def console(event,json_mode=False):
 if json_mode:print(json.dumps(event),flush=True);return
 value=event.get('percent',0);bar='━'*int(value/4)+'─'*(25-int(value/4))
 text=f'{bar} {value:5.1f}%  {event.get("stage_name","")} · {event.get("message","")}'
 if sys.stderr.isatty():print('\r'+text.ljust(115),end='\n' if event['status'] in ['failed','cancelled','complete'] else '',file=sys.stderr,flush=True)
 else:print(text,file=sys.stderr,flush=True)


RESAMPLE_INPUTS={
 'production':['hi3d/extracted-raw.glb'],
 'production-textured':['gaustudio/results/gaustudio/mesh-uv.npz','gaustudio/results/gaustudio/basecolor.png','gaustudio/manifest.json','idol/camera.json'],
}

def splat_source(job):
 # Resamples keep their dense mesh locally and refer back to the original splat.
 if job.cfg['mode'] not in RESAMPLE_INPUTS or job.state['status']!='complete':return None
 mode=job.cfg['mode'];visited=set()
 for _ in range(32):
  if job.path.name in visited or job.cfg['mode']!=mode or job.state['status']!='complete':return None
  visited.add(job.path.name)
  if (job.path/'idol/splat.ply').is_file():return job
  parent=job.cfg.get('source_generation_job') or job.cfg.get('source_job')
  if not isinstance(parent,str):return None
  try:job=Job.open(parent)
  except (ValueError,OSError,KeyError):return None
 return None

def output_options(job):
 result=job.state.get('result',{});mode=job.cfg['mode'];complete=job.state['status']=='complete'
 needed=RESAMPLE_INPUTS.get(mode,[])
 available=complete and bool(needed) and all((job.path/p).is_file() for p in needed)
 reason='' if available else ('Saved intermediate files are missing.' if complete and needed else 'Resampling is available on completed Production results.')
 yaw=0.
 if mode=='production-textured' and (job.path/'idol/camera.json').is_file():
  import math
  yaw=float(json.loads((job.path/'idol/camera.json').read_text())['yaw'])-math.pi
 source=splat_source(job);splat_yaw=0.
 if source and (source.path/'idol/camera.json').is_file():
  import math
  try:splat_yaw=float(json.loads((source.path/'idol/camera.json').read_text())['yaw'])-math.pi
  except (ValueError,OSError,KeyError,TypeError):pass
 return {'has_texture':bool(result.get('embedded_images',0)), 'front_yaw':yaw,
         'splat_available':source is not None,'splat_source_job':source.path.name if source else None,
         'splat_yaw':splat_yaw,'splat_reason':'' if source else 'Original splat is unavailable; its generation run may have been removed.', 
         'resample_available':bool(available), 'resample_reason':reason,
         'resample_min':100,'resample_max':2000000}

class Job:
 def __init__(self,path):
  self.path=path;self.cfg=json.loads((path/'config.json').read_text());self.state=json.loads((path/'status.json').read_text());self.listener=None;self.process=None;self.cancelled=threading.Event();self.index=0
 @classmethod
 def create(cls,image,mode='fast',triangles=None,seed=42,refiner_seed=0,texture='auto',idol_steps=None):
  cfg=settings(mode,triangles,seed,refiner_seed,texture,idol_steps);image=Path(image).resolve()
  if not image.is_file() or image.stat().st_size>32*1024**2:raise ValueError('Input must be an image file under 32 MiB')
  cfg.update(input_sha256=digest(image),input_name=image.name,code_sha256=fingerprint(),created=time.time(),local_inference=True)
  ident=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8];path=RUNS/ident;path.mkdir(parents=True)
  shutil.copyfile(image,path/'source-image');atomic(path/'config.json',cfg)
  atomic(path/'status.json',dict(id=ident,status='queued',percent=0,message='Ready to start',mode=mode,stages=[dict(id=s,name=n,status='pending') for s,n,w in stages(cfg)],created=cfg['created']))
  return cls(path)
 @classmethod
 def texture_existing(cls,ident):
  source=cls.open(ident)
  if source.state['status']!='complete' or source.cfg['mode'] not in ['fast','medium','production']:raise ValueError('Choose a completed Prototype, Medium or Production V1 job')
  if source.cfg.get('texture','none')!='none':raise ValueError('This job is already textured')
  result=json.loads((source.path/'result.json').read_text())
  if digest(source.path/'model.glb')!=result['sha256']:raise ValueError('Source mesh changed since completion')
  j=cls.create(source.path/'source-image',source.cfg['mode'],source.cfg['triangles'],source.cfg['seed'],texture='auto',idol_steps=source.cfg.get('idol_steps'))
  shutil.copyfile(source.path/'model.glb',j.path/'source-mesh.glb')
  shutil.copyfile(source.path/'input.png',j.path/'input.png')
  j.cfg.update(texture_only=True,source_job=ident,source_mesh_sha256=digest(j.path/'source-mesh.glb'),prepared_image_sha256=digest(j.path/'input.png'))
  if source.cfg['mode']=='production':
   retained={}
   for f in RESAMPLE_INPUTS['production']:
    if (source.path/f).is_file():
     dest=j.path/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source.path/f,dest);retained[f]=digest(dest)
   j.cfg.update(resample_inputs=retained,source_generation_job=source.cfg.get('source_generation_job',ident))
  j.state['stages']=[dict(id=s,name=n,status='pending') for s,n,w in stages(j.cfg)]
  atomic(j.path/'config.json',j.cfg);atomic(j.path/'status.json',j.state)
  return j
 @classmethod
 def resample_existing(cls,ident,triangles):
  source=cls.open(ident);options=output_options(source)
  if not options['resample_available']:raise ValueError(options['resample_reason'] or 'Saved dense source is unavailable')
  if isinstance(triangles,bool) or not isinstance(triangles,int):raise ValueError('Triangle target must be an integer')
  if not options['resample_min']<=triangles<=options['resample_max']:raise ValueError('Triangle target must be 100–2,000,000; it may be above or below the current count')
  result=json.loads((source.path/'result.json').read_text())
  if digest(source.path/'model.glb')!=result['sha256']:raise ValueError('Source model changed since completion')
  files=['input.png',*RESAMPLE_INPUTS[source.cfg['mode']]]
  saved={}
  for marker in source.path.glob('*.complete.json'):saved.update(json.loads(marker.read_text()))
  saved.update(source.cfg.get('resample_inputs',{}))
  for f in files:
   if not (source.path/f).is_file():raise ValueError('Missing resample source: '+f)
   if f in saved and digest(source.path/f)!=saved[f]:raise ValueError('Saved intermediate changed: '+f)
  j=cls.create(source.path/'source-image',source.cfg['mode'],triangles,source.cfg['seed'],source.cfg.get('refiner_seed',0),texture=source.cfg.get('texture','none'),idol_steps=source.cfg.get('idol_steps',50))
  for f in files:
   dest=j.path/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source.path/f,dest)
  j.cfg.update(resample_only=True,source_job=ident,source_generation_job=source.cfg.get('source_generation_job',ident),
               source_triangles=result['triangles'],source_model_sha256=result['sha256'],
               resample_inputs={f:digest(j.path/f) for f in files})
  j.state['stages']=[dict(id=s,name=n,status='pending') for s,n,w in stages(j.cfg)]
  atomic(j.path/'config.json',j.cfg);atomic(j.path/'status.json',j.state)
  return j
 @classmethod
 def open(cls,ident):
  if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-f0-9]{8}',ident):raise ValueError('Invalid job ID')
  return cls(RUNS/ident)
 def emit(self,message,fraction=None,step=None,total=None,**extra):
  plan=stages(self.cfg);base=sum(x[2] for x in plan[:self.index]);weight=plan[self.index][2]
  percent=base+(weight*max(0,min(1,fraction)) if fraction is not None else 0)
  self.state.update(message=message,percent=max(self.state.get('percent',0),percent),indeterminate=fraction is None,step=step,total=total,updated=time.time(),elapsed_seconds=time.time()-self.state.get('started',time.time()),**extra)
  atomic(self.path/'status.json',self.state)
  with open(self.path/'events.jsonl','a') as f:f.write(json.dumps(self.state)+'\n')
  if self.listener:self.listener(self.state.copy())
 def cancel(self):
  self.cancelled.set()
  if self.process and self.process.poll() is None:
   try:os.killpg(self.process.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   def force_stop(process):
    try:process.wait(timeout=8)
    except subprocess.TimeoutExpired:
     try:os.killpg(process.pid,signal.SIGKILL)
     except ProcessLookupError:pass
   threading.Thread(target=force_stop,args=(self.process,),daemon=True).start()
 def command(self,args):
  if self.cancelled.is_set():raise InterruptedError('Cancelled')
  env={**os.environ,'PYTHONUNBUFFERED':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','PYTHONHASHSEED':str(self.cfg['seed'])}
  self.process=subprocess.Popen(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env=env,cwd=ROOT)
  with open(self.path/'console.log','a') as log:
   for line in self.process.stdout:
    log.write(line);log.flush()
    if 'GLGMESH_EVENT ' in line:self.emit(**json.loads(line.split('GLGMESH_EVENT ',1)[1]))
   code=self.process.wait()
   self.process.stdout.close()
  self.process=None
  if self.cancelled.is_set():raise InterruptedError('Cancelled')
  if code:raise RuntimeError(f'Local worker exited with code {code}. See console.log for details.')
 def worker(self,name,env):self.command([python(env),ROOT/'workers'/f'{name}.py',self.path])
 def run(self):
  if self.state['status']=='complete' and (self.path/'model.glb').exists():
   if self.listener:self.listener(self.state.copy())
   return
  stopped=threading.Event()
  (self.path/'cancel.request').unlink(missing_ok=True)
  def watch_cancel():
   while not stopped.wait(.25):
    if (self.path/'cancel.request').exists():self.cancel();return
  threading.Thread(target=watch_cancel,daemon=True).start()
  try:
   with machine_lock():
    mode=self.cfg['mode']
    if not self.cfg.get('resample_only') and not doctor()['modes'][mode]['ready']:raise RuntimeError(f'Install this mode first: ./glgmesh.sh setup {mode}')
    if not texture_ready(self.cfg.get('texture','none')):raise RuntimeError('Install texturing first: ./glgmesh.sh setup '+mode+' --texture '+self.cfg['texture'])
    if not Path(BLENDER).exists():raise RuntimeError('Blender missing. Set GLGMESH_BLENDER to the Blender executable.')
    if self.cfg['code_sha256']!=fingerprint():raise RuntimeError('Pipeline code changed since this job. Start a new run to avoid mixing checkpoints.')
    self.state.update(status='running',pid=os.getpid(),started=time.time(),percent=0)
    if digest(self.path/'source-image')!=self.cfg['input_sha256']:raise RuntimeError('Source image changed. Start a new run.')
    self.emit('Validating and preparing image')
    if self.cfg.get('resample_only'):
     for f,sha in self.cfg['resample_inputs'].items():
      if digest(self.path/f)!=sha:raise RuntimeError('Resample source changed: '+f)
    elif self.cfg.get('texture_only'):
     for f,k in [('source-mesh.glb','source_mesh_sha256'),('input.png','prepared_image_sha256')]:
      if digest(self.path/f)!=self.cfg[k]:raise RuntimeError('Texture source changed: '+f)
    else:self.worker('prepare',MODES[mode]['envs'][0])
    for self.index,(name,label,weight) in enumerate(stages(self.cfg)):
     self.state['stage_name']=label;self.state['stage']=name
     marker=self.path/(name+'.complete.json')
     if marker.exists():
      saved=json.loads(marker.read_text())
      if all((self.path/p).exists() and digest(self.path/p)==sha for p,sha in saved.items()):
       self.state['stages'][self.index]['status']='complete';self.emit('Resumed completed stage',1);continue
     for downstream,_,_ in stages(self.cfg)[self.index+1:]:
      (self.path/(downstream+'.complete.json')).unlink(missing_ok=True)
     self.state['stages'][self.index]['status']='running';self.emit('Starting '+label,0)
     if name=='hunyuan':self.worker(name,'hunyuan');outputs=['hunyuan/raw.glb']
     elif name=='paint':
      self.worker('paint','hunyuan')
      stats=glb_stats(self.path/'model.glb')
      source=glb_stats(self.path/('source-mesh.glb' if self.cfg.get('texture_only') else 'untextured.glb'))
      if stats['triangles']!=source['triangles'] or not stats['embedded_images']:raise RuntimeError('Paint changed triangle count or omitted its texture')
      outputs=['model.glb','basecolor.png','paint/metrics.json','paint/views.png']
     elif name=='mv_adapter':
      self.worker(name,'mv');outputs=['mv/prepared.npz','mv/cameras.npz','mv/generation.json','mv/views.png']+[f'mv/view-{i}.png' for i in range(6)]
     elif name=='mv_bake':
      self.worker(name,'mv')
      stats=glb_stats(self.path/'model.glb');source=glb_stats(self.path/('source-mesh.glb' if self.cfg.get('texture_only') else 'untextured.glb'))
      if stats['triangles']!=source['triangles'] or not stats['embedded_images']:raise RuntimeError('MV-Adapter changed triangle count or omitted its texture')
      outputs=['model.glb','basecolor.png','mv/metrics.json']
     elif name=='trellis':self.worker(name,'torch');outputs=['model.glb']
     elif name=='idol':self.worker(name,'torch');outputs=['idol/gaussians.npz','idol/camera.json','idol/splat.ply']
     elif name=='gaustudio':
      self.worker(name,'torch');outputs=['gaustudio/results/gaustudio/mesh-uv.npz','gaustudio/results/gaustudio/basecolor.png','gaustudio/results/gaustudio/raw-mesh.ply','gaustudio/results/gaustudio/runtime.json','gaustudio/manifest.json']
     elif name=='texture_reduce':
      self.command([BLENDER,'-b','--factory-startup','--python-exit-code','1','-P',ROOT/'workers/blender_textured.py','--',self.path])
      stats=glb_stats(self.path/'model.glb')
      if stats['triangles']>self.cfg['triangles']:raise RuntimeError('Textured output exceeds the triangle target')
      if not stats['embedded_images'] or not stats['unlit_materials']:raise RuntimeError('Textured output is missing its embedded appearance texture')
      outputs=['model.glb','model.blend','basecolor.png','model-reduction.json']
     elif name=='surface':self.worker(name,'torch');outputs=['surface/raw.glb']
     elif name=='hi3d_reduce':self.worker(name,'hi3d');outputs=[('untextured.glb' if self.cfg.get('texture')=='mv' else 'model.glb'),'hi3d/resample.json','hi3d/extracted-raw.glb']
     elif name=='hi3d':self.worker(name,'hi3d');outputs=[('untextured.glb' if self.cfg.get('texture')=='mv' else 'model.glb'),'hi3d/extracted-raw.glb']
     elif name=='reduce':
      source=self.path/('surface/raw.glb' if mode=='production' else 'hunyuan/raw.glb');target=10000 if mode=='production' else self.cfg['triangles'];dest=self.path/('intermediate-10k.glb' if mode=='production' else ('untextured.glb' if self.cfg.get('texture') in ['rgb','mv'] else 'model.glb'))
      self.command([BLENDER,'-b','--factory-startup','--python-exit-code','1','-P',ROOT/'workers/blender_reduce.py','--',source,dest,str(target)])
      reduced=glb_stats(dest)
      if reduced['triangles']>target:raise RuntimeError('Blender output exceeds the triangle target')
      outputs=[dest.name]
     else:
      stats=glb_stats(self.path/'model.glb')
      if stats['triangles']>self.cfg['triangles']:raise RuntimeError(f'Output has {stats["triangles"]} triangles, over requested {self.cfg["triangles"]}.')
      atomic(self.path/'result.json',{**stats,'requested_triangles':self.cfg['triangles'],'settings':self.cfg,'weights':{k:v for k,v in json.loads((ROOT/'weights.json').read_text()).items() if k in MODES[mode]['weights']+(['hunyuan-paint'] if self.cfg.get('texture')=='rgb' else ['mv-adapter','sd21'] if self.cfg.get('texture')=='mv' else [])},'local_inference':True,'textured':mode in ['high','production-textured'] or self.cfg.get('texture') in ['rgb','mv'],'preview_style':'textured' if mode=='production-textured' or self.cfg.get('texture') in ['rgb','mv'] else 'neutral'})
      self.command([BLENDER,'-b','--factory-startup','--python-exit-code','1','-P',ROOT/'workers/blender_review.py','--',self.path])
      qa=json.loads((self.path/'qa.json').read_text());result=json.loads((self.path/'result.json').read_text())
      if self.cfg.get('texture')=='rgb':result['paint']=json.loads((self.path/'paint/metrics.json').read_text())
      if self.cfg.get('texture')=='mv':result['mv_adapter']=json.loads((self.path/'mv/metrics.json').read_text())
      result['qa']={'passed':qa.get('pass',False),'errors':qa.get('errors',[]),'warnings':qa.get('warnings',[])}
      atomic(self.path/'result.json',result)
      outputs=['model.glb','result.json','preview.png','qa.json']+(['model.blend'] if self.cfg.get('texture') in ['rgb','mv'] else [])
     for output in outputs:
      if not (self.path/output).is_file() or not (self.path/output).stat().st_size:raise RuntimeError('Missing stage output '+output)
     atomic(marker,{p:digest(self.path/p) for p in outputs})
     self.state['stages'][self.index]['status']='complete';self.emit(label+' complete',1)
    self.state['status']='complete';self.state['percent']=100;self.state['result']=json.loads((self.path/'result.json').read_text());self.emit('Mesh ready',1)
  except (KeyboardInterrupt,InterruptedError):
   self.cancel();self.state['status']='cancelled';self.emit('Cancelled. Completed stages are saved for resume.')
  except Exception as e:
   self.state['status']='failed'
   if self.state.get('stage'):self.state['stages'][self.index]['status']='failed'
   self.emit(str(e))
  finally:stopped.set()
