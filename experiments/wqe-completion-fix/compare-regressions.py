#!/usr/bin/env python3
"""Compare all deterministic simulation CSV, payload and summary artifacts."""
import argparse, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--before',type=Path,required=True); p.add_argument('--after',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as r:
  for chunk in iter(lambda:r.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def collect(root):
 return {str(f.relative_to(root)):sha(f) for f in sorted(root.rglob('*')) if f.is_file() and (f.suffix in ('.csv','.bin') or f.name in ('summary.json','summary-optimized.json'))}
b=collect(a.before);c=collect(a.after);changed=[k for k in sorted(b.keys()|c.keys()) if b.get(k)!=c.get(k)]
result={'before_files':len(b),'after_files':len(c),'changed':changed,'pass':bool(b) and not changed,'before_hashes':b,'after_hashes':c}
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if not k.endswith('_hashes')}));raise SystemExit(not result['pass'])
