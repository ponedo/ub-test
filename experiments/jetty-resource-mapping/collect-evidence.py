#!/usr/bin/env python3
"""Copy small original measurement records; hash large raw artifacts without duplicating them."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('Refuse existing evidence directory')
a.out.mkdir(parents=True);manifest={}
for case in sorted(a.raw.iterdir()):
 if not (case/'attempt.json').exists():continue
 rec=json.loads((case/'attempt.json').read_text())
 if rec.get('status')!='success':continue
 dest=a.out/case.name;dest.mkdir()
 files=[case/'attempt.json',case/'timing.tsv']+list((case/'stages').glob('*/*.json'))+list((case/'stages').glob('*/*.txt'))
 files += [case/'run'/n for n in ['simulator-metrics.json','result.json','summary.json','verification.json']]
 for f in files:
  if not f.is_file():continue
  rel=f.relative_to(case);d=dest/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d)
 for f in sorted(case.rglob('*')):
  if not f.is_file() or 'home' in f.relative_to(case).parts:continue
  h=hashlib.sha256()
  with f.open('rb') as r:
   for b in iter(lambda:r.read(1048576),b''):h.update(b)
  manifest[str(f.relative_to(a.raw))]={'bytes':f.stat().st_size,'sha256':h.hexdigest()}
(a.out/'raw-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'output':str(a.out),'raw_files':len(manifest)}))
