"""Reimport, QA report, neutral geometry review renders."""
import bpy,bmesh,sys,json,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from common import event
import qa_check
job=Path(sys.argv[-1]);bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(job/'model.glb'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
cfg=json.loads((job/'config.json').read_text()) if (job/'config.json').exists() else {}
production_textured=cfg.get('mode')=='production-textured'
textured=production_textured or cfg.get('texture') in ['rgb','mv']
# Shape-only generators can export without a material; supply a neutral review material.
mat=bpy.data.materials.new('Neutral geometry');mat.diffuse_color=(.46,.49,.52,1)
mat.use_nodes=True;bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bsdf.inputs['Base Color'].default_value=(.46,.49,.52,1);bsdf.inputs['Roughness'].default_value=.82
for o in objects:
 if not o.data.materials:o.data.materials.append(mat)
event('Checking mesh topology and materials',.1)
qa_objects=objects
if textured:
 # glTF splits vertices at UV/normal seams. Weld an analysis copy so shared
 # triangle edges are not misreported as disconnected or overlapping surfaces.
 qa_objects=[]
 for original in objects:
  copy=original.copy();copy.data=original.data.copy();copy.name=original.name+'_QA'
  bpy.context.collection.objects.link(copy);qa_objects.append(copy)
  bm=bmesh.new();bm.from_mesh(copy.data)
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
  bm.to_mesh(copy.data);bm.free();copy.data.update()
qa=qa_check.run(objects=[o.name for o in qa_objects],profile='render',uv=textured)
if textured:
 qa['scope']='Reimported GLB with coincident UV/normal seam vertices welded on temporary QA copies; exported/rendered mesh unchanged.'
 for copy in qa_objects:bpy.data.objects.remove(copy,do_unlink=True)
(job/'qa.json').write_text(json.dumps(qa,indent=2,default=str))
if cfg.get('texture') in ['rgb','mv']:
 for image in bpy.data.images:
  if image.source=='FILE':image.pack()
 bpy.ops.wm.save_as_mainfile(filepath=str(job/'model.blend'))
# A QA report is not artistic approval. Retain generated geometry for review.
if not textured:
 for o in objects:
  o.data.materials.clear();o.data.materials.append(mat)
points=[o.matrix_world@Vector(corner) for o in objects for corner in o.bound_box]
lo=Vector(tuple(min(v[k] for v in points) for k in range(3)));hi=Vector(tuple(max(v[k] for v in points) for k in range(3)));center=(lo+hi)/2;span=max(hi-lo)
scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('World');scene.world.color=(.055,.065,.08)
scene.render.resolution_x=640;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
camdata=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.type='ORTHO';camdata.ortho_scale=span*1.35
views=[('preview',.35),('front',0),('back',math.pi)]+([('clay',.35)] if textured else [])+[('wireframe',.35)]
if textured:
 import bake_maps
 scene.render.engine='CYCLES';bake_maps._set_device(scene,'GPU');scene.cycles.samples=8;scene.cycles.use_denoising=False
 yaw=float(json.loads((job/'idol/camera.json').read_text())['yaw']) if production_textured else math.pi
 if not production_textured:
  # RGB appearance review: display base color without inventing PBR maps.
  for o in objects:
   for m in o.data.materials:
    if m and m.use_nodes:
     tex=next((n for n in m.node_tree.nodes if n.type=='TEX_IMAGE'),None)
     out=next((n for n in m.node_tree.nodes if n.type=='OUTPUT_MATERIAL'),None)
     if tex and out:
      emission=m.node_tree.nodes.new('ShaderNodeEmission');m.node_tree.links.new(tex.outputs['Color'],emission.inputs['Color']);m.node_tree.links.new(emission.outputs[0],out.inputs['Surface'])
for index,(name,angle) in enumerate(views):
 offset=Vector((math.sin(yaw+angle),math.cos(yaw+angle),.12) if textured else (math.sin(angle),-math.cos(angle),.12))*span*3;cam.location=center+offset;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
 if textured and name in ['clay','wireframe']:
  scene.render.engine='BLENDER_WORKBENCH'
  for o in objects:o.data.materials.clear();o.data.materials.append(mat)
 if name=='wireframe':
  wiremat=bpy.data.materials.new('Wireframe');wiremat.diffuse_color=(.025,.03,.035,1)
  for o in objects:
   o.data.materials.append(wiremat);mod=o.modifiers.new('Wireframe preview','WIREFRAME');mod.thickness=span*.0005;mod.use_replace=False;mod.material_offset=1
 scene.render.filepath=str(job/(name+'.png'));bpy.ops.render.render(write_still=True);event('Rendering review views',(index+1)/len(views),index+1,len(views))
