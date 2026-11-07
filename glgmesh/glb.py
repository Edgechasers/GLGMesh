"""Geometry-preserving, texture-free GLB export without loading a 3D runtime."""
import json,struct,uuid
from pathlib import Path


def neutral_glb(blob):
 if len(blob)<20 or struct.unpack_from('<4sII',blob)!=(b'glTF',2,len(blob)):raise ValueError('Invalid GLB')
 offset=12;doc=None;binary=b''
 while offset<len(blob):
  size,kind=struct.unpack_from('<II',blob,offset);offset+=8
  data=blob[offset:offset+size];offset+=size
  if kind==0x4e4f534a:doc=json.loads(data)
  elif kind==0x004e4942:binary=data
 if not doc or any('uri' in b for b in doc.get('buffers',[])):raise ValueError('Expected self-contained GLB')
 image_views={i['bufferView'] for i in doc.pop('images',[]) if 'bufferView' in i}
 doc.pop('textures',None);doc.pop('samplers',None)
 doc['materials']=[{'name':'Neutral geometry','pbrMetallicRoughness':{'baseColorFactor':[.48,.5,.48,1],'roughnessFactor':.85,'metallicFactor':0}}]
 for mesh in doc.get('meshes',[]):
  for p in mesh['primitives']:
   p['material']=0
   for key in list(p.get('attributes',{})):
    if key.startswith('COLOR_'):del p['attributes'][key]
 # These material/image extensions no longer describe any resources.
 for key in ['extensionsUsed','extensionsRequired']:
  doc[key]=[x for x in doc.get(key,[]) if not x.startswith('KHR_materials_') and x not in ['KHR_texture_transform','KHR_texture_basisu','EXT_texture_webp','EXT_texture_avif']]
  if not doc[key]:doc.pop(key,None)
 doc.get('extensions',{}).pop('KHR_materials_variants',None)
 for mesh in doc.get('meshes',[]):
  for p in mesh['primitives']:p.get('extensions',{}).pop('KHR_materials_variants',None)
 views=doc.pop('bufferViews',[]);used=set()
 def refs(value):
  if isinstance(value,dict):
   for k,v in value.items():
    if k=='bufferView':used.add(v)
    else:refs(v)
  elif isinstance(value,list):
   for v in value:refs(v)
 refs(doc)
 # Keep all non-image views, including extension data; remove image bytes themselves.
 mapping={};packed=bytearray();kept=[]
 for i,view in enumerate(views):
  if i in image_views and i not in used:continue
  if view.get('buffer',0)!=0:raise ValueError('Only single-buffer GLBs are supported')
  start=view.get('byteOffset',0);end=start+view['byteLength']
  if end>len(binary):raise ValueError('Buffer view exceeds binary data')
  packed.extend(b'\0'*((-len(packed))%4));mapping[i]=len(kept)
  kept.append({**view,'buffer':0,'byteOffset':len(packed)})
  packed.extend(binary[start:end])
 def remap(value):
  if isinstance(value,dict):
   for k,v in value.items():
    if k=='bufferView':value[k]=mapping[v]
    else:remap(v)
  elif isinstance(value,list):
   for v in value:remap(v)
 remap(doc);doc['bufferViews']=kept;doc['buffers']=[{'byteLength':len(packed)}]
 payload=json.dumps(doc,separators=(',',':')).encode();payload+=b' '*((-len(payload))%4);packed.extend(b'\0'*((-len(packed))%4))
 return struct.pack('<4sII',b'glTF',2,28+len(payload)+len(packed))+struct.pack('<II',len(payload),0x4e4f534a)+payload+struct.pack('<II',len(packed),0x004e4942)+packed


def export_neutral(source,dest):
 data=neutral_glb(Path(source).read_bytes());dest=Path(dest)
 pending=dest.with_name(dest.name+'.'+uuid.uuid4().hex+'.tmp')
 try:pending.write_bytes(data);pending.replace(dest)
 finally:pending.unlink(missing_ok=True)
 return dest
