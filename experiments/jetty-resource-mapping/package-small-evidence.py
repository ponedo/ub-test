#!/usr/bin/env python3
"""Package bounded real inputs/events/profiles, never overwrite earlier artifacts."""
import argparse,gzip,hashlib,json,lzma,shutil,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--inputs-raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('Refuse existing output')
a.out.mkdir(parents=True);manifest=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
inputs=a.out/'fixed-inputs.tar.gz'
with tarfile.open(inputs,'w:gz',compresslevel=6) as t:
 for n in (5000,10000,20000,50000):
  root=a.inputs_raw/f'common-{n}'/'run'
  for f in sorted(root.iterdir()):
   if not f.is_file():raise ValueError(f)
   t.add(f,arcname=f'common-{n}/run/{f.name}')
manifest.append({'file':inputs.name,'bytes':inputs.stat().st_size,'sha256':sha(inputs),'contents':'Exact seven original run input files for each measured size'})
for n in (5000,10000,20000,50000):
 src=a.raw/f'{n}-A-timing'/'run'/'events.csv';dst=a.out/f'{n}-A-events.csv.gz'
 with src.open('rb') as r,gzip.open(dst,'wb',compresslevel=6) as w:shutil.copyfileobj(r,w)
 manifest.append({'file':dst.name,'bytes':dst.stat().st_size,'sha256':sha(dst),'raw_sha256':sha(src),'contents':'Raw A events; B exact identity independently checked in parity records'})
for arm in ('A','B'):
 src=a.raw/f'50000-{arm}-sampled'/'perf.data'
 if not src.is_file():continue
 # Compress locally first. Larger profiles remain local and are manifest-listed.
 dst=a.raw/f'50000-{arm}-sampled'/'perf.data.gz'
 if dst.exists():raise ValueError(f'Refuse overwrite {dst}')
 with src.open('rb') as r,gzip.open(dst,'wb',compresslevel=6) as w:shutil.copyfileobj(r,w)
 row={'source':str(src),'raw_bytes':src.stat().st_size,'raw_sha256':sha(src),'compressed_bytes':dst.stat().st_size,'compressed_sha256':sha(dst)}
 if dst.stat().st_size>=16*1024*1024:
  dst=a.raw/f'50000-{arm}-sampled'/'perf.data.xz'
  if dst.exists():raise ValueError(f'Refuse overwrite {dst}')
  with src.open('rb') as r,lzma.open(dst,'wb',preset=3) as w:shutil.copyfileobj(r,w)
  row['compressed_bytes']=dst.stat().st_size;row['compressed_sha256']=sha(dst)
 if dst.stat().st_size<20*1000*1000:
  target=a.out/f'50000-{arm}-{dst.name}';shutil.copy2(dst,target);row['file']=target.name
 else:row['not_published_reason']='Compressed profile exceeds 20MB repository delivery bound; full raw retained on host'
 manifest.append(row)
(a.out/'archives.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
