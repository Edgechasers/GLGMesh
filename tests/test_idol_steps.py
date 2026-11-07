import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workers'))
from glgmesh import engine
from glgmesh.config import settings,stages
from idol_checkpoint import check_schedule
import test_engine
import test_resample

class IdolStepsTests(unittest.TestCase):
 setUp=test_engine.RunnerTests.setUp
 tearDown=test_engine.RunnerTests.tearDown
 def test_defaults_bounds_and_invalid_values(self):
  for mode in ['production','production-textured']:
   self.assertEqual(settings(mode)['idol_steps'],50)
   for steps in [50,100,200,400]:self.assertEqual(settings(mode,idol_steps=steps)['idol_steps'],steps)
   for steps in [0,49,401,True,100.5,'100']:
    with self.assertRaises(ValueError):settings(mode,idol_steps=steps)
  for mode in ['fast','medium','high']:
   self.assertNotIn('idol_steps',settings(mode))
   with self.assertRaises(ValueError):settings(mode,idol_steps=100)
 def test_saved_setting_reopens_and_drives_stage_labels(self):
  for mode in ['production','production-textured']:
   job=engine.Job.create(self.source,mode,idol_steps=200)
   reopened=engine.Job.open(job.path.name)
   self.assertEqual(reopened.cfg['idol_steps'],200)
   self.assertEqual(reopened.state['stages'][0]['name'],'IDOL · 200 sampling steps')
   self.assertEqual(stages(reopened.cfg)[0][1],'IDOL · 200 sampling steps')
   del reopened.cfg['idol_steps']
   self.assertEqual(stages(reopened.cfg)[0][1],'IDOL · 50 sampling steps')
 def test_resample_keeps_original_sampling_setting(self):
  for mode in ['production','production-textured']:
   parent=test_resample.ResampleTests.source_job(self,mode)
   parent.cfg['idol_steps']=200;engine.atomic(parent.path/'config.json',parent.cfg)
   child=engine.Job.resample_existing(parent.path.name,5000)
   self.assertEqual(child.cfg['idol_steps'],200)
   self.assertNotIn('idol',[s[0] for s in stages(child.cfg)])
 def test_checkpoint_rejects_changed_schedule_and_allows_matching_resume(self):
  for filename in ['idol-progress.pt','idol-sample.pt']:
   with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder);check_schedule(folder,200)
    (folder/filename).write_bytes(b'latent')
    check_schedule(folder,200)
    with self.assertRaisesRegex(ValueError,'step count changed'):check_schedule(folder,100)
    self.assertEqual(json.loads((folder/'sampling-schedule.json').read_text())['steps'],200)
 def test_legacy_checkpoints_require_fifty_steps(self):
  (self.root/'idol-progress.pt').write_bytes(b'legacy latent')
  with self.assertRaises(ValueError):check_schedule(self.root,100)
  check_schedule(self.root,50)

if __name__=='__main__':unittest.main()
