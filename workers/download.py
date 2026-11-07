"""Downloads pinned released weights, never invokes inference APIs."""
import json,sys
from pathlib import Path
from huggingface_hub import hf_hub_download,snapshot_download
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'weights.json').read_text())
for name in sys.argv[1:]:
 spec=manifest[name];dest=root/'runtime/weights'/name;dest.mkdir(parents=True,exist_ok=True)
 print('DOWNLOAD',name,spec['repo'],flush=True)
 if 'patterns' in spec:snapshot_download(spec['repo'],revision=spec['revision'],allow_patterns=spec['patterns'],local_dir=dest)
 else:
  for i,file in enumerate(spec['files']):
   print(f'FILE {i+1}/{len(spec["files"])} {name}/{file}',flush=True)
   hf_hub_download(spec['repo'],file,revision=spec['revision'],local_dir=dest)
 print('DOWNLOADED',name,flush=True)
