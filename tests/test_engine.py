import json,struct,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh import engine
from glgmesh.config import settings,MODES

def glb(path,triangles=10000,textured=False):
 doc={'meshes':[{'primitives':[{'indices':0,'attributes':{},'mode':4}]}],'accessors':[{'count':triangles*3}]}
 if textured:doc.update(images=[{'bufferView':0,'mimeType':'image/png'}],materials=[{'extensions':{'KHR_materials_unlit':{}}}])
 payload=json.dumps(doc).encode();payload+=b' '*((-len(payload))%4)
 path.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(payload))+struct.pack('<II',len(payload),0x4e4f534a)+payload)
class RunnerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'image.png';self.source.write_bytes(b'input')
  self.patches=[patch.object(engine,'RUNS',self.root/'runs'),patch.object(engine,'RUNTIME',self.root/'runtime')]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.temp.cleanup()
 def test_defaults_and_invalid_targets(self):
  self.assertEqual([settings(m)['triangles'] for m in MODES],[10000,10000,200000,10000,10000])
  for n in [0,-1,99,2000001]:
   with self.assertRaises(ValueError):settings('fast',n)
  with self.assertRaises(ValueError):settings('cloud')
 def test_jobs_are_isolated_and_source_preserved(self):
  a=engine.Job.create(self.source,texture='none');b=engine.Job.create(self.source,texture='none')
  self.assertNotEqual(a.path,b.path);self.assertEqual((a.path/'source-image').read_bytes(),b'input')
  self.assertEqual(a.cfg['input_sha256'],engine.digest(self.source))
 def test_job_path_traversal_rejected(self):
  for value in ['../runtime','/etc/passwd','20261104-123456-zzzzzzzz']:
   with self.assertRaises(ValueError):engine.Job.open(value)
 def test_progress_is_monotonic(self):
  j=engine.Job.create(self.source,texture='none');j.emit('step',.5,15,30);value=j.state['percent'];j.emit('load');self.assertEqual(j.state['percent'],value);self.assertTrue(j.state['indeterminate']);j.emit('finish',1);self.assertEqual(j.state['percent'],85)
 def test_glb_budget_is_measured(self):
  p=self.root/'mesh.glb';glb(p,9999);self.assertEqual(engine.glb_stats(p)['triangles'],9999)
  p.write_bytes(b'bad');
  with self.assertRaises((ValueError,struct.error)):engine.glb_stats(p)
 def test_one_job_lock(self):
  with engine.machine_lock():
   with self.assertRaises(RuntimeError):
    with engine.machine_lock():pass
 def test_worker_failure_and_log(self):
  j=engine.Job.create(self.source,texture='none')
  with self.assertRaises(RuntimeError):j.command([sys.executable,'-c','print("failure detail");raise SystemExit(7)'])
  self.assertIn('failure detail',(j.path/'console.log').read_text())
 def test_real_process_cancellation(self):
  j=engine.Job.create(self.source,texture='none');errors=[]
  def run():
   try:j.command([sys.executable,'-c','import time;print("ready",flush=True);time.sleep(60)'])
   except InterruptedError:errors.append('cancelled')
  t=threading.Thread(target=run);t.start()
  for _ in range(100):
   if j.process is not None:break
   time.sleep(.01)
  j.cancel();t.join(4);self.assertFalse(t.is_alive());self.assertEqual(errors,['cancelled'])
 def test_network_guard(self):
  import subprocess
  script=Path(__file__).resolve().parents[1]/'workers'
  result=subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);import common;import socket;socket.create_connection(("example.com",443))',str(script)],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('disabled during local inference',result.stderr)
 def test_stage_resume_and_manifest(self):
  j=engine.Job.create(self.source,texture='none');calls=[]
  def worker(name,env):
   calls.append(name)
   if name=='hunyuan':(j.path/'hunyuan').mkdir();glb(j.path/'hunyuan/raw.glb',20000)
  def command(args):
   if 'blender_reduce.py' in str(args):glb(j.path/'model.glb')
   else:
    (j.path/'preview.png').write_bytes(b'preview');(j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'fast':{'ready':True}}}),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):
   j.run();self.assertEqual(j.state['status'],'complete');self.assertEqual(j.state['result']['triangles'],10000)
   j.run();self.assertEqual(calls.count('hunyuan'),1)
 def test_production_final_target_does_not_change_intermediate(self):
  j=engine.Job.create(self.source,'production',20000,texture='none');commands=[]
  def worker(name,env):
   if name=='idol':
    (j.path/'idol').mkdir()
    for f in ['gaussians.npz','camera.json','splat.ply']:(j.path/'idol'/f).write_bytes(b'fixture')
   if name=='surface':(j.path/'surface').mkdir();glb(j.path/'surface/raw.glb',374260)
   if name=='hi3d':
    glb(j.path/'model.glb',20000);(j.path/'hi3d').mkdir();glb(j.path/'hi3d/extracted-raw.glb',100000)
  def command(args):
   commands.append(args)
   if 'blender_reduce.py' in str(args):
    self.assertEqual(args[-1],'10000');glb(j.path/'intermediate-10k.glb')
   else:
    (j.path/'preview.png').write_bytes(b'preview');(j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'production':{'ready':True}}}),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):
   j.run();self.assertEqual(j.state['status'],'complete');self.assertEqual(j.state['result']['triangles'],20000)
 def textured_run(self,target=7500,exported=7499,textured=True):
  j=engine.Job.create(self.source,'production-textured',target);calls=[]
  def worker(name,env):
   calls.append(name)
   if name=='idol':
    (j.path/'idol').mkdir()
    for f in ['gaussians.npz','camera.json','splat.ply']:(j.path/'idol'/f).write_bytes(b'fixture')
   if name=='gaustudio':
    folder=j.path/'gaustudio/results/gaustudio';folder.mkdir(parents=True)
    for f in ['mesh-uv.npz','basecolor.png','raw-mesh.ply','runtime.json']:(folder/f).write_bytes(b'fixture')
    (j.path/'gaustudio/manifest.json').write_text('{}')
  def command(args):
   if 'blender_textured.py' in str(args):
    calls.append('texture_reduce');self.assertEqual(json.loads((j.path/'config.json').read_text())['triangles'],target)
    glb(j.path/'model.glb',exported,textured)
    for f in ['model.blend','basecolor.png','model-reduction.json']:(j.path/f).write_bytes(b'fixture')
   else:
    calls.append('review');(j.path/'preview.png').write_bytes(b'preview');(j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'production-textured':{'ready':True}}}),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):
   j.run()
  return j,calls
 def test_textured_route_uses_final_budget_and_keeps_texture_artifacts(self):
  j,calls=self.textured_run()
  self.assertEqual(j.state['status'],'complete');self.assertEqual(calls,['prepare','idol','gaustudio','texture_reduce','review'])
  self.assertEqual(j.state['result']['triangles'],7499);self.assertEqual(j.state['result']['preview_style'],'textured')
  self.assertTrue(j.state['result']['textured']);self.assertNotIn('hi3d',j.state['result']['weights'])
  saved=json.loads((j.path/'texture_reduce.complete.json').read_text())
  self.assertEqual(set(saved),{'model.glb','model.blend','basecolor.png','model-reduction.json'})
 def test_textured_route_rejects_over_budget_export(self):
  j,_=self.textured_run(exported=7501);self.assertEqual(j.state['status'],'failed');self.assertIn('exceeds',j.state['message'])
 def test_textured_route_rejects_untextured_export(self):
  j,_=self.textured_run(textured=False);self.assertEqual(j.state['status'],'failed');self.assertIn('texture',j.state['message'])
 def test_nested_worker_changes_invalidate_checkpoints(self):
  root=self.root/'app';(root/'workers/support').mkdir(parents=True);(root/'weights.json').write_text('{}')
  script=root/'workers/support/tool.py';script.write_text('before')
  with patch.object(engine,'ROOT',root):
   a=engine.fingerprint();script.write_text('after');self.assertNotEqual(a,engine.fingerprint())
 def test_tqdm_mixed_progress_events(self):
  j=engine.Job.create(self.source,texture='none')
  j.command([sys.executable,'-c','print(\'Sampling: 10% GLGMESH_EVENT {"message":"sample", "fraction":0.5,"step":5,"total":10}\')'])
  self.assertEqual(j.state['step'],5);self.assertEqual(j.state['percent'],42.5)
 def test_resume_refuses_code_change(self):
  j=engine.Job.create(self.source,texture='none')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'fast':{'ready':True}}}),patch.object(engine,'fingerprint',return_value='changed'):
   j.run();self.assertEqual(j.state['status'],'failed');self.assertIn('code changed',j.state['message'])
if __name__=='__main__':unittest.main()
