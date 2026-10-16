#!/usr/bin/env python3
"""Losslessly archive the publication export; prove archive bytes."""
import hashlib,json,tarfile
from pathlib import Path
H=Path(__file__).resolve().parent;RAW=Path('/workspace/prefill-cpu-export');OUT=H/'archives';OUT.mkdir(exist_ok=True)
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
archives=[]
for p in sorted(RAW.iterdir()):
 name=p.name+'.tar.gz';dest=OUT/name
 if not dest.exists():
  with tarfile.open(dest,'w:gz',compresslevel=6) as t:t.add(p,arcname=p.name)
 files={str(f.relative_to(RAW)):digest(f) for f in ([p] if p.is_file() else p.rglob('*')) if f.is_file()}
 with tarfile.open(dest,'r:gz') as t:
  seen={}
  for member in t:
   if member.isfile():
    h=hashlib.sha256();f=t.extractfile(member)
    while b:=f.read(1024*1024):h.update(b)
    seen[member.name]=h.hexdigest()
 assert seen==files,(p,'archive mismatch')
 archive_hash=digest(dest)
 parts=[]
 if dest.stat().st_size>45*1024**2:
  with dest.open('rb') as f:
   i=0
   while b:=f.read(32*1024**2):
    part=OUT/(name+f'.part{i:02}');part.write_bytes(b);parts.append(dict(file=part.name,bytes=len(b),sha256=digest(part)));i+=1
  dest.unlink()
 archives.append(dict(archive=name,sha256=archive_hash,parts=parts,files=files))
 print(name,len(files),'verified',flush=True)
(H/'evidence/archive-manifest.json').write_text(json.dumps(archives,indent=2)+'\n')
(OUT/'README.md').write_text('# Raw evidence\n\nEach tar.gz retains the publication export of a raw directory or standalone file. Inherited credential strings in DWARF stack bytes were redacted at equal length; original raw profiles remain local in /workspace/prefill-cpu-raw and are not published. See ../evidence/publication-redactions.json for exact file hashes/counts and proof that decoded stacks are byte-identical. All other raw files are unchanged. File-by-file SHA256 was rechecked by reading the compressed archive; live raw files were not deleted. See ../evidence/archive-manifest.json.\n\nIf split, concatenate numbered parts in order: `cat NAME.tar.gz.part* > NAME.tar.gz`. Extract each archive into a fresh directory with `tar -xzf NAME.tar.gz -C DEST`. The local original data are preserved; export/redaction and compression happened after measurements.\n')
