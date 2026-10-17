#!/usr/bin/env python3
"""Hash local large evidence without copying or publishing binary profiles."""
import argparse,hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);a=p.parse_args();raw=a.raw.resolve()
def entry(p,root):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=h.hexdigest())
files=[]
for d in ['runtime','calibration','instrumented','parity','python','postflight','faults','faults-enabled','faults-host','faults-enabled-host','build-host','aux']:
 for p in sorted((raw/d).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:files.append(entry(p,raw))
(H/'evidence/local-raw-manifest.json').write_text(json.dumps(dict(raw_root=str(raw),policy='Local-only large profiles, decoded stacks, ELF and execution evidence; hashes are not embedded data.',files=files),indent=2)+'\n')
files=[entry(p,H) for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST.json']
(H/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(files=files),indent=2)+'\n');print(len(files),'delivery files')
