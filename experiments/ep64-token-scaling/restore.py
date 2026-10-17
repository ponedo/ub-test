#!/usr/bin/env python3
"""Restore one independently hashed evidence package into a fresh directory."""
import argparse,hashlib,io,json,tarfile,tempfile
from pathlib import Path,PurePosixPath
from compact import sha

def restore(package,out,prefix=None):
 package,out=Path(package),Path(out)
 m=json.loads((package/'manifest.json').read_text())
 if m['format']!='verified-tar-xz-parts-v1':raise ValueError('format')
 if out.exists() and any(out.iterdir()):raise ValueError('empty destination required')
 out.mkdir(parents=True,exist_ok=True)
 def safe(s):
  p=PurePosixPath(s)
  if p.is_absolute() or '..' in p.parts or str(p)!=s:raise ValueError('unsafe path')
  return p
 # Stream parts via a file-like reader; no second disk copy of the archive.
 class Parts(io.RawIOBase):
  def __init__(self):self.index=0;self.current=None;self.h=hashlib.sha256();self.n=0
  def readable(self):return True
  def read(self,size=-1):
   if size<0:raise ValueError('unbounded read')
   result=bytearray()
   while len(result)<size:
    if self.current is None:
     if self.index==len(m['parts']):break
     row=m['parts'][self.index];p=package/safe(row['name'])
     if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('part hash')
     self.current=p.open('rb');self.index+=1
    b=self.current.read(size-len(result))
    if not b:self.current.close();self.current=None;continue
    self.h.update(b);self.n+=len(b);result.extend(b)
   return bytes(result)
 stream=Parts();seen=set()
 with tarfile.open(fileobj=stream,mode='r|xz') as t:
  for member in t:
   name=str(safe(member.name));expected=m['files'].get(name)
   if not member.isfile() or name in seen or expected is None or expected['bytes']!=member.size:raise ValueError('invalid member')
   selected=prefix is None or name.startswith(prefix+'/')
   relative=name if prefix is None else name[len(prefix)+1:]
   h=hashlib.sha256();n=0;src=t.extractfile(member);f=None
   if selected:
    path=out/safe(relative);path.parent.mkdir(parents=True,exist_ok=True);f=path.open('xb')
   try:
    while b:=src.read(1024*1024):
     if f:f.write(b)
     h.update(b);n+=len(b)
   finally:
    if f:f.close()
   if n!=expected['bytes'] or h.hexdigest()!=expected['sha256']:raise ValueError('file hash')
   seen.add(name)
 while stream.read(1024*1024):pass
 if stream.n!=m['archive_bytes'] or stream.h.hexdigest()!=m['archive_sha256'] or seen!=m['files'].keys():raise ValueError('archive/file set mismatch')
 if prefix is not None and not any(n.startswith(prefix+'/') for n in seen):raise ValueError('missing prefix')
 return {'status':'PASS','files':len(seen),'bytes':sum(v['bytes'] for v in m['files'].values())}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(restore(a.package,a.out)))
