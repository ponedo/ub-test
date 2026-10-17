#!/usr/bin/env python3
"""Hash compact delivered evidence and own host-local raw files, never delete data."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
 return h.hexdigest()
def entry(p,root):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
# Canonical LF for compact CSV delivery; host-local raw is never changed.
for p in H.rglob('*.csv'):p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
raw=[entry(p,R) for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
(H/'local-raw-manifest.json').write_text(json.dumps(dict(root=str(R),note='Retained on the original host; hashes do not imply remote availability. Includes intentionally preserved initial harness failures and full resources.',files=raw),indent=2)+'\n')
files=[entry(p,H) for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST.json']
(H/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(files=files,total_bytes=sum(x['bytes'] for x in files),raw_files=len(raw),raw_bytes=sum(x['bytes'] for x in raw)),indent=2)+'\n')
print(len(files),'compact files;',len(raw),'local raw files')
