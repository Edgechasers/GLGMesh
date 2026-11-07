import json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from glgmesh.server import Handler
from glgmesh import server as appserver
from glgmesh import engine
from http.server import ThreadingHTTPServer
class ServerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
 def test_status_and_csp(self):
  with urllib.request.urlopen(self.url+'/api/state') as r:
   d=json.load(r);self.assertEqual(len(d['modes']),5);self.assertEqual(d['modes']['production-textured']['minutes'],120);self.assertTrue(d['token']);self.assertIn("connect-src 'self'",r.headers['Content-Security-Policy'])
 def test_foreign_host(self):
  req=urllib.request.Request(self.url,headers={'Host':'evil.test'})
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
 def test_post_requires_token(self):
  req=urllib.request.Request(self.url+'/api/cancel',data=b'{}',headers={'Content-Type':'application/json'})
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
 def test_resample_requires_token_and_rejects_foreign_origin(self):
  for headers in [{},{'X-GLGMesh-Token':appserver.TOKEN,'Origin':'https://evil.test'}]:
   request=urllib.request.Request(self.url+'/api/resample',data=b'{"id":"anything","triangles":5000}',headers={'Content-Type':'application/json',**headers})
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
   self.assertEqual(e.exception.code,403)
 def test_resample_validation_error_is_reported(self):
  request=urllib.request.Request(self.url+'/api/resample',data=b'{"id":"missing","triangles":5000}',headers={'Content-Type':'application/json','X-GLGMesh-Token':appserver.TOKEN})
  with patch.object(appserver,'ACTIVE',None),patch.object(appserver,'doctor',return_value={'busy':False}),patch.object(appserver,'history',return_value=[]),patch.object(appserver.Job,'resample_existing',side_effect=ValueError('Saved intermediate files are missing.')):
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
   self.assertEqual(e.exception.code,400);self.assertIn('Saved intermediate',json.load(e.exception)['error'])
 def test_traversal_and_runtime_not_served(self):
  for p in ['/../README.md','/runtime/weights.json','/runs/../../README.md','/runs/invalid/config.json']:
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.url+p)
   self.assertEqual(e.exception.code,404)
 def test_run_saves_steps_for_both_production_pipelines(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(appserver,'ACTIVE',None),patch.object(appserver,'RUNTIME',root),patch.object(engine,'RUNS',root/'runs'),patch.object(appserver,'history',return_value=[]),patch.object(appserver,'doctor',return_value={'busy':False,'modes':{m:{'ready':True} for m in ['production','production-textured']}}),patch.object(appserver.Job,'run'):
    for mode in ['production','production-textured']:
     for count in [100,200,400,49,401,True,100.5,'200']:
      appserver.ACTIVE=None
      request=urllib.request.Request(self.url+'/api/run',data=json.dumps({'mode':mode,'image':'aW1hZ2U=','idol_steps':count}).encode(),headers={'Content-Type':'application/json','X-GLGMesh-Token':appserver.TOKEN})
      if type(count) is int and 50<=count<=400:
       with urllib.request.urlopen(request) as response:ident=json.load(response)['id']
       self.assertEqual(engine.Job.open(ident).cfg['idol_steps'],count)
      else:
       with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
       self.assertEqual(e.exception.code,400);self.assertIn('IDOL steps',json.load(e.exception)['error'])
if __name__=='__main__':unittest.main()
