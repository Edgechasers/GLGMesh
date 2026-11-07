import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh import engine
from glgmesh.config import settings,stages
import test_engine
from test_engine import glb

class PaintTests(unittest.TestCase):
 setUp=test_engine.RunnerTests.setUp
 tearDown=test_engine.RunnerTests.tearDown
 def test_optional_stage_order_and_mode_validation(self):
  for mode in ['fast','medium']:
   self.assertEqual([s[0] for s in stages(settings(mode,texture='rgb'))],['hunyuan','reduce','paint','review'])
   self.assertEqual([s[0] for s in stages(settings(mode,texture='none'))],['hunyuan','reduce','review'])
  for mode in ['high','production','production-textured']:
   with self.assertRaises(ValueError):settings(mode,texture='rgb')
  with self.assertRaises(ValueError):settings('fast',texture='unknown')
 def test_rgb_pipeline_keeps_reduction_checkpoint_valid(self):
  j=engine.Job.create(self.source,texture='rgb');calls=[]
  def worker(name,env):
   calls.append(name)
   if name=='hunyuan':(j.path/'hunyuan').mkdir();glb(j.path/'hunyuan/raw.glb',20000)
   if name=='paint':
    self.assertTrue((j.path/'untextured.glb').exists());glb(j.path/'model.glb',10000,True)
    (j.path/'paint').mkdir();(j.path/'paint/metrics.json').write_text('{}');(j.path/'paint/views.png').write_bytes(b'views');(j.path/'basecolor.png').write_bytes(b'tex')
  def command(args):
   if 'blender_reduce.py' in str(args):glb(j.path/'untextured.glb')
   else:(j.path/'preview.png').write_bytes(b'preview');(j.path/'qa.json').write_text('{}');(j.path/'model.blend').write_bytes(b'blend')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',return_value={'modes':{'fast':{'ready':True}}}),patch.object(engine,'paint_ready',return_value=True),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):j.run()
  self.assertEqual(j.state['status'],'complete');self.assertTrue(j.state['result']['textured'])
  saved=json.loads((j.path/'reduce.complete.json').read_text());self.assertEqual(saved,{'untextured.glb':engine.digest(j.path/'untextured.glb')})
 def test_texture_existing_preserves_source_and_rejects_changed_mesh(self):
  old=engine.Job.create(self.source,texture='none');glb(old.path/'model.glb');(old.path/'input.png').write_bytes(b'prepared');engine.atomic(old.path/'result.json',engine.glb_stats(old.path/'model.glb'));old.state['status']='complete';engine.atomic(old.path/'status.json',old.state)
  new=engine.Job.texture_existing(old.path.name)
  self.assertNotEqual(new.path,old.path);self.assertEqual(new.cfg['source_job'],old.path.name)
  self.assertEqual(engine.digest(new.path/'source-mesh.glb'),engine.digest(old.path/'model.glb'))
  self.assertEqual([s[0] for s in stages(new.cfg)],['paint','review'])
  glb(old.path/'model.glb',9000)
  with self.assertRaises(ValueError):engine.Job.texture_existing(old.path.name)
