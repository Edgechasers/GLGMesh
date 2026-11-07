"""The Bailiff-tested GauStudio adaptation, parameterized for isolated GLGMesh jobs."""
import os,sys,subprocess,json,time
from common import context,event,stage_dir
from pathlib import Path
job,cfg,_=context();root=stage_dir(job,'gaustudio');support=Path(__file__).parent/'gaustudio_support'
env={**os.environ,'GLGMESH_GAUS_ROOT':str(root)};start=time.monotonic()
steps=[('prepare_inputs.py',[],'Preparing calibrated views',0),
       ('render_common.py',[],'Rendering 98 splat views and median depths',.05),
       ('fuse.py',[],'Fusing median depths into a mesh',.35),
       ('prepare_textured_mesh.py',['gaustudio','--triangles',str(max(600000,cfg['triangles']))],'Preparing dense UV mesh',.5),
       ('project_texture.py',['gaustudio'],'Projecting original splat appearance into a 4K texture',.75)]
for script,args,label,fraction in steps:
    event(label,fraction)
    subprocess.run([sys.executable,str(support/script),*args],env=env,check=True)
path=root/'results/gaustudio/runtime.json';data=json.loads(path.read_text())
data['total_stage_seconds']=time.monotonic()-start;path.write_text(json.dumps(data,indent=2))
event('Textured GauStudio mesh ready',1)
