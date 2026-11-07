"""Reduce the dense GauStudio mesh to the requested budget and rebake appearance."""
import bpy,bmesh,sys,json,time,struct
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from common import event
import bake_maps

job=Path(sys.argv[-1]).resolve();cfg=json.loads((job/'config.json').read_text())
folder=job/'gaustudio/results/gaustudio';target=int(cfg['triangles']);start=time.monotonic()
bpy.ops.wm.read_factory_settings(use_empty=True)
d=np.load(folder/'mesh-uv.npz');M=np.array(json.loads((job/'gaustudio/manifest.json').read_text())['native_to_ply'])
uvfaces=d['triangles'].astype(np.int32);uv=d['uv']
_,first,inverse=np.unique(d['original_vertex'],return_index=True,return_inverse=True)
v=d['vertices'][first]@M;f=inverse[uvfaces].astype(np.int32)
mesh=bpy.data.meshes.new('Dense_GauStudio');mesh.vertices.add(len(v));mesh.vertices.foreach_set('co',v.ravel())
mesh.loops.add(f.size);mesh.loops.foreach_set('vertex_index',f.ravel())
mesh.polygons.add(len(f));mesh.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*3)
mesh.polygons.foreach_set('loop_total',np.full(len(f),3,dtype=np.int32));mesh.update()
mesh.polygons.foreach_set('use_smooth',np.ones(len(f),dtype=bool))
mesh.uv_layers.new(name='UVMap').data.foreach_set('uv',uv[uvfaces.ravel()].ravel())
high=bpy.data.objects.new('Dense_GauStudio',mesh);bpy.context.collection.objects.link(high)
def appearance(name,image):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
    out=nodes.new('ShaderNodeOutputMaterial');em=nodes.new('ShaderNodeEmission');tex=nodes.new('ShaderNodeTexImage')
    tex.image=image;mat.node_tree.links.new(tex.outputs['Color'],em.inputs['Color'])
    mat.node_tree.links.new(em.outputs[0],out.inputs['Surface']);return mat
source_image=bpy.data.images.load(str(folder/'basecolor.png'));source_image.colorspace_settings.name='sRGB'
high.data.materials.append(appearance('Dense_appearance',source_image))
low=high.copy();low.data=high.data.copy();low.name='Generated_mesh';bpy.context.collection.objects.link(low)
for obj in bpy.context.scene.objects:obj.select_set(False)
low.select_set(True);bpy.context.view_layer.objects.active=low
event('Reducing mesh to the requested triangle budget',.05)
source_count=len(mesh.polygons)
if source_count>target:
    mod=low.modifiers.new('Target triangle budget','DECIMATE');mod.ratio=max(1,target-1)/source_count
    mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
bm=bmesh.new();bm.from_mesh(low.data)
bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges))
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
wire=[e for e in bm.edges if not e.link_faces]
if wire:bmesh.ops.delete(bm,geom=wire,context='EDGES')
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
bmesh.ops.triangulate(bm,faces=list(bm.faces))
# Tiny disconnected reconstruction fragments are not useful at the target budget.
unseen=set(bm.verts);parts=[]
while unseen:
    seed=unseen.pop();part={seed};stack=[seed]
    while stack:
        for edge in stack.pop().link_edges:
            for vert in edge.verts:
                if vert in unseen:unseen.remove(vert);part.add(vert);stack.append(vert)
    parts.append(part)
largest=max(parts,key=len) if parts else set()
debris=[v for part in parts if part is not largest and len({f for v in part for f in v.link_faces})<8 for v in part]
if debris:bmesh.ops.delete(bm,geom=debris,context='VERTS')
bm.to_mesh(low.data);bm.free();low.data.update();low.data.calc_loop_triangles()
count=len(low.data.loop_triangles)
if not 0<count<=target:raise RuntimeError(f'Reduction produced {count} triangles for budget {target}')
while low.data.uv_layers:low.data.uv_layers.remove(low.data.uv_layers[0])
low.data.uv_layers.new(name='UVMap')
event('Unwrapping the reduced mesh',.2)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.151917306,island_margin=.008,correct_aspect=True,scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
low.data.materials.clear();mat=bpy.data.materials.new('Bake_target');mat.use_nodes=True;low.data.materials.append(mat)
event('Baking original splat appearance into a 4K texture',.35)
bake=bake_maps.run(low=low.name,high=[high.name],maps=['emit'],res=4096,samples=16,
    margin_px=16,extrusion=.008,out=str(job),name='Generated',device='GPU')
image=bpy.data.images['T_Generated_E'];image.filepath_raw=str(job/'basecolor.png');image.file_format='PNG';image.save()
image.pack();low.data.materials.clear();low.data.materials.append(appearance('Baked_splat_appearance',image))
bpy.data.objects.remove(high,do_unlink=True)
bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
for obj in scene.objects:obj.select_set(False)
low.select_set(True);bpy.context.view_layer.objects.active=low
bpy.ops.wm.save_as_mainfile(filepath=str(job/'model.blend'))
event('Exporting textured GLB',.9)
bpy.ops.export_scene.gltf(filepath=str(job/'model.glb'),export_format='GLB',use_selection=True,
                         use_active_scene=True,export_animations=False,export_yup=True)
# Encode the baked appearance explicitly as glTF unlit, as in the validated Bailiff.
p=job/'model.glb';blob=p.read_bytes();n,_=struct.unpack('<II',blob[12:20]);doc=json.loads(blob[20:20+n])
for mat in doc['materials']:
    texture=mat.pop('emissiveTexture');mat.pop('emissiveFactor',None)
    mat['pbrMetallicRoughness']={'baseColorTexture':texture,'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1}
    mat.setdefault('extensions',{})['KHR_materials_unlit']={}
doc.setdefault('extensionsUsed',[]).append('KHR_materials_unlit')
chunk=json.dumps(doc,separators=(',',':')).encode();chunk+=b' '*((-len(chunk))%4);tail=blob[20+n:]
p.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(chunk)+len(tail))+struct.pack('<II',len(chunk),0x4e4f534a)+chunk+tail)
(job/'T_Generated_E.png').unlink(missing_ok=True)
(job/'model-reduction.json').write_text(json.dumps(dict(source_triangles=source_count,triangles=count,
    requested_triangles=target,texture_size=4096,seconds=time.monotonic()-start,bake_device=bake['device'],
    appearance='Original IDOL splat, projected to dense mesh, rebaked onto fresh low-mesh UVs',
    material='KHR_materials_unlit; baked appearance, not relightable PBR'),indent=2))
event('Reduced textured mesh saved',1)
