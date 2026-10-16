#!/usr/bin/env python3
"""Lossless per-scale archives with content-identical files stored as tar links.
Run only after the matrix and secret scan finish. Does not remove raw evidence.
"""
import argparse,hashlib,json,tarfile
from pathlib import Path
H=Path(__file__).resolve().parent;WORK=H.parents[2];RAW=WORK/'prefill-cpu-raw'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def archive(dest,roots,base):
 seen={};manifest={}
 with tarfile.open(dest,'w:gz',compresslevel=6) as tar:
  for root in roots:
   for p in sorted(root.rglob('*')) if root.is_dir() else [root]:
    if not p.is_file():continue
    name=str(p.relative_to(base));sha=digest(p);size=p.stat().st_size;manifest[name]=dict(sha256=sha,bytes=size)
    info=tar.gettarinfo(str(p),arcname=name);key=(sha,size)
    if key in seen:info.type=tarfile.LNKTYPE;info.linkname=seen[key];info.size=0;tar.addfile(info)
    else:
     seen[key]=name
     with p.open('rb') as f:tar.addfile(info,f)
 verified={}
 with tarfile.open(dest,'r|gz') as check:
  for member in check:
   if member.islnk():verified[member.name]=verified[member.linkname]
   elif member.isfile():
    h=hashlib.sha256()
    f=check.extractfile(member)
    while b:=f.read(1024*1024):h.update(b)
    verified[member.name]=dict(sha256=h.hexdigest(),bytes=member.size)
 assert verified==manifest,'Archive round-trip hash verification failed'
 manifestpath=dest.with_suffix(dest.suffix+'.manifest.json');manifestpath.write_text(json.dumps(manifest,indent=2)+'\n')
 return dict(file=dest.name,bytes=dest.stat().st_size,sha256=digest(dest),files=len(manifest),unique_contents=len(seen),uncompressed_bytes=sum(x['bytes'] for x in manifest.values()),manifest=manifestpath.name,manifest_sha256=digest(manifestpath),archive_roundtrip_hash_check='PASS')
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=WORK/'prefill-cpu-delivery');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 scan=json.loads((H/'evidence/secret-scan.json').read_text());assert scan['status']=='PASS','Do not package flagged files'
 records=[]
 for n in [5000,10000,20000,50000]:
  roots=[RAW/f'common-{n}']+[RAW/f'{n}-{v}' for v in ['baseline','sampled','timed']]
  target=a.out/f'dot-prefill-{n}-raw.tar.gz'
  if target.exists():raise RuntimeError('Refuse overwrite '+str(target))
  records.append(archive(target,roots,RAW));print(records[-1],flush=True)
 extras=[p for p in [RAW/'small-parity',RAW/'5000-sampled-leafonly-attempt',RAW/'regressions',RAW/'analysis-raw',RAW/'calibration'] if p.exists()]
 records.append(archive(a.out/'dot-prefill-validation.tar.gz',extras,RAW));print(records[-1],flush=True)
 records.append(archive(a.out/'dot-prefill-symbols.tar.gz',[RAW/'symfs'],RAW));print(records[-1],flush=True)
 (a.out/'archives.json').write_text(json.dumps(records,indent=2)+'\n');(H/'evidence/archives.json').write_text(json.dumps(records,indent=2)+'\n')
 # Exact per-file inventories are small enough to publish with the source/report.
 for r in records:(H/'evidence'/r['manifest']).write_bytes((a.out/r['manifest']).read_bytes())
if __name__=='__main__':main()
