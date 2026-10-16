#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;files={}
for p in sorted(ROOT.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name=='artifact-manifest.json':continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 files[str(p.relative_to(ROOT))]=dict(bytes=p.stat().st_size,sha256=h.hexdigest())
(ROOT/'evidence/artifact-manifest.json').write_text(json.dumps(files,indent=2)+'\n');print('hashed',len(files),'capacity artifacts')
