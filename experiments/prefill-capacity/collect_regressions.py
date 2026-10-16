#!/usr/bin/env python3
import hashlib,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent;raw=Path(os.environ.get('CAPACITY_RAW','/workspace/prefill-capacity-raw'));out=ROOT/'evidence';source=raw/'regressions';dest=out/'regressions';dest.mkdir(exist_ok=True)
for p in source.iterdir():
 if p.is_file():shutil.copyfile(p,dest/p.name)
if (source/'prior-regression').exists():shutil.copytree(source/'prior-regression',dest/'prior-regression',dirs_exist_ok=True)
for name in ['console.txt','resource.json','resource-samples.csv']:
 shutil.copyfile(raw/'regression-host'/name,out/('regression-'+name))
files={}
for p in source.rglob('*'):
 if p.is_file():
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  files[str(p.relative_to(source))]=dict(bytes=p.stat().st_size,sha256=h.hexdigest())
(dest/'raw-artifacts.json').write_text(json.dumps(files,indent=2)+'\n');print('regression evidence collected:',len(files),'raw files')
