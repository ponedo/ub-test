#!/usr/bin/env python3
import json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
rows=[]
for root in sorted((R/'runtime').glob('*')):
 summary=root/'run/online-summary.json'
 if not summary.exists():continue
 dest=R/'postflight'/root.name
 if dest.exists():
  r=json.loads((dest/'host/resource.json').read_text());result=json.loads((dest/'result.json').read_text());assert r['status']==result['status']=='PASS'
  rows.append(dict(run=root.name,status='PASS',wall_s=r['wall_seconds'],user_cpu_s=r['user_cpu_seconds'],result=result));continue
 dest.mkdir(parents=True)
 inp=Path(json.loads((root/'provenance.json').read_text())['input']).parent
 cmd=[sys.executable,str(H.parent/'tiered-logging/preflight.py'),str(inp),'--graph-tool',str(W/'ep64-scaling-raw/build/graph-tool'),'--execution-summary',str(summary),'--out',str(dest/'result.json')]
 r=run(cmd,dest/'host',300,case=dest);assert r['status']=='PASS'
 rows.append(dict(run=root.name,status='PASS',wall_s=r['wall_seconds'],user_cpu_s=r['user_cpu_seconds'],result=json.loads((dest/'result.json').read_text())))
(H/'postflight.json').write_text(json.dumps(dict(status='PASS',completed_runs=rows,note='Incomplete runs have no completed latency or postflight claim.'),indent=2)+'\n')
