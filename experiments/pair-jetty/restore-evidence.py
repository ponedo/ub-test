#!/usr/bin/env python3
"""Restore and independently verify all raw evidence from the GitHub CAS bundles.

Only regular files are created. No tar extraction, symlinks, hardlinks, absolute
paths or parent traversal are accepted. Output must be absent/empty. Use
--verify-only to re-read every restored file against the manifest afterward.
"""
import argparse,functools,hashlib,json,lzma,tarfile
from pathlib import Path,PurePosixPath

def sha_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def safe(root,name):
 p=PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts or not p.parts or str(p)!=name:raise ValueError('unsafe path '+name)
 dest=root.joinpath(*p.parts)
 if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('path escape')
 return dest

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--verify-only',action='store_true');p.add_argument('--result',type=Path);a=p.parse_args()
 m=json.loads((a.bundle_dir/'manifest.json').read_text());assert m['format']=='pair-jetty-cas-v1' and m['chunk_bytes']==8*1024*1024
 if not a.verify_only:
  if a.out.exists() and any(a.out.iterdir()):raise RuntimeError('output must be empty')
  if a.out.is_symlink():raise RuntimeError('output symlink forbidden')
  a.out.mkdir(parents=True,exist_ok=True)
  handles={}
  for row in m['bundles']:
   f=safe(a.bundle_dir,row['name']);assert f.stat().st_size==row['bytes'] and sha_file(f)==row['sha256'],f
   t=tarfile.open(f,'r:');names=[]
   for member in t:
    if not member.isfile():raise RuntimeError('only regular objects accepted')
    h=member.name.removesuffix('.xz')
    if member.name!=h+'.xz' or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise RuntimeError('invalid object name')
    if h not in m['objects'] or m['objects'][h]['bundle']!=row['name']:raise RuntimeError('unexpected object')
    if member.size!=m['objects'][h]['compressed_bytes']:raise RuntimeError('object size mismatch')
    names.append(member.name)
   if len(names)!=len(set(names)):raise RuntimeError('duplicate archive object')
   handles[row['name']]=t
  @functools.lru_cache(maxsize=8)
  def chunk(h):
   row=m['objects'][h];t=handles[row['bundle']];z=t.extractfile(h+'.xz').read();decoder=lzma.LZMADecompressor(memlimit=128*1024*1024);b=decoder.decompress(z,max_length=8*1024*1024+1)
   if not decoder.eof or decoder.unused_data:raise RuntimeError('invalid compressed object')
   if len(b)!=row['bytes'] or len(b)>m['chunk_bytes'] or hashlib.sha256(b).hexdigest()!=h:raise RuntimeError('object integrity failure')
   return b
  for name,row in m['files'].items():
   dest=safe(a.out,name);dest.parent.mkdir(parents=True,exist_ok=True)
   with dest.open('xb') as f:
    for h in row['chunks']:f.write(chunk(h))
  for t in handles.values():t.close()
 # Separate full readback verifies reconstructed bytes, not only in-memory chunks.
 count=0;total=0
 for name,row in m['files'].items():
  f=safe(a.out,name)
  if f.is_symlink() or not f.is_file() or f.stat().st_size!=row['bytes'] or sha_file(f)!=row['sha256']:raise RuntimeError('file integrity failure '+name)
  count+=1;total+=row['bytes']
 result={'status':'PASS','files_verified':count,'bytes_verified':total,'fresh_restore':not a.verify_only,'manifest_sha256':sha_file(a.bundle_dir/'manifest.json'),'original_container_note':'native.tar.gz transport containers are represented by original native member files; container gzip bytes are not reconstructed.'}
 if a.result:a.result.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
if __name__=='__main__':main()
