import local_env
import argparse,json,time
import numpy as np
import open3d as o3d
import xatlas
ROOT=local_env.ROOT
ap=argparse.ArgumentParser();ap.add_argument('method');ap.add_argument('--triangles',type=int,default=600000);args=ap.parse_args()
folder=ROOT/'results'/args.method;start=time.monotonic()
rawmesh=o3d.io.read_triangle_mesh(str(folder/'raw-mesh.ply'))
raw=dict(vertices=len(rawmesh.vertices),triangles=len(rawmesh.triangles))
mesh=rawmesh
labels,counts,areas=mesh.cluster_connected_triangles();counts=np.asarray(counts)
mesh.remove_triangles_by_mask(counts[np.asarray(labels)]<50)
mesh.remove_unreferenced_vertices();mesh.remove_duplicated_vertices();mesh.remove_duplicated_triangles();mesh.remove_degenerate_triangles()
mesh.remove_non_manifold_edges()
if len(mesh.triangles)>args.triangles:mesh=mesh.simplify_quadric_decimation(args.triangles)
mesh.remove_degenerate_triangles();mesh.remove_duplicated_triangles();mesh.remove_non_manifold_edges();mesh.remove_unreferenced_vertices()
mesh.compute_vertex_normals()
o3d.io.write_triangle_mesh(str(folder/'comparison-mesh.ply'),mesh)
print('CLEANED',len(mesh.vertices),len(mesh.triangles),time.monotonic()-start,flush=True)
v=np.asarray(mesh.vertices).astype(np.float32);f=np.asarray(mesh.triangles).astype(np.uint32)
atlas=xatlas.Atlas()
# Prepartition only UV charts; the geometric vertices and faces remain identical.
# Bounded chart groups avoid quadratic growth on dense reconstructed surfaces.
center=v[f].mean(1);grid=np.minimum(3,((center-v.min(0))/np.maximum(np.ptp(v,axis=0),1e-6)*4).astype(int))
mesh.compute_triangle_normals();norm=np.asarray(mesh.triangle_normals);axis=np.argmax(np.abs(norm),axis=1);side=norm[np.arange(len(f)),axis]>0
group=((grid[:,0]*4+grid[:,1])*4+grid[:,2])*6+axis*2+side
maps=[]
for key in np.unique(group):
    sub=f[group==key];ids,inverse=np.unique(sub,return_inverse=True)
    atlas.add_mesh(v[ids],inverse.reshape(-1,3).astype(np.uint32));maps.append(ids)
chart=xatlas.ChartOptions();chart.max_iterations=1
pack=xatlas.PackOptions();pack.resolution=4096;pack.padding=4;pack.bilinear=True
atlas.generate(chart,pack)
assert atlas.atlas_count==1, f'Expected one texture atlas, got {atlas.atlas_count}'
allmap=[];allf=[];alluv=[];offset=0
for i,ids in enumerate(maps):
    vmapping,indices,uv=atlas[i];allmap.append(ids[vmapping]);allf.append(indices+offset);alluv.append(uv);offset+=len(vmapping)
vmapping=np.concatenate(allmap);indices=np.concatenate(allf);uv=np.concatenate(alluv)
np.savez_compressed(folder/'mesh-uv.npz',vertices=v[vmapping],triangles=indices,uv=uv,
    normals=np.asarray(mesh.vertex_normals,dtype=np.float32)[vmapping],colors=np.asarray(mesh.vertex_colors,dtype=np.float32)[vmapping],
    original_vertex=vmapping)
report=dict(raw=raw,comparison=dict(vertices=len(v),triangles=len(f),uv_vertices=len(vmapping)),
    cleanup='Removed islands under 50 triangles, duplicate/degenerate triangles and non-manifold edges; QEM capped at requested intermediate budget.',
    uv=dict(tool='xatlas',resolution=4096,padding=4,charts=atlas.chart_count,utilization=atlas.utilization,atlas_count=atlas.atlas_count,packed_size=[atlas.width,atlas.height]),
    seconds=time.monotonic()-start)
(folder/'preparation.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
