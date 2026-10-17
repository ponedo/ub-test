#!/usr/bin/env python3
"""Independently verify every completed large execution; never run preparation."""
import argparse,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args();a.raw=a.raw.resolve();rows=[]
for d in sorted((a.raw/'runtime').iterdir()):
 summary=d/'run/online-summary.json'
 if not summary.exists():continue
 prov=json.loads((d/'provenance.json').read_text());dest=a.raw/'postflight'/d.name;dest.mkdir(parents=True,exist_ok=False)
 cmd=[sys.executable,str(H.parent/'tiered-logging/preflight.py'),prov['input_directory'],'--graph-tool',str(a.graph_tool.resolve()),'--execution-summary',str(summary),'--out',str(dest/'result.json')]
 r=run(cmd,dest/'host',300,case=dest);assert r['status']=='PASS',(d,r)
 result=json.loads((dest/'result.json').read_text());assert result['status']=='PASS'
 rows.append(dict(run=d.name,status='PASS',wall_seconds=r['wall_seconds'],user_cpu_seconds=r['user_cpu_seconds'],system_cpu_seconds=r['system_cpu_seconds'],peak_rss_kib=r['peak_rss_kib'],result=result))
(a.raw/'postflight/results.json').write_text(json.dumps(dict(status='PASS',runs=rows,chunk='Not completed; no postflight result'),indent=2)+'\n');print(json.dumps(rows,indent=2))
