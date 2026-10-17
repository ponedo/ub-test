#!/usr/bin/env python3
import tempfile,json
from pathlib import Path
from compact import compact
from restore import restore
with tempfile.TemporaryDirectory() as td:
 root=Path(td);src=root/'source';src.mkdir();(src/'nested').mkdir();(src/'nested/a.bin').write_bytes(bytes(range(256))*100);(src/'empty').write_bytes(b'')
 compact(src,root/'package');r=restore(root/'package',root/'restored');assert r['files']==2
 try:restore(root/'package',root/'restored')
 except ValueError:pass
 else:raise AssertionError('nonempty accepted')
 manifest=json.loads((root/'package/manifest.json').read_text());part=root/'package'/manifest['parts'][0]['name'];part.write_bytes(b'x'+part.read_bytes()[1:])
 try:restore(root/'package',root/'tamper')
 except ValueError:pass
 else:raise AssertionError('corruption accepted')
print(json.dumps({'status':'PASS','tests':['roundtrip','nonempty rejected','corrupted part rejected']}))
# Mutated archive headers remain invalid even with matching transport hashes.
import tarfile,io,hashlib
for kind in ['traversal','symlink']:
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);package=root/'package';package.mkdir();archive=root/'x.tar.xz'
  with tarfile.open(archive,'w:xz') as t:
   m=tarfile.TarInfo('../outside' if kind=='traversal' else 'link');m.size=0
   if kind=='symlink':m.type=tarfile.SYMTYPE;m.linkname='/tmp'
   t.addfile(m,io.BytesIO(b''))
  data=archive.read_bytes();(package/'part').write_bytes(data);h=hashlib.sha256(data).hexdigest()
  manifest=dict(format='verified-tar-xz-parts-v1',parts=[dict(name='part',bytes=len(data),sha256=h)],archive_bytes=len(data),archive_sha256=h,files={m.name:dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest())})
  (package/'manifest.json').write_text(json.dumps(manifest))
  try:restore(package,root/'output')
  except ValueError:pass
  else:raise AssertionError(kind+' accepted')
print(json.dumps({'status':'PASS','tests':['path traversal rejected','symlink rejected']}))
with tempfile.TemporaryDirectory() as td:
 root=Path(td);src=root/'source';(src/'direct').mkdir(parents=True);(src/'chunk').mkdir();(src/'direct/a').write_bytes(b'direct');(src/'chunk/b').write_bytes(b'chunk')
 compact(src,root/'package');r=restore(root/'package',root/'selected',prefix='direct')
 assert r['files']==2 and (root/'selected/a').read_bytes()==b'direct' and not (root/'selected/b').exists()
print(json.dumps({'status':'PASS','tests':['selected input restore verifies all archived bytes']}))
