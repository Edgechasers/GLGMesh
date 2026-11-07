"""Experimental CPU surface proxy from IDOL Gaussians, not an official IDOL mesh decoder."""
import sys,json,time,math,os
from pathlib import Path
import numpy as np
from numba import njit
from scipy.ndimage import gaussian_filter,map_coordinates
from skimage.measure import marching_cubes
import trimesh
from common import *
job,cfg,_=context();mode='sum';resolution=256;levels=[.1];source='idol'
out=job/'idol';start=time.time();d=np.load(out/'gaussians.npz')
event('Accumulating Gaussian density on a 256-voxel grid',.02)
xyz=d['xyz'];alpha=d['opacity'].ravel();keep=alpha>=.01
xyz=xyz[keep].astype(np.float64);alpha=alpha[keep];scales=d['scaling'][keep].astype(np.float64)
q=d['rotation'][keep].astype(np.float64);q/=np.linalg.norm(q,axis=1)[:,None];w,x,y,z=q.T
R=np.empty((len(q),3,3));R[:,0,0]=1-2*(y*y+z*z);R[:,0,1]=2*(x*y-w*z);R[:,0,2]=2*(x*z+w*y);R[:,1,0]=2*(x*y+w*z);R[:,1,1]=1-2*(x*x+z*z);R[:,1,2]=2*(y*z-w*x);R[:,2,0]=2*(x*z-w*y);R[:,2,1]=2*(y*z+w*x);R[:,2,2]=1-2*(x*x+y*y)
cov=(R*scales[:,None,:]**2)@R.transpose(0,2,1)
colors=np.clip(.5+.28209479177387814*d['features_dc'][keep,0,:],0,1)
lo=xyz.min(0)-.04;hi=xyz.max(0)+.04
spacing=float((hi-lo).max()/(resolution-1));shape=np.ceil((hi-lo)/spacing).astype(int)+1
# Half-voxel broadening makes subvoxel Gaussian splats sampleable on the field.
cov[:,np.arange(3),np.arange(3)]+=(spacing*.5)**2
inverse=np.linalg.inv(cov);radii=3*np.sqrt(np.diagonal(cov,axis1=1,axis2=2));centers=(xyz-lo)/spacing
@njit
def accumulate(centers,radii,inverse,alpha,colors,spacing,shape):
 field=np.zeros((shape[0],shape[1],shape[2],5),np.float32)
 for n in range(len(centers)):
  c=centers[n];rad=radii[n]/spacing;A=inverse[n]
  low=np.maximum(0,np.floor(c-rad).astype(np.int64));high=np.minimum(shape,np.ceil(c+rad).astype(np.int64)+1)
  for i in range(low[0],high[0]):
   dx=(i-c[0])*spacing
   for j in range(low[1],high[1]):
    dy=(j-c[1])*spacing
    for k in range(low[2],high[2]):
     dz=(k-c[2])*spacing
     power=-.5*(A[0,0]*dx*dx+A[1,1]*dy*dy+A[2,2]*dz*dz+2*A[0,1]*dx*dy+2*A[0,2]*dx*dz+2*A[1,2]*dy*dz)
     if power < -4.5:continue
     value=alpha[n]*math.exp(power);field[i,j,k,0]+=value
     field[i,j,k,4]=max(field[i,j,k,4],value)
     for ch in range(3):field[i,j,k,ch+1]+=value*colors[n,ch]
 return field
print('ACCUMULATE',len(xyz),'grid',shape,'memory_MiB',np.prod(shape)*20/1024**2,flush=True)
field=accumulate(centers,radii,inverse,alpha,colors,spacing,shape)
for c in range(5):field[:,:,:,c]=gaussian_filter(field[:,:,:,c],.5)
event('Extracting surface with marching cubes',.75)
cam=json.loads((out/'camera.json').read_text());turn=trimesh.transformations.rotation_matrix(cam['yaw']-math.pi,[0,0,1]);up=trimesh.transformations.rotation_matrix(-math.pi/2,[1,0,0]);transform=up@turn
for level in levels:
 target=stage_dir(job,'surface')
 v,f,normals,_=marching_cubes(field[:,:,:,4 if mode=='max' else 0],level=level,spacing=(spacing,spacing,spacing),gradient_direction='descent',allow_degenerate=False)
 coords=(v/spacing).T;density=map_coordinates(field[:,:,:,0],coords,order=1,mode='nearest')
 rgb=np.stack([map_coordinates(field[:,:,:,c],coords,order=1,mode='nearest')/np.maximum(density,1e-8) for c in range(1,4)],axis=-1)
 mesh=trimesh.Trimesh(vertices=v+lo,faces=f,vertex_colors=np.uint8(np.clip(np.c_[rgb,np.ones(len(v))],0,1)*255),process=False)
 # skimage descent winding points towards higher scalar values; invert for outward normals.
 mesh.invert();mesh.apply_transform(transform)
 # The splat preview stores display-space RGB. glTF vertex color multipliers are linear.
 linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
 mesh.vertex_attributes['_LINEAR_COLOR']=np.c_[linear,np.ones(len(v))].astype(np.float32)
 def materialize(tree,unlit):
  material={'name':'Baked splat vertex colors','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1},'doubleSided':False}
  if unlit:
   material['extensions']={'KHR_materials_unlit':{}};tree['extensionsUsed']=list(set(tree.get('extensionsUsed',[]))|{'KHR_materials_unlit'})
  tree['materials']=[material]
  for obj in tree['meshes']:
   for prim in obj['primitives']:
    prim['attributes']['COLOR_0']=prim['attributes'].pop('_LINEAR_COLOR');prim['material']=0
 for unlit,filename in [(False,'raw.glb')]:
  binary=trimesh.exchange.gltf.export_glb(mesh.scene(),include_normals=True,tree_postprocessor=lambda tree:materialize(tree,unlit))
  (target/filename).write_bytes(binary)
 stats={'source':source,'type':'Experimental Gaussian-derived surface proxy; not native IDOL mesh output','method':('Maximum Gaussian opacity' if mode=='max' else 'Opacity-weighted anisotropic Gaussian sum')+', opacity >= 0.01, 3-sigma support, covariance broadened by half a voxel, 0.5-voxel field smoothing, marching cubes, field-weighted vertex colors','resolution':resolution,'grid_shape':shape.tolist(),'voxel_spacing':spacing,'field_mode':mode,'density_threshold':level,'vertices':len(v),'triangles':len(f),'bounds_padding':.04,'generation_seconds':time.time()-start,'orientation':'Native Z-up yaw aligned to predicted image camera, then rotated to glTF Y-up','textures':'Float32 linear vertex colors converted from splat display RGB; lit GLB uses roughness 1 / metallic 0; no UV atlas','all_vertex_positions_finite':bool(np.isfinite(mesh.vertices).all()),'is_watertight':bool(mesh.is_watertight),'signed_volume':float(mesh.volume)}
 (target/'conversion.json').write_text(json.dumps(stats,indent=2));(target/'raw-inventory.json').write_text(json.dumps(stats,indent=2));print('EXPORTED',target.name,stats,flush=True)

event('Gaussian-derived mesh saved',1)
