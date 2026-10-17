#!/usr/bin/env python3
"""Collect small reproducibility evidence; never collect payload/native traces."""
import argparse,json,shutil,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
names={'runs.json','status.json','execution-provenance.json','routing.csv','expert-load.json','preparation-metrics.json','capacity-demand.json','resource.json','console.txt','preflight.json','online-summary.json','validation.json','simulator-metrics.json','summary.json'}
manifest=[]
for src in sorted(a.raw.rglob('*')):
 if not src.is_file() or src.name not in names or any(part in {'prepared-evidence','input-evidence','input-materialized'} for part in src.relative_to(a.raw).parts):continue
 if src.stat().st_size>2*1024**2:continue
 # Avoid duplicate input trees; preparation summaries and original routing are sufficient.
 if 'prepared' in src.relative_to(a.raw).parts and src.name not in {'routing.csv','expert-load.json','preparation-metrics.json','capacity-demand.json'}:continue
 dst=a.out/src.relative_to(a.raw);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 manifest.append(dict(path=str(dst.relative_to(a.out)),bytes=dst.stat().st_size,sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
(a.out/'manifest.json').write_text(json.dumps(dict(files=manifest,total_bytes=sum(x['bytes'] for x in manifest)),indent=2)+'\n');print(len(manifest),'small files',sum(x['bytes'] for x in manifest),'bytes')
