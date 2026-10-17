#!/usr/bin/env python3
"""Check transformed evidence against pre-existing reviewed file hashes."""
import argparse,json
from pathlib import Path,PurePosixPath
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--bundle-dir',type=Path,required=True);p.add_argument('--result',type=Path,required=True);a=p.parse_args()
m=json.loads((a.bundle_dir/'manifest.json').read_text());n=0;expanded=0
for manifest in a.previous.glob('*.manifest.json'):
 for name,row in json.loads(manifest.read_text()).items():
  target=m['expanded_original_containers'].get(name) if name.endswith('/native.tar.gz') else m['files'].get(name)
  assert target is not None and all(target[k]==row[k] for k in ['bytes','sha256']),name
  n+=1
for name,row in m['expanded_original_containers'].items():
 old=json.loads((a.raw/PurePosixPath(name).parent/'native.manifest.json').read_text())
 assert row['sha256']==old['archive_sha256'] and row['bytes']==old['archive_bytes'],name
 for rel,expected in old['files'].items():
  path=str(PurePosixPath(name).parent/'native'/rel);got=m['files'][path]
  assert all(got[k]==expected[k] for k in ['bytes','sha256']),path
  expanded+=1
r={'status':'PASS','old_manifest_file_entries_checked':n,'expanded_native_members_checked':expanded,'scope':'Every old selected file/container hash matches; every expanded native file matches its original pre-compaction member hash.'};a.result.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
