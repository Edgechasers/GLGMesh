"""10k export budget, applied to freshly reconstructed meshes before UV/baking."""
import json
from pathlib import Path
import numpy as np

def reduce_geometry(vertices,faces,out,method='fast',target=10000):
    v=np.asarray(vertices,dtype=np.float64);f=np.asarray(faces,dtype=np.int32)
    source_v,source_f=v,f
    report={'target_triangles':target,'raw_triangles':len(f),'method':method}
    if method=='hunyuan':
        import pymeshlab
        ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(v,f))
        if len(f)>target:
            ms.apply_filter('meshing_decimation_quadric_edge_collapse',targetfacenum=target,qualitythr=1.,preserveboundary=True,boundaryweight=3,preservenormal=True,preservetopology=True,autoclean=True)
        v=ms.current_mesh().vertex_matrix().copy();f=ms.current_mesh().face_matrix().copy()
        report['method']='Tencent FaceReducer settings: PyMeshLab quadric edge collapse, preserve boundary/normals/topology'
    if len(f)>target:
        import fast_simplification
        v,f=fast_simplification.simplify(v,f,target_count=target)
        report['final_cap']='fast_simplification quadric collapse to target_count'
    if len(f)>target:
        report['fast_simplification_stalled_at']=len(f)
        import pymeshlab
        ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(source_v,source_f))
        ms.apply_filter('meshing_decimation_quadric_edge_collapse',targetfacenum=target,qualitythr=.3,preserveboundary=False,preservenormal=False,preservetopology=False,autoclean=True)
        v=ms.current_mesh().vertex_matrix().copy();f=ms.current_mesh().face_matrix().copy()
        report['final_cap']='PyMeshLab quadric collapse from fresh raw surface; boundary/normal/topology preservation disabled'
    assert len(f)<=target and len(f)>0 and np.isfinite(v).all()
    report['output_triangles']=len(f);Path(out).write_text(json.dumps(report,indent=2))
    print('TRIANGLE_TARGET',report,flush=True)
    return np.asarray(v),np.asarray(f,dtype=np.int64)
