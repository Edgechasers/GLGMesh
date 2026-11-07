"""Blender Collapse reduction, always measured after triangulation."""
import bpy,sys,json,math,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from common import event
source,dest,target=sys.argv[sys.argv.index('--')+1:];target=int(target);dest=Path(dest)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=source)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not objects:raise ValueError('No mesh in input')
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
if len(objects)>1:bpy.ops.object.join()
obj=bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
obj.data.calc_loop_triangles();original=len(obj.data.loop_triangles)
mod=obj.modifiers.new('GLGMesh triangle budget','DECIMATE');mod.decimate_type='COLLAPSE';mod.use_collapse_triangulate=True;mod.use_symmetry=False
lo,hi=0.,1.;ratio=min(1.,target/original);best=None;best_ratio=None
for attempt in range(22):
 mod.ratio=ratio;bpy.context.view_layer.update()
 evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());me.calc_loop_triangles();count=len(me.loop_triangles)
 event(f'Blender reduction · {count:,} triangles',min(.9,(attempt+1)/22),attempt+1,22)
 if 0<count<=target and (best is None or count>best[0]):
  if best:bpy.data.meshes.remove(best[1])
  best=(count,me);best_ratio=ratio
 else:bpy.data.meshes.remove(me)
 if target-1<=count<=target or original<=target:break
 if count>target:hi=ratio
 else:lo=ratio
 ratio=(lo+hi)/2
if best is None:raise RuntimeError('Blender cannot meet this triangle budget on this topology. Source mesh retained; no automatic destructive reconstruction was applied.')
obj.modifiers.clear();obj.data=best[1];obj.name='GLGMesh'
bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_animations=False,export_yup=True)
with open(dest,'rb') as stream:
 stream.read(12);size,kind=struct.unpack('<II',stream.read(8));document=json.loads(stream.read(size))
exported=sum(document['accessors'][primitive['indices']]['count']//3 for mesh in document['meshes'] for primitive in mesh['primitives'])
if not 0<exported<=target:raise RuntimeError('Exported GLB exceeds the triangle budget or is empty')
(dest.parent/(dest.stem+'-reduction.json')).write_text(json.dumps({'source_triangles':original,'target_triangles':target,'evaluated_triangles':best[0],'exported_triangles':exported,'ratio':best_ratio,'method':'Blender Collapse, triangulated, no symmetry','blender':bpy.app.version_string},indent=2))
event(f'Blender mesh exported · {exported:,} triangles (target {target:,})',1)
