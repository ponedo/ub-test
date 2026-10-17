#!/usr/bin/env python3
"""Lossless deduplicated evidence transport; preserve original evidence file bytes.

Opaque previous native.tar.gz containers are expanded to their original native/
member paths. Old container hashes are recorded separately, not claimed restored.
Every file is split into <=8 MiB chunks; identical chunks are stored once as XZ.
Natural content objects are packed into independent <=10 MB tar bundles. No links.
"""
import argparse,hashlib,io,json,lzma,tarfile,subprocess,sys
from pathlib import Path,PurePosixPath

def digest(b):return hashlib.sha256(b).hexdigest()
def safe(s):
 p=PurePosixPath(s)
 if p.is_absolute() or '..' in p.parts or not p.parts or str(p)!=s:raise ValueError('unsafe path '+s)
 return p

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise RuntimeError('fresh output required')
 a.out.mkdir(parents=True)
 files={};objects={};bundles=[];containers={};pending=[];pending_bytes=0
 def flush():
  nonlocal pending,pending_bytes
  if not pending:return
  name=f'objects-{len(bundles):04d}.tar';dest=a.out/name
  with tarfile.open(dest,'w',format=tarfile.USTAR_FORMAT) as t:
   for h,b in pending:
    m=tarfile.TarInfo(h+'.xz');m.size=len(b);m.mode=0o644;t.addfile(m,io.BytesIO(b));objects[h]['bundle']=name
  b=dest.read_bytes();assert len(b)<=10_000_000
  bundles.append({'name':name,'bytes':len(b),'sha256':digest(b)})
  print(name,len(b),flush=True);pending=[];pending_bytes=0
 def add(name,f,size):
  nonlocal pending_bytes
  safe(name);h=hashlib.sha256();chunks=[];n=0
  while b:=f.read(8*1024*1024):
   h.update(b);n+=len(b);ch=digest(b);chunks.append(ch)
   if ch in objects:continue
   z=lzma.compress(b,preset=3);cost=512+((len(z)+511)//512)*512
   if pending_bytes+cost>9_800_000:flush()
   pending.append((ch,z));pending_bytes+=cost;objects[ch]={'bytes':len(b),'compressed_bytes':len(z)}
  assert n==size,(name,n,size)
  row={'bytes':n,'sha256':h.hexdigest(),'chunks':chunks}
  if name in files and files[name]!=row:raise RuntimeError('path collision '+name)
  files[name]=row
 # Previous manifests define exactly the reviewed inclusion scope.
 selected=set()
 for mf in a.previous.glob('*.manifest.json'):selected.update(json.loads(mf.read_text()))
 for name in ['build-release','gate-a-extra-final','gate-a-extra-release']:
  for f in (a.raw/name).rglob('*'):
   if f.is_file() and f.open('rb').read(4)!=b'\x7fELF':selected.add(str(f.relative_to(a.raw)))
 selected.update(['reproduced-native-tree.txt','release-build-equivalence.json'])
 for name in sorted(selected):
  f=a.raw/name
  if f.name=='native.tar.gz':
   containers[name]={'bytes':f.stat().st_size,'sha256':digest(f.read_bytes()),'representation':'expanded member files'}
   with tarfile.open(f,'r:gz') as t:
    for m in t:
     if m.isdir():continue
     if not m.isfile():raise RuntimeError('unsupported tar member')
     child=str(PurePosixPath(name).parent/safe(m.name));add(child,t.extractfile(m),m.size)
  else:
   with f.open('rb') as stream:add(name,stream,f.stat().st_size)
 flush()
 manifest={'format':'pair-jetty-cas-v1','chunk_bytes':8*1024*1024,'compression':'xz-preset3','files':files,'objects':objects,'bundles':bundles,'expanded_original_containers':containers,'scope':'All previous selected evidence files, with native gzip containers expanded; plus final release wrapper validation. ELF/source clone exclusions unchanged.'}
 (a.out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 subprocess.run([sys.executable,str(Path(__file__).with_name('check-bundle-anchors.py')),'--raw',str(a.raw),'--previous',str(a.previous),'--bundle-dir',str(a.out),'--result',str(a.out/'anchor-verification.json')],check=True)
 print(json.dumps({'files':len(files),'objects':len(objects),'bundles':len(bundles),'logical_bytes':sum(x['bytes'] for x in files.values()),'bundle_bytes':sum(x['bytes'] for x in bundles)}),flush=True)
if __name__=='__main__':main()
