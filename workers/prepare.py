from common import *
from PIL import Image,ImageOps
job,cfg,_=context()
Image.MAX_IMAGE_PIXELS=32_000_000
with Image.open(job/'source-image') as im:
 if im.width*im.height>32_000_000:raise ValueError('Image exceeds 32 megapixels')
 im=ImageOps.exif_transpose(im).convert('RGBA')
 if im.getchannel('A').getbbox() is None:raise ValueError('Image is fully transparent')
 im.thumbnail((2048,2048),Image.Resampling.LANCZOS)
 if im.getchannel('A').getextrema()[0]==255:
  event('Removing background with local U²-Net weights')
  os.environ['U2NET_HOME']=str(RUNTIME/'weights/background')
  if not (RUNTIME/'weights/background/u2net.onnx').is_file():raise RuntimeError('Local background-removal weights are missing. Run setup for this mode again.')
  from rembg import remove,new_session
  im=remove(im,session=new_session('u2net',providers=['CPUExecutionProvider']))
  if im.getchannel('A').getbbox() is None:raise ValueError('No foreground found. Supply a transparent PNG cutout.')
 im.save(job/'input.png')
event('Input prepared; original image retained',0)
