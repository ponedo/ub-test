#!/usr/bin/env python3
"""Lossless, hash-verified format compaction of completed generated native traces.

Never invoke while a simulation/benchmark is active. Only this stage's own
completed run directories, with successful resource and verifier records, qualify.
"""
import argparse,hashlib,json,os,shutil,tarfile
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);a=p.parse_args();raw=a.raw.resolve()
if raw.name!='pair-jetty-raw':raise SystemExit('Refuse unrelated stage tree')
records=[]
for path in sorted(raw.glob('gate-d-*/*/*/run/native')):
 run=path.parent;arm=run.parent
 if not (run/'pair-validation.json').exists() or not (arm/'host/resource.json').exists():continue
 if json.loads((arm/'host/resource.json').read_text())['status']!='PASS':continue
 if json.loads((run/'pair-validation.json').read_text())['status']!='PASS':continue
 manifest={str(p.relative_to(path)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(path.rglob('*')) if p.is_file()}
 dest=run/'native.tar.gz';temp=run/'native.tar.gz.tmp';mp=run/'native.manifest.json'
 if dest.exists() or temp.exists() or mp.exists():raise RuntimeError('Refuse overwriting existing archive')
 with tarfile.open(temp,'w:gz',compresslevel=6) as t:t.add(path,arcname='native')
 readback={}
 with tarfile.open(temp,'r:gz') as t:
  for m in t:
   if m.isfile():
    h=hashlib.sha256();f=t.extractfile(m)
    while b:=f.read(1024*1024):h.update(b)
    readback[str(Path(m.name).relative_to('native'))]={'bytes':m.size,'sha256':h.hexdigest()}
 if readback!=manifest:raise RuntimeError('Archive readback mismatch; originals retained')
 os.replace(temp,dest)
 record={'operation':'lossless_format_compaction','source':'native/','archive':'native.tar.gz','archive_sha256':sha(dest),'archive_bytes':dest.stat().st_size,'original_bytes':sum(v['bytes'] for v in manifest.values()),'every_member_readback_verified':True,'files':manifest}
 mp.write_text(json.dumps(record,indent=2)+'\n')
 # Only the verified, fully recoverable generated representation is replaced.
 shutil.rmtree(path)
 records.append({'run':str(run.relative_to(raw)),**{k:v for k,v in record.items() if k!='files'}})
 (raw/'native-compaction.json').write_text(json.dumps(records,indent=2)+'\n')
 print(run,'verified',record['original_bytes'],'->',record['archive_bytes'],flush=True)
