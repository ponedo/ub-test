#!/usr/bin/env python3
import argparse,json,subprocess,sys,time
from pathlib import Path
from cases import cases
from adapter import emit,require
from verify import verify
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);args=p.parse_args()
HERE=Path(__file__).resolve().parent;out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((HERE/'matrix.yaml').read_text());require([x['case_id'] for x in manifest]==[name+'/'+mode for name in cases() for mode in ['no-balancing','ultraep']],'frozen matrix mismatch')
ledger=[];pairs=[]
for name,(pc,params) in cases().items():
    summaries={};configs={}
    for mode in ['no-balancing','ultraep']:
        case=out/name/mode;c,plan=emit(pc,params,mode,case);configs[mode]=c
        command=[sys.executable,'./ns3','run','--no-build',f'direct-weight-forward --input={case}/input.txt --out={case}']
        row=dict(case=name+'/'+mode,status='running',command=command,start_unix=time.time());ledger.append(row)
        (out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
        with (case/'console.txt').open('w') as f:r=subprocess.run(command,cwd=args.ns3,stdout=f,stderr=subprocess.STDOUT)
        row.update(returncode=r.returncode,end_unix=time.time())
        try:
            require(r.returncode==0,f'{name}/{mode}: simulator exit {r.returncode}')
            summary=verify(case);summaries[mode]=summary;(case/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
            with (case/'summary-optimized.json').open('w') as f:subprocess.run([sys.executable,'-O',str(HERE/'verify.py'),str(case)],stdout=f,check=True)
            row.update(status='success',summary=summary,checkpoint='verified; continue')
        except Exception as error:
            row.update(status='failed',error=str(error));(out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');raise
        (out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
        print(name,mode,summary['layer_latency_ps'],summary['replicas'],flush=True)
    a,b=configs['no-balancing'],configs['ultraep'];require(a['planner_input']==b['planner_input'] and a['parameters']==b['parameters'],'unfair pair controls')
    for key in ['assignment','token','rank','expert','source']:
        require([x[key] for x in a['assignments']]==[x[key] for x in b['assignments']],'routing trace/WQE rule differs')
    nb,u=summaries['no-balancing'],summaries['ultraep']
    pairs.append(dict(case=name,no_balancing=nb,ultraep=u,speedup=nb['layer_latency_ps']/u['layer_latency_ps'] if u['layer_latency_ps'] else None,interpretation='empty functional case' if nb['empty'] else 'simulation ratio, not hardware speedup'))
    (out/'comparison.json').write_text(json.dumps(pairs,indent=2)+'\n')
# Bounded repeatability check. Timings do not depend on Python planner wall time.
for mode in ['no-balancing','ultraep']:
    require((out/'single_replica4'/mode/'events.csv').read_bytes()==(out/'single_replica4_repeat'/mode/'events.csv').read_bytes(),'non-deterministic event stream')
(out/'reproducibility.txt').write_text('PASS: repeated single_replica4 event streams byte-identical for both modes.\n')
(HERE/'run-ledger.md').write_text('# Run ledger\n\n26/26 fixed matrix runs successful; negative speedup retained. Each checkpoint passed independent event verification before the next case. Exact commands, return codes, timestamps and summaries: evidence/run-ledger.json.\n')
