#!/usr/bin/env python3
"""Check post-matrix binaries and retain exact mmap paths in a portable symfs."""
import hashlib,json,os,shutil,struct,subprocess
from pathlib import Path
from execute import H,WORK,RAW

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
checks={}
for variant in ['baseline','timed']:
 before=json.loads((H/f'evidence/{variant}-binary-hashes-before.json').read_text());after={str(p):sha(Path(p)) for p in before};checks[variant]=dict(all_unchanged=all(after[p]==x['sha256'] for p,x in before.items()),sha256=after)
 assert checks[variant]['all_unchanged'],'Measured binary changed during matrix'
(H/'evidence/binary-hashes-after.json').write_text(json.dumps(checks,indent=2)+'\n')
paths=set(Path(p) for variant in checks.values() for p in variant['sha256'])
for data in list(RAW.glob('*-sampled/perf.data')) + list((H/'evidence').glob('calibration*.data')):
 with data.open('rb') as f:
  head=f.read(56);_,_,_,_,_,off,length=struct.unpack('<7Q',head);end=off+length
  while off<end:
   f.seek(off);typ,misc,size=struct.unpack('<IHH',f.read(8));assert size>=8
   if typ==10:
    f.seek(off+72);name=f.read(size-72).split(b'\0',1)[0].decode(errors='replace')
    if name.startswith('/') and Path(name).is_file():paths.add(Path(name))
   off+=size
symfs=RAW/'symfs';symfs.mkdir(exist_ok=True);manifest={}
for p in sorted(paths):
 target=symfs/str(p).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():
  try:os.link(p.resolve(),target)
  except OSError:shutil.copy2(p,target)
 manifest[str(p)]={'symfs_path':str(target.relative_to(RAW)),'sha256':sha(target),'bytes':target.stat().st_size}
(H/'evidence/symbol-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Frozen exact native/system ELF paths:',len(paths))
