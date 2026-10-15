#!/usr/bin/env python3
import argparse,json,os,subprocess,sys
from pathlib import Path
from cases import generate,emit
from verify import verify,require
p=argparse.ArgumentParser();p.add_argument('--ns3',required=True);p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=True)
specs=[('n4',4,None,'uniform'),('n8',8,None,'uniform'),('n64',64,None,'uniform'),('skew4',4,None,'skew'),('empty4',4,0,'uniform'),('local4',4,None,'local'),('custom4',4,7,'uniform'),('n4-repeat',4,None,'uniform')]
ledger=[]
for name,n,t,mode in specs:
    case=root/name;c=generate(n=n,t=t,mode=mode)
    if name=='custom4':
        c.update(model_dim=257,ff_dim=769,segment_bytes=256,peak_gflops=800,util_permille=625,setup_ns=75,link_gbps=80,link_delay_ns=30)
        c['placement']=[(x*3+1)%4 for x in range(c['experts'])]
        for token,row in enumerate(c['mapping']):row['source']=0 if token<5 else 2
    emit(c,case)
    cmd=[sys.executable,'./ns3','run','--no-build',f'no-balancing-layer --input={case}/input.txt --out={case}']
    with open(case/'console.txt','w') as f:r=subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError(f'{name}: simulation failed {r.returncode}; see console')
    summary=verify(case);(case/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Run optimized verification too; any failure stops before the next scale.
    with open(case/'summary-optimized.json','w') as f:subprocess.run([sys.executable,'-O',str(Path(__file__).with_name('verify.py')),str(case)],stdout=f,check=True)
    ledger.append(dict(case=name,status='passed',command=cmd,**summary))
    (root/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(name,summary['layer_latency_ps'],flush=True)
require((root/'n4/events.csv').read_bytes()==(root/'n4-repeat/events.csv').read_bytes(),'same-seed event replay differs')
(root/'reproducibility.txt').write_text('PASS: n4 and n4-repeat event CSVs byte-identical; same seed and config.\n')
