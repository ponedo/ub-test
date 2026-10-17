#!/usr/bin/env python3
"""A finalized audit must never certify an incomplete or duplicate run set."""
import json, subprocess, sys, tempfile
from pathlib import Path
H=Path(__file__).resolve().parent
full=[dict(layer=l,strategy=s,status='PASS') for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming']]
cases=[('empty',[],'PASS'),('eight',full[:8],'PASS'),('running',full,'RUNNING'),('duplicate',full[:-1]+[full[0]],'PASS'),('failed',full[:-1]+[dict(full[-1],status='FAIL')],'PASS')]
for name,rows,status in cases:
 with tempfile.TemporaryDirectory(prefix='qwen-final-audit-') as tmp:
  root=Path(tmp);(root/'runs.json').write_text(json.dumps(rows));(root/'status.json').write_text(json.dumps(dict(status=status)))
  r=subprocess.run([sys.executable,H/'verify_artifacts.py','--private',root,'--out',root/'result.json'],capture_output=True,text=True)
  if r.returncode==0 or 'exactly nine unique completed cases' not in r.stderr or (root/'result.json').exists():raise RuntimeError(name+' was not rejected correctly')
print('PASS 5 incomplete/duplicate final-inventory rejection checks')
