#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',default=str(ROOT/'evidence'));args=p.parse_args();out=Path(args.out)
files={}
for root,prefix in [(ROOT,'module'),(out,'evidence')]:
 for path in sorted(root.rglob('*')):
  if not path.is_file() or '__pycache__' in path.parts or '.venv' in path.parts or path.name=='artifact-manifest.json':continue
  if prefix=='module' and 'evidence' in path.relative_to(root).parts:continue
  files[prefix+'/'+str(path.relative_to(root))]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(out/'artifact-manifest.json').write_text(json.dumps(files,indent=2)+'\n');print('artifact hashes:',len(files))
