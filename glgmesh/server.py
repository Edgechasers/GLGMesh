"""Loopback-only UI with local processing and no hosted inference."""
import os,base64,json,mimetypes,secrets,subprocess,sys,threading,time,webbrowser
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,unquote
from .config import ROOT,RUNTIME,RUNS,MODES,resolve_texture
from .engine import Job,doctor,output_options,digest,splat_source
from .glb import export_neutral
TOKEN=secrets.token_urlsafe(32)
ACTIVE=None
SETUP={'status':'idle','lines':[]}
GUARD=threading.Lock()

def history():
 result=[]
 for p in sorted(RUNS.glob('*/status.json'),reverse=True)[:30]:
  try:
   s=json.loads(p.read_text())
   if s['status']=='running':
    try:os.kill(s.get('pid',-999999),0)
    except ProcessLookupError:s.update(status='interrupted',message='Run interrupted. Resume to continue.')
   if s['status']=='complete':s['output_options']=output_options(Job(p.parent))
   result.append(s)
  except (ValueError,OSError):pass
 return result

def setup_worker(mode,texture='auto'):
 global SETUP
 SETUP={'status':'running','mode':mode,'lines':[]}
 with open(RUNTIME/f'setup-{mode}.log','w') as log:
  p=subprocess.Popen([sys.executable,'-m','glgmesh','setup',mode,'--texture',texture],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  for line in p.stdout:
   log.write(line);log.flush();SETUP['lines']=(SETUP['lines']+[line.rstrip()])[-80:]
  SETUP['status']='complete' if p.wait()==0 else 'failed'

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def valid_host(self):return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']
 def send(self,value,code=200,mime='application/json'):
  data=json.dumps(value).encode() if mime=='application/json' else value
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob: data:; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; style-src 'self'; connect-src 'self' blob:; frame-ancestors 'none'");self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if not self.valid_host():self.send({'error':'Invalid host'},403);return
  path=unquote(urlsplit(self.path).path)
  if path=='/api/state':self.send({'app':'GLGMesh','version':'0.1.0','token':TOKEN,'doctor':doctor(),'modes':MODES,'jobs':history(),'setup':SETUP});return
  if path.startswith('/runs/'):
   parts=path.split('/')
   if len(parts)!=4 or parts[3] not in ['source-splat.ply','model.glb','model-untextured.glb','input.png','preview.png','front.png','back.png','wireframe.png','clay.png','basecolor.png','model.blend','result.json','qa.json','console.log']:self.send({'error':'Not found'},404);return
   try:
    job=Job.open(parts[2]);file=job.path/parts[3]
    if parts[3]=='source-splat.ply':
     source=splat_source(job)
     if source is None:raise ValueError('Source splat unavailable')
     file=source.path/'idol/splat.ply'
    if parts[3]=='model-untextured.glb':
     if job.state['status']!='complete':raise ValueError('Model is not ready')
     source=job.path/'model.glb';sha=digest(source)
     if sha!=job.state['result']['sha256']:raise ValueError('Source model changed')
     stamp=job.path/'model-untextured.source-sha256'
     if not file.exists() or not stamp.exists() or stamp.read_text()!=sha:
      export_neutral(source,file);stamp.write_text(sha)
   except (ValueError,OSError):self.send({'error':'Not found'},404);return
  else:file=ROOT/'ui'/('index.html' if path=='/' else path.lstrip('/'))
  allowed=ROOT/'ui' if not path.startswith('/runs/') else RUNS
  if not file.resolve().is_relative_to(allowed) or not file.is_file():self.send({'error':'Not found'},404);return
  self.send(file.read_bytes(),mime=mimetypes.guess_type(file)[0] or 'application/octet-stream')
 def do_POST(self):
  global ACTIVE,SETUP
  if not self.valid_host() or self.headers.get('X-GLGMesh-Token')!=TOKEN or self.headers.get('Origin') not in [None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}']:
   self.send({'error':'Unauthorized local request'},403);return
  try:
   size=int(self.headers.get('Content-Length','0'))
   if size<1 or size>45*1024**2:raise ValueError('Request too large')
   data=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
   with GUARD:
    busy=(ACTIVE is not None and ACTIVE.state['status'] in ['queued','running']) or doctor()['busy'] or any(j['status']=='running' for j in history())
    if path=='/api/cancel':
     job=Job.open(data['id'])
     if job.state['status']=='running':
      (job.path/'cancel.request').touch()
      if ACTIVE is not None and ACTIVE.path==job.path:ACTIVE.cancel()
     self.send({'ok':True});return
    if busy or SETUP['status']=='running':raise ValueError('A local task is already running')
    if path=='/api/setup':
     mode=data['mode']
     if mode not in MODES:raise ValueError('Invalid mode')
     resolve_texture(mode,data.get('texture','auto'))
     SETUP={'status':'running','mode':mode,'lines':[]};threading.Thread(target=setup_worker,args=(mode,data.get('texture','auto')),daemon=True).start();self.send({'ok':True});return
    if path=='/api/run':
     mode=data['mode']
     if mode not in MODES or not doctor()['modes'][mode]['ready']:raise ValueError('Install this mode first')
     payload=base64.b64decode(data['image'],validate=True)
     if len(payload)>32*1024**2:raise ValueError('Image exceeds 32 MiB')
     upload=RUNTIME/('upload-'+secrets.token_hex(8))
     try:
      upload.write_bytes(payload);ACTIVE=Job.create(upload,mode,data.get('triangles'),data.get('seed',42),data.get('refiner_seed',0),data.get('texture','auto'),data.get('idol_steps'))
     finally:upload.unlink(missing_ok=True)
    elif path=='/api/resample':
     ACTIVE=Job.resample_existing(data['id'],data.get('triangles'))
    elif path=='/api/resume':
     ACTIVE=Job.open(data['id'])
     if ACTIVE.state['status']=='complete':raise ValueError('Job already completed')
    else:raise ValueError('Unknown action')
    threading.Thread(target=ACTIVE.run,daemon=True).start();self.send({'id':ACTIVE.path.name})
  except (ValueError,KeyError,OSError) as e:self.send({'error':str(e)},400)

def serve(port=8766,open_browser=True):
 RUNTIME.mkdir(exist_ok=True);RUNS.mkdir(exist_ok=True)
 try:server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
 except OSError as error:
  import urllib.request
  url=f'http://127.0.0.1:{port}'
  try:
   with urllib.request.urlopen(url+'/api/state',timeout=2) as response:existing=json.load(response)
  except Exception:raise error
  if existing.get('app')!='GLGMesh':raise error
  print('GLGMesh is already running: '+url,flush=True)
  if open_browser:webbrowser.open(url)
  return
 url=f'http://127.0.0.1:{server.server_port}'
 print(f'GLGMesh UI: {url}\nAll inference runs locally. Keep this process open.',flush=True)
 if open_browser:webbrowser.open(url)
 try:server.serve_forever()
 except KeyboardInterrupt:
  if ACTIVE:ACTIVE.cancel()
 finally:server.server_close()
