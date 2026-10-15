#!/usr/bin/env python3
import argparse,datetime,json,subprocess,sys,time
from pathlib import Path
from cases import cases,MODES,base,HERE
from adapter import emit
from verify import verify
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);p.add_argument('--case');a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);ledger=[];comparison={}
for name,(c,params,relay) in cases().items():
 if a.case and name!=a.case:continue
 # Compile the accepted plan once; copy its exact bytes into all three treatments.
 common=out/'common'/name
 base.emit(c,params,'no-balancing',common/'no-balancing');base.emit(c,params,'ultraep',common/'ultraep')
 block={}
 for mode in MODES:
  target=out/name/mode
  emit(common/('no-balancing' if mode=='no-balancing' else 'ultraep'),relay,'direct' if mode=='no-balancing' else mode,target)
  cmd=[sys.executable,'./ns3','run','--no-build',f'multi-npu-relay --input={target}/input.txt --out={target}']
  rec=dict(case_id=name+'/'+mode,command=cmd,start=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='running');ledger.append(rec)
  (out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
  with (target/'console.txt').open('w') as f:result=subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT)
  rec['returncode']=result.returncode
  try:
   if result.returncode:raise RuntimeError((target/'console.txt').read_text()[-2000:])
   summary=verify(target)
   with (target/'summary-optimized.json').open('w') as f:subprocess.run([sys.executable,'-O',str(HERE/'verify.py'),str(target)],stdout=f,check=True)
   if summary!=json.loads((target/'summary-optimized.json').read_text()):raise ValueError('normal/-O summary drift')
   (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');rec.update(status='PASS',summary=summary);block[mode]=summary
  except Exception as ex:
   rec.update(status='FAIL',error=str(ex));(out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');raise
  (out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
  print(name,mode,summary['layer_latency_ps'],summary['replicas'],len(summary['pipeline_overlaps']),flush=True)
 plans=[(out/name/m/'plan.json').read_bytes() for m in MODES[1:]]
 if not all(p==plans[0] for p in plans):raise ValueError('Planner changed between strategies')
 if not all(block[m]['per_npu_load']==block['direct']['per_npu_load'] for m in MODES[1:]):raise ValueError('compute load changed')
 if len({v['combine_sha256'] for v in block.values()})!=1:raise ValueError('Combine results changed')
 comparison[name]=block
 (out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
print('PASS matrix',len(ledger))
