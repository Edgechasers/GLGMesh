import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh import engine
from glgmesh.config import settings,stages,MODES
import test_engine
from test_engine import glb

class TextureRouteTests(unittest.TestCase):
 setUp=test_engine.RunnerTests.setUp
 tearDown=test_engine.RunnerTests.tearDown
 def test_default_routes_and_legacy_none(self):
  expected={'fast':['hunyuan','reduce','paint','review'], 'medium':['hunyuan','reduce','mv_adapter','mv_bake','review'],
            'production':['idol','surface','reduce','hi3d','mv_adapter','mv_bake','review']}
  for mode,plan in expected.items():
   cfg=settings(mode);self.assertEqual([s[0] for s in stages(cfg)],plan);self.assertAlmostEqual(sum(w for _,_,w in stages(cfg)),100)
   self.assertNotIn('mv_adapter',[s[0] for s in stages(settings(mode,texture='none'))])
  self.assertEqual(MODES['production']['name'],'Production V1');self.assertEqual(MODES['production-textured']['name'],'Production V2')
  for mode in ['fast','high','production-textured']:
   with self.assertRaises(ValueError):settings(mode,texture='mv')
 def test_mv_failure_resumes_without_geometry_or_view_regeneration(self):
  j=engine.Job.create(self.source,'medium');calls=[];fail=[True]
  def worker(name,env):
   calls.append(name)
   if name=='hunyuan':(j.path/'hunyuan').mkdir();glb(j.path/'hunyuan/raw.glb',20000)
   elif name=='mv_adapter':
    self.assertEqual(env,'mv');self.assertTrue((j.path/'untextured.glb').exists());(j.path/'mv').mkdir()
    for f in ['prepared.npz','cameras.npz','generation.json','views.png',*[f'view-{i}.png' for i in range(6)]]:(j.path/'mv'/f).write_bytes(b'checkpoint')
   elif name=='mv_bake':
    if fail[0]:raise RuntimeError('Bake interrupted')
    glb(j.path/'model.glb',10000,True);(j.path/'basecolor.png').write_bytes(b'texture');(j.path/'mv/metrics.json').write_text('{"seed":42}')
  def command(args):
   if 'blender_reduce.py' in str(args):glb(j.path/'untextured.glb')
   else:
    for name in ['preview.png','model.blend']:(j.path/name).write_bytes(b'review')
    (j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'medium':{'ready':True}}}),patch.object(engine,'mv_ready',return_value=True),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):
   j.run();self.assertEqual(j.state['status'],'failed');self.assertIn('interrupted',j.state['message'])
   checkpoint=engine.digest(j.path/'untextured.glb');fail[0]=False;j.run()
  self.assertEqual(j.state['status'],'complete',j.state['message']);self.assertEqual(calls.count('hunyuan'),1);self.assertEqual(calls.count('mv_adapter'),1)
  self.assertEqual(engine.digest(j.path/'untextured.glb'),checkpoint);self.assertEqual(j.state['result']['mv_adapter']['seed'],42)
  self.assertIn('sd21',j.state['result']['weights']);self.assertNotIn('hunyuan-paint',j.state['result']['weights'])
 def test_textured_production_resample_keeps_mv_and_dense_source(self):
  old=engine.Job.create(self.source,'production');glb(old.path/'model.glb',10000,True);(old.path/'input.png').write_bytes(b'prepared')
  (old.path/'hi3d').mkdir();glb(old.path/'hi3d/extracted-raw.glb',150000)
  result=engine.glb_stats(old.path/'model.glb');engine.atomic(old.path/'result.json',result);old.state.update(status='complete',result=result);engine.atomic(old.path/'status.json',old.state)
  j=engine.Job.resample_existing(old.path.name,20000)
  self.assertEqual(j.cfg['texture'],'mv');self.assertEqual([s[0] for s in stages(j.cfg)],['hi3d_reduce','mv_adapter','mv_bake','review'])
  self.assertEqual(engine.digest(j.path/'hi3d/extracted-raw.glb'),engine.digest(old.path/'hi3d/extracted-raw.glb'))
 def test_texture_existing_production_retains_resample_and_splat_parent(self):
  old=engine.Job.create(self.source,'production',texture='none');glb(old.path/'model.glb');(old.path/'input.png').write_bytes(b'prepared')
  (old.path/'hi3d').mkdir();glb(old.path/'hi3d/extracted-raw.glb',150000)
  engine.atomic(old.path/'result.json',engine.glb_stats(old.path/'model.glb'));old.state['status']='complete';engine.atomic(old.path/'status.json',old.state)
  j=engine.Job.texture_existing(old.path.name)
  self.assertEqual(j.cfg['texture'],'mv');self.assertEqual(j.cfg['source_generation_job'],old.path.name)
  self.assertEqual([s[0] for s in stages(j.cfg)],['mv_adapter','mv_bake','review'])
  self.assertTrue((j.path/'hi3d/extracted-raw.glb').is_file())

 def test_production_execution_keeps_intermediate_and_dense_checkpoints(self):
  j=engine.Job.create(self.source,'production',20000);calls=[]
  def worker(name,env):
   calls.append(name)
   if name=='prepare':(j.path/'input.png').write_bytes(b'prepared')
   elif name=='idol':
    (j.path/'idol').mkdir()
    for f in ['gaussians.npz','camera.json','splat.ply']:(j.path/'idol'/f).write_bytes(b'checkpoint')
   elif name=='surface':(j.path/'surface').mkdir();glb(j.path/'surface/raw.glb',400000)
   elif name=='hi3d':
    self.assertEqual(engine.glb_stats(j.path/'intermediate-10k.glb')['triangles'],10000)
    (j.path/'hi3d').mkdir();glb(j.path/'hi3d/extracted-raw.glb',200000);glb(j.path/'untextured.glb',20000)
   elif name=='mv_adapter':
    self.assertEqual(engine.glb_stats(j.path/'untextured.glb')['triangles'],20000);(j.path/'mv').mkdir()
    for f in ['prepared.npz','cameras.npz','generation.json','views.png',*[f'view-{i}.png' for i in range(6)]]:(j.path/'mv'/f).write_bytes(b'checkpoint')
   elif name=='mv_bake':
    glb(j.path/'model.glb',20000,True);(j.path/'basecolor.png').write_bytes(b'texture');(j.path/'mv/metrics.json').write_text('{}')
  def command(args):
   if 'blender_reduce.py' in str(args):
    self.assertEqual(args[-1],'10000');glb(j.path/'intermediate-10k.glb')
   else:
    (j.path/'preview.png').write_bytes(b'preview');(j.path/'model.blend').write_bytes(b'blend');(j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'production':{'ready':True}}}),patch.object(engine,'mv_ready',return_value=True),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):j.run()
  self.assertEqual(j.state['status'],'complete',j.state['message']);self.assertEqual(calls,['prepare','idol','surface','hi3d','mv_adapter','mv_bake'])
  saved=json.loads((j.path/'hi3d.complete.json').read_text());self.assertEqual(set(saved),{'untextured.glb','hi3d/extracted-raw.glb'})
  self.assertTrue(all(engine.digest(j.path/name)==sha for name,sha in saved.items()))
  child=engine.Job.resample_existing(j.path.name,5000);self.assertEqual(child.cfg['texture'],'mv')
