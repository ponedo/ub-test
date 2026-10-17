#!/usr/bin/env python3
"""Collect bounded aggregates/proofs only; keep raw input and payload files local."""
import argparse,hashlib,io,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest();sources=[]
names={'status.json','execution-provenance.json','preparation-metrics.json','capacity-precheck.json','preflight.json','postflight.json','validation.json','online-summary.json','simulator-metrics.json','resource.json'}
for src in sorted(a.raw.rglob('*')):
 if not src.is_file() or src.name not in names or any(x in src.relative_to(a.raw).parts for x in ('input-evidence','prepared-evidence','input-materialized')):continue
 data=src.read_bytes()
 if len(data)>2*1024**2:raise ValueError('Unexpected oversized aggregate: '+str(src))
 dest=a.out/src.relative_to(a.raw);dest.parent.mkdir(parents=True,exist_ok=True)
 if src.name=='resource.json':
  d=json.loads(data);d={k:v for k,v in d.items() if k not in ('host_before','host_after')};dest.write_text(json.dumps(d,indent=2)+'\n')
 else:dest.write_bytes(data)
 sources.append(dict(source=str(src),source_bytes=len(data),source_sha256=sha(data),delivery=str(dest.relative_to(a.out)),delivery_sha256=sha(dest.read_bytes()),transformation='omit bulky host snapshots only' if src.name=='resource.json' else 'exact bytes'))
# Extract the original small capacity predictions, preserving original wording.
for package in sorted(a.raw.glob('tokens-*/prepared-evidence')):
 m=json.loads((package/'manifest.json').read_text());parts=[]
 for r in m['parts']:
  b=(package/r['name']).read_bytes();assert sha(b)==r['sha256'];parts.append(b)
 data=b''.join(parts);assert sha(data)==m['archive_sha256']
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as archive:
  for member in archive:
   if not member.name.endswith('-capacity-prediction.json'):continue
   data=archive.extractfile(member).read();assert sha(data)==m['files'][member.name]['sha256'];dest=a.out/package.parent.name/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);sources.append(dict(source=str(package)+':'+member.name,source_sha256=sha(data),delivery=str(dest.relative_to(a.out)),delivery_sha256=sha(data),transformation='exact verified archive member'))
(a.out/'source-manifest.json').write_text(json.dumps(sources,indent=2)+'\n');print(len(sources),'aggregate proofs')
