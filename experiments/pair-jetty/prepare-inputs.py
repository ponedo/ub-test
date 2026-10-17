#!/usr/bin/env python3
"""Reuse the accepted fixed-seed generator, planner and graph adapter unchanged."""
import argparse,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path[:0]=[str(H.parent/'wqe-completion-fix'),str(H.parents[2]/'prefill-cpu-tools')]
from guard import run
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--assignments',type=int,required=True);p.add_argument('--mode',choices=['no-balancing','ultraep'],default='no-balancing');p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args()
a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
env={'PATH':os.path.dirname(sys.executable)+':/usr/bin:/bin','LANG':'C.UTF-8','RELAY_GRAPH_TOOL':str(a.graph_tool.resolve())}
ledger=[]
for stage in ['generate','planner','adapter']:
 command=[sys.executable,str(H.parent/'prefill-capacity/stage.py'),stage,'--case',str(a.out),'--assignments',str(a.assignments),'--mode',a.mode]
 r=run(command,a.out/'stages'/stage,300,case=a.out,env=env);ledger.append({'stage':stage,'host':r})
 (a.out/'preparation.json').write_text(json.dumps(ledger,indent=2)+'\n')
 if r['status']!='PASS':raise SystemExit('Input preparation failed: '+stage)
