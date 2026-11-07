import argparse,json,sys
from .config import MODES

def main():
 p=argparse.ArgumentParser(prog='glgmesh',description='Generate textured low-poly meshes from reference images locally.')
 sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('setup',help='Install local runtimes and download weights');s.add_argument('mode',choices=[*MODES,'all']);s.add_argument('--texture',choices=['auto','none','rgb','mv'],default='auto')
 sub.add_parser('doctor',help='Check local installation')
 s=sub.add_parser('ui',help='Start the local UI');s.add_argument('--port',type=int,default=8766);s.add_argument('--no-open',action='store_true')
 s=sub.add_parser('run',help='Generate a mesh locally');s.add_argument('image');s.add_argument('--mode',choices=MODES,default='fast');s.add_argument('--texture',choices=['auto','none','rgb','mv'],default='auto');s.add_argument('--triangles',type=int);s.add_argument('--seed',type=int,default=42);s.add_argument('--refiner-seed',type=int,default=0);s.add_argument('--idol-steps',type=int,help='Production IDOL sampling steps: 50–400 (default 50; about 2 minutes per step)');s.add_argument('--json',action='store_true',help='JSON events instead of console progress')
 s=sub.add_parser('texture',help='Texture an existing completed Prototype, Medium or Production V1 job');s.add_argument('job');s.add_argument('--json',action='store_true')
 s=sub.add_parser('resample',help='Resample a Production result from its saved dense source');s.add_argument('job');s.add_argument('--triangles',type=int,required=True);s.add_argument('--json',action='store_true')
 s=sub.add_parser('resume',help='Resume a failed or cancelled job');s.add_argument('job');s.add_argument('--json',action='store_true')
 a=p.parse_args()
 try:
  if a.command=='setup':
   from .setup import setup
   from .engine import machine_lock
   with machine_lock():setup(a.mode,a.texture)
  elif a.command=='doctor':
   from .engine import doctor
   print(json.dumps(doctor(),indent=2))
  elif a.command=='ui':
   from .server import serve
   serve(a.port,not a.no_open)
  else:
   from .engine import Job,console
   job=Job.create(a.image,a.mode,a.triangles,a.seed,a.refiner_seed,a.texture,a.idol_steps) if a.command=='run' else (Job.texture_existing(a.job) if a.command=='texture' else (Job.resample_existing(a.job,a.triangles) if a.command=='resample' else Job.open(a.job)))
   job.listener=lambda event:console(event,a.json)
   job.run()
   if not a.json:
    print(('Output: '+str(job.path/'model.glb')) if job.state['status']=='complete' else ('Log: '+str(job.path/'console.log')))
   if job.state['status']!='complete':sys.exit(1)
 except KeyboardInterrupt:sys.exit(130)
 except Exception as e:print(f'GLGMesh: {e}',file=sys.stderr);sys.exit(1)
