import json,math,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh import engine,server
from http.server import ThreadingHTTPServer
import test_resample

class SplatTests(unittest.TestCase):
 setUp=test_resample.ResampleTests.setUp
 tearDown=test_resample.ResampleTests.tearDown
 source_job=test_resample.ResampleTests.source_job
 def add_splat(self,job):
  (job.path/'idol').mkdir(exist_ok=True)
  (job.path/'idol/splat.ply').write_bytes(b'original Gaussian PLY')
  (job.path/'idol/camera.json').write_text(json.dumps({'yaw':math.pi+.5}))
 def test_both_modes_resolve_original_source_and_camera(self):
  for mode in engine.RESAMPLE_INPUTS:
   j=self.source_job(mode);self.add_splat(j)
   options=engine.output_options(j)
   self.assertTrue(options['splat_available']);self.assertEqual(options['splat_source_job'],j.path.name);self.assertAlmostEqual(options['splat_yaw'],.5)
 def test_nested_resamples_use_original_splat_without_copying_it(self):
  parent=self.source_job('production');self.add_splat(parent)
  child=engine.Job.resample_existing(parent.path.name,5000)
  child.state['status']='complete';engine.atomic(child.path/'status.json',child.state)
  self.assertFalse((child.path/'idol/splat.ply').exists())
  self.assertEqual(engine.splat_source(child).path,parent.path)
  # Legacy source_job-only chain is supported as well.
  child.cfg.pop('source_generation_job');self.assertEqual(engine.splat_source(child).path,parent.path)
  (parent.path/'idol/splat.ply').unlink();self.assertIsNone(engine.splat_source(child))
 def test_incomplete_nonproduction_cycles_and_traversal_have_no_splat(self):
  j=self.source_job('production');self.add_splat(j)
  j.state['status']='running';self.assertIsNone(engine.splat_source(j))
  j.state['status']='complete';j.cfg['mode']='fast';self.assertIsNone(engine.splat_source(j));j.cfg['mode']='production'
  (j.path/'idol/splat.ply').unlink()
  for parent in [j.path.name,'../../outside',123]:
   j.cfg['source_generation_job']=parent;engine.atomic(j.path/'config.json',j.cfg)
   self.assertIsNone(engine.splat_source(j))
 def test_http_serves_only_the_resolved_source(self):
  parent=self.source_job('production');self.add_splat(parent)
  child=engine.Job.resample_existing(parent.path.name,5000);child.state['status']='complete';engine.atomic(child.path/'status.json',child.state)
  with patch.object(server,'RUNS',engine.RUNS.resolve()):
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
   try:
    url=f'http://127.0.0.1:{http.server_port}/runs/{child.path.name}/source-splat.ply'
    with urllib.request.urlopen(url) as r:
     self.assertEqual(r.read(),b'original Gaussian PLY');self.assertIn("worker-src 'self' blob:",r.headers['Content-Security-Policy']);self.assertNotIn("'unsafe-eval'",r.headers['Content-Security-Policy'])
    (parent.path/'idol/splat.ply').unlink()
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url)
    self.assertEqual(e.exception.code,404)
   finally:http.shutdown();http.server_close();t.join()
if __name__=='__main__':unittest.main()
