#!/usr/bin/env python3
"""Run each native unit suite from its expected checkout cwd, retaining all results."""
import argparse,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--runner',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.native=a.native.resolve();a.runner=a.runner.resolve()
if a.out.exists():raise SystemExit('Refuse existing output')
a.out.mkdir(parents=True)
# Use the native type filter to enumerate exactly its unit suites.
names=subprocess.check_output([str(a.runner),'--list','--test-type=unit'],cwd=a.native,text=True).splitlines()
(a.out/'test-list.txt').write_text('\n'.join(names)+'\n');results=[]
for name in names:
 if not name.strip():continue
 started=time.monotonic()
 with (a.out/(name+'.log')).open('w') as f:
  try:r=subprocess.run([str(a.runner),'--test-name='+name,'--verbose'],cwd=a.native,stdout=f,stderr=subprocess.STDOUT,timeout=120);code=r.returncode
  except subprocess.TimeoutExpired:code=124
 results.append({'suite':name,'returncode':code,'wall_seconds':time.monotonic()-started})
 (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'suites':len(results),'passed':sum(r['returncode']==0 for r in results)}))
raise SystemExit(not results or any(r['returncode'] for r in results))
