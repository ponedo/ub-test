#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
from guard import run
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--assignments',type=int,required=True);p.add_argument('--mode',default='no-balancing',choices=['no-balancing','ultraep']);p.add_argument('--raw',default='/workspace/prefill-capacity-raw');p.add_argument('--binary',default='/workspace/ns-3-ub/build/scratch/ns3.44-multi-npu-relay');a=p.parse_args()
cid=f'{a.mode}-{a.assignments}';case=Path(a.raw)/cid;case.mkdir(parents=True,exist_ok=True);ledgerpath=ROOT/'evidence/run-ledger.json';ledger=json.loads(ledgerpath.read_text());entry=next(x for x in ledger if x['case_id']==cid)
if entry['status'] not in ['pending','not_attempted']:raise SystemExit('case already attempted; preserve evidence')
entry.update(status='running',stages={})
def save():ledgerpath.write_text(json.dumps(ledger,indent=2)+'\n')
save()
for stage in ['generate','planner','adapter','ns3','verify']:
 if stage=='ns3':cmd=[a.binary,'--input='+str(case/'run/input.txt'),'--out='+str(case/'run'),'--capacityMetrics='+str(case/'run/simulator-metrics.json')]
 else:cmd=[sys.executable,str(ROOT/'stage.py'),stage,'--case',str(case),'--assignments',str(a.assignments),'--mode',a.mode]
 result=run(cmd,case/'stages'/stage,300 if stage in ['ns3','verify'] else 180,case=case)
 entry['stages'][stage]=result;save()
 if result['status']!='PASS':
  entry.update(status='failed',failed_stage=stage,reason=result['guard'] or (case/'stages'/stage/'console.txt').read_text()[-2000:]);save();break
else:entry['status']='success';save()
print(cid,entry['status'],flush=True)
