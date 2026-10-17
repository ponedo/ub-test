#!/usr/bin/env python3
"""Lossless finalized, owned case compaction; exact readback before removal."""
import hashlib,json,os,shutil,tarfile
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def compact(source,out):
 source,out=Path(source).resolve(),Path(out).resolve()
 if source==out or source in out.parents:raise ValueError('archive must be outside source')
 if out.exists():raise ValueError('fresh archive target required')
 out.mkdir(parents=True)
 files={str(f.relative_to(source)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(source.rglob('*')) if f.is_file()}
 if any(f.is_symlink() for f in source.rglob('*')):raise ValueError('symlink refused')
 tmp=out/'content.tar.xz'
 with tarfile.open(tmp,'w:xz',preset=3) as t:
  for name in files:t.add(source/name,arcname=name,recursive=False)
 check={}
 with tarfile.open(tmp,'r:xz') as t:
  for m in t:
   if not m.isfile():raise ValueError('nonfile')
   h=hashlib.sha256();f=t.extractfile(m)
   while b:=f.read(1024*1024):h.update(b)
   check[m.name]={'bytes':m.size,'sha256':h.hexdigest()}
 if files!=check:raise ValueError('archive mismatch; original retained')
 parts=[]
 with tmp.open('rb') as f:
  while b:=f.read(9_000_000):
   name=f'part-{len(parts):04d}.xzpart';(out/name).write_bytes(b);parts.append({'name':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 record={'format':'verified-tar-xz-parts-v1','source_name':source.name,'files':files,'parts':parts,'archive_bytes':tmp.stat().st_size,'archive_sha256':sha(tmp),'full_readback_verified':True}
 joined=hashlib.sha256();joined_bytes=0
 for row in parts:
  data=(out/row['name']).read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'];joined.update(data);joined_bytes+=len(data)
 assert joined_bytes==record['archive_bytes'] and joined.hexdigest()==record['archive_sha256']
 (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');tmp.unlink()
 # Owned finalized outputs only. Caller waits for simulation AND verifier termination.
 shutil.rmtree(source)
 return {k:v for k,v in record.items() if k not in ['files','parts']}
