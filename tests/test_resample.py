import json,struct,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh import engine
from glgmesh.glb import neutral_glb
from glgmesh.config import stages
import test_engine
glb=test_engine.glb

class ResampleTests(unittest.TestCase):
 setUp=test_engine.RunnerTests.setUp
 tearDown=test_engine.RunnerTests.tearDown
 def source_job(self,mode):
  j=engine.Job.create(self.source,mode,texture='none')
  (j.path/'input.png').write_bytes(b'image')
  glb(j.path/'model.glb')
  for name in engine.RESAMPLE_INPUTS[mode]:
   p=j.path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'intermediate')
  if mode=='production-textured':(j.path/'idol/camera.json').write_text('{"yaw": 3.14}')
  result=engine.glb_stats(j.path/'model.glb');engine.atomic(j.path/'result.json',result)
  j.state.update(status='complete',result=result);engine.atomic(j.path/'status.json',j.state)
  engine.atomic(j.path/'source.complete.json',{f:engine.digest(j.path/f) for f in engine.RESAMPLE_INPUTS[mode]})
  return j
 def test_reuses_intermediates_preserves_original_and_skips_inference(self):
  for mode,stage in [('production','hi3d_reduce'),('production-textured','texture_reduce')]:
   parent=self.source_job(mode);before=(parent.path/'model.glb').read_bytes()
   child=engine.Job.resample_existing(parent.path.name,5000)
   self.assertEqual([s[0] for s in stages(child.cfg)],[stage,'review'])
   self.assertEqual(child.cfg['source_generation_job'],parent.path.name)
   self.assertFalse((child.path/'idol/splat.ply').exists())
   self.assertEqual((parent.path/'model.glb').read_bytes(),before)
   for f in engine.RESAMPLE_INPUTS[mode]:self.assertEqual((parent.path/f).read_bytes(),(child.path/f).read_bytes())
 def test_targets_can_match_or_exceed_current_count_in_both_modes(self):
  for mode in engine.RESAMPLE_INPUTS:
   parent=self.source_job(mode)
   for target in [100,10000,25000,2000000]:
    child=engine.Job.resample_existing(parent.path.name,target)
    self.assertEqual(child.cfg['triangles'],target)
    self.assertTrue(child.cfg['resample_only'])
    for f in engine.RESAMPLE_INPUTS[mode]:self.assertEqual(engine.digest(child.path/f),engine.digest(parent.path/f))
   parent.state['result']['triangles']=100
   self.assertTrue(engine.output_options(parent)['resample_available'])
 def test_missing_changed_or_invalid_inputs_refused(self):
  j=self.source_job('production')
  for target in [99,2000001,True,500.5,'500',None]:
   with self.assertRaises(ValueError):engine.Job.resample_existing(j.path.name,target)
  (j.path/'hi3d/extracted-raw.glb').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'changed'):engine.Job.resample_existing(j.path.name,5000)
  (j.path/'hi3d/extracted-raw.glb').unlink()
  self.assertFalse(engine.output_options(j)['resample_available'])
 def test_execution_only_reduces_and_reviews_without_setup(self):
  parent=self.source_job('production');j=engine.Job.resample_existing(parent.path.name,5000);calls=[]
  def worker(name,env):
   calls.append(name);self.assertEqual(name,'hi3d_reduce');glb(j.path/'model.glb',5000);(j.path/'hi3d/resample.json').write_text('{}')
  def command(args):
   calls.append('review');self.assertIn('blender_review.py',str(args));(j.path/'preview.png').write_bytes(b'preview');(j.path/'qa.json').write_text('{}')
  with patch.object(engine,'BLENDER',str(self.source)),patch.object(engine,'doctor',side_effect=AssertionError('Full setup must not run')),patch.object(j,'worker',side_effect=worker),patch.object(j,'command',side_effect=command):j.run()
  self.assertEqual(j.state['status'],'complete');self.assertEqual(calls,['hi3d_reduce','review'])
  child=engine.Job.resample_existing(j.path.name,2500)
  self.assertEqual(child.cfg['source_generation_job'],parent.path.name)

class NeutralTests(unittest.TestCase):
 def test_texture_bytes_removed_geometry_preserved(self):
  geometry=struct.pack('<9f3H',0,0,0,1,0,0,0,1,0,0,1,2);binary=b'FAKEPNG!'+geometry
  doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(binary)}],'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':8},{'buffer':0,'byteOffset':8,'byteLength':len(geometry)}],'accessors':[{'bufferView':1,'componentType':5126,'count':3,'type':'VEC3'}],'images':[{'bufferView':0,'mimeType':'image/png'}],'textures':[{'source':0}],'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}},'extensions':{'KHR_materials_unlit':{}}}],'extensionsUsed':['KHR_materials_unlit'],'meshes':[{'primitives':[{'attributes':{'POSITION':0,'COLOR_0':0},'material':0}]}]}
  payload=json.dumps(doc).encode();payload+=b' '*(-len(payload)%4);binary+=b'\0'*(-len(binary)%4)
  blob=struct.pack('<4sII',b'glTF',2,28+len(payload)+len(binary))+struct.pack('<II',len(payload),0x4e4f534a)+payload+struct.pack('<II',len(binary),0x004e4942)+binary
  output=neutral_glb(blob);n=struct.unpack_from('<I',output,12)[0];new=json.loads(output[20:20+n]);data=output[28+n:]
  self.assertNotIn('images',new);self.assertNotIn('textures',new);self.assertNotIn('FAKEPNG',str(output));self.assertNotIn('extensionsUsed',new)
  self.assertEqual(new['accessors'][0]['bufferView'],0);self.assertEqual(data[:len(geometry)],geometry)
  self.assertNotIn('COLOR_0',new['meshes'][0]['primitives'][0]['attributes'])
 def test_invalid_glb_rejected(self):
  with self.assertRaises(ValueError):neutral_glb(b'bad')

if __name__=='__main__':unittest.main()
