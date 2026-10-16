#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from guard import snapshot
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--raw',required=True);a=p.parse_args();raw=Path(a.raw).resolve();out=ROOT/'evidence';out.mkdir(exist_ok=True)
rows=[];commands=[]
for mode in ['no-balancing','ultraep']:
 for count in [50000,100000,200000,500000,1000000]:
  cid=f'{mode}-{count}';case=raw/cid
  if case.exists():raise SystemExit('raw case exists; choose a fresh CAPACITY_RAW')
  row=dict(case_id=cid,mode=mode,assignments=count,tokens=count//8,status='pending',selection='sequential NoBalance' if mode=='no-balancing' else 'only first and largest fully successful NoBalance scale; other rows not_selected',raw_dir=str(case));rows.append(row)
  d=ROOT/'cases'/cid;d.mkdir(parents=True,exist_ok=True);(d/'experiment-spec.md').write_text('# '+cid+'\n\nSee shared experiment-plan.md for fixed controls, hypotheses and guards.\n\n'+json.dumps(row,indent=2)+'\n')
  commands.append(dict(case_id=cid,stages=[dict(stage=s,argv=['python3.12',str(ROOT/'stage.py'),s,'--case',str(case),'--assignments',str(count),'--mode',mode]) for s in ['generate','planner','adapter','verify']],ns3_argv=['/workspace/ns-3-ub/build/scratch/ns3.44-multi-npu-relay','--input='+str(case/'run/input.txt'),'--out='+str(case/'run'),'--capacityMetrics='+str(case/'run/simulator-metrics.json')]))
(out/'run-ledger.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'initial-host.json').write_text(json.dumps(snapshot(),indent=2)+'\n');(ROOT/'matrix.yaml').write_text(json.dumps(rows,indent=2)+'\n');(ROOT/'command-manifest.yaml').write_text(json.dumps(commands,indent=2)+'\n')
