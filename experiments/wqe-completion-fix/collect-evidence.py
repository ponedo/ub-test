#!/usr/bin/env python3
"""Publish raw small artifacts and integrity manifests, never duplicate bulk payloads/ELFs."""
import argparse, hashlib, json, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
def copy(source,relative):
 target=a.out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
for group in ('probes','probes-final','native-unit-suites','native-unit-suites-final','overhead-summary'):
 root=a.raw/group
 if root.exists():
  for f in root.iterdir():
   if f.is_file() and f.suffix:copy(f,Path(group)/f.name)
for f in a.raw.iterdir():
 if f.is_file() and f.suffix in ('.json','.csv','.log','.txt'):copy(f,f.name)
for group in ('regression-C','regression-final'):
 root=a.raw/group
 if not root.exists():continue
 for f in root.rglob('*'):
  if not f.is_file() or 'source' in f.relative_to(root).parts or 'aux' in f.relative_to(root).parts:continue
  if f.name in ('console.txt','resource.json','resource-samples.csv','bootstrap-only.patch','native-provenance.json','tests.json','tests-optimized.json','execution.json','legacy-parity.json','artifact-sha256.json','comparison.json','run-ledger.json','summary.json','summary-optimized.json','planner-numeric-bounds.json') or f.suffix=='.txt':
   copy(f,Path(group)/f.relative_to(root))
root=a.raw/'overhead'
if root.exists():
 for f in root.rglob('*'):
  if not f.is_file() or 'frozen' in f.relative_to(root).parts or 'run' in f.relative_to(root).parts:continue
  if f.suffix in ('.json','.jsonl','.csv','.txt','.md'):copy(f,Path('overhead')/f.relative_to(root))
manifest={str(f.relative_to(a.out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.out.rglob('*')) if f.is_file()}
(a.out/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(len(manifest),'files',sum(f.stat().st_size for f in a.out.rglob('*') if f.is_file()),'bytes')
