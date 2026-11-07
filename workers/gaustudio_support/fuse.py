import local_env
import json,time
import numpy as np
import open3d as o3d
from render_common import matrices
ROOT=local_env.ROOT
start=time.monotonic();cameras=json.loads((ROOT/'inputs/cameras.json').read_text())
volume=o3d.pipelines.integration.ScalableTSDFVolume(voxel_length=.0015,sdf_trunc=.006,
    color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8)
for i,c in enumerate(cameras):
    with np.load(ROOT/'inputs/rendered'/(c['img_name']+'.npz')) as data:
        rgb=data['rgb'];depth=data['depth'].copy()
        depth[(data['alpha']<.5)|~np.isfinite(depth)|(depth<.1)|(depth>8)]=0
    H,W=depth.shape;_,_,K,V=matrices(c);K=K.numpy();V=V.numpy().astype(float)
    intrinsic=o3d.camera.PinholeCameraIntrinsic(W,H,K[0,0],K[1,1],K[0,2],K[1,2])
    rgbd=o3d.geometry.RGBDImage.create_from_color_and_depth(o3d.geometry.Image(np.ascontiguousarray(rgb)),
        o3d.geometry.Image(np.ascontiguousarray(depth)),depth_scale=1.,depth_trunc=8.,convert_rgb_to_intensity=False)
    volume.integrate(rgbd,intrinsic,V)
mesh=volume.extract_triangle_mesh();mesh.compute_vertex_normals()
assert len(mesh.triangles)>0,'TSDF reconstruction is empty'
out=ROOT/'results/gaustudio';out.mkdir(parents=True,exist_ok=True)
assert o3d.io.write_triangle_mesh(str(out/'raw-mesh.ply'),mesh)
(out/'runtime.json').write_text(json.dumps(dict(views=len(cameras),voxel=.0015,sdf_trunc=.006,
    seconds=time.monotonic()-start,triangles=len(mesh.triangles),geometry_source='Median splat depth',
    local_adaptation=True,replacements='Metal rasterizer; Open3D CPU TSDF replaces VDBFusion'),indent=2))
