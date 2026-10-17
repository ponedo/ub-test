#!/usr/bin/env python3
"""Package this stage's measured evidence, keeping exact per-file hashes.

Compiled ELF files, prior-checkout snapshots and .git internals are excluded.
Application payload bytes and raw event logs are included. Native trace archives
are included when present. The complete original workspace remains untouched.
"""
import argparse,hashlib,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--groups',nargs='+');a=p.parse_args();raw=a.raw.resolve();a.out.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
# Separate groups keep individual archives manageable for GitHub.
groups={'gate-a':['gate-a','gate-a-extra','gate-a-final'],'gate-b-c':['gate-b','gate-c','gate-c-negative'],'regressions':['native-tests','old-regressions'],'build':['build-final','cpp-source-sha256.txt','source-invariants.json','native-provenance.json','application-integration.patch','native-compaction.json','reverify-small.json','elf-post-regression-check.txt','source-post-regression-check.txt','restored-fixture-parity.json','restore-fixtures-console.txt']}
for d in sorted(raw.glob('gate-d-*')):
 if d.is_dir():
  if d.name=='gate-d-100000':
   for mode in ['pair','per-wqe']:
    groups[d.name+'-'+mode]=[str(x.relative_to(raw)) for x in d.glob('*/'+mode)]+[str((d/'results.json').relative_to(raw))]
  else:groups[d.name]=[d.name]
groups['prepared-inputs']=['common-100000']
groups['release-validation']=['build-release','gate-a-extra-final','gate-a-extra-release','reproduced-native-tree.txt','release-build-equivalence.json']
archives=json.loads((a.out/'archives.json').read_text()) if a.groups and (a.out/'archives.json').exists() else []
for group,names in groups.items():
 if a.groups and group not in a.groups:continue
 files=[]
 for name in names:
  p=raw/name
  if not p.exists():continue
  candidates=[p] if p.is_file() else sorted(p.rglob('*'))
  for f in candidates:
   if not f.is_file():continue
   rel=f.relative_to(raw)
   if '.git' in rel.parts or 'source' in rel.parts:continue
   with f.open('rb') as h:
    if h.read(4)==b'\x7fELF':continue
   files.append(f)
 if not files:continue
 dest=a.out/(group+'.tar.gz')
 if dest.exists():raise RuntimeError('Refuse archive overwrite')
 manifest={str(f.relative_to(raw)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in files}
 with tarfile.open(dest,'w:gz',compresslevel=6) as t:
  for f in files:t.add(f,arcname=str(f.relative_to(raw)),recursive=False)
 check={}
 with tarfile.open(dest,'r:gz') as t:
  for m in t:
   if not m.isfile():continue
   h=hashlib.sha256();f=t.extractfile(m)
   while b:=f.read(1024*1024):h.update(b)
   check[m.name]={'bytes':m.size,'sha256':h.hexdigest()}
 if check!=manifest:raise RuntimeError('Archive verification mismatch')
 (a.out/(group+'.manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 row={'file':dest.name,'sha256':sha(dest),'bytes':dest.stat().st_size,'members':len(manifest),'full_readback_verified':True};archives.append(row)
 (a.out/'archives.json').write_text(json.dumps(archives,indent=2)+'\n');print(row,flush=True)
