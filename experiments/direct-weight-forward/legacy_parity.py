#!/usr/bin/env python3
"""Cross-executor parity for the legacy two-matrix NoBalancing formula."""
import argparse,json,subprocess,sys
from pathlib import Path
from adapter import KEYS,require
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.out).resolve();case=root/'legacy-parity';case.mkdir(exist_ok=True)
c=json.loads((root/'two_matrix4/no-balancing/config.json').read_text());pc=c['planner_input'];params=c['parameters'];head=dict(params,npus=pc['npus'],experts=pc['experts'],top_k=pc['top_k'],tokens=len(pc['mapping']))
legacy=dict(head,placement=pc['main_placement'],mapping=pc['mapping'])
(case/'config.json').write_text(json.dumps(legacy,indent=2)+'\n')
lines=[' '.join(str(head[k]) for k in KEYS),' '.join(map(str,pc['main_placement']))]+[' '.join(map(str,[r['source']]+r['experts'])) for r in pc['mapping']]
(case/'input.txt').write_text('\n'.join(lines)+'\n')
subprocess.run([sys.executable,str(Path(__file__).resolve().parent.parent/'no-balancing-layer/cases.py'),'--config',str(case/'config.json'),'--out',str(case)],check=True)
command=[sys.executable,'./ns3','run','--no-build',f'no-balancing-layer --input={case}/input.txt --out={case}']
with (case/'console.txt').open('w') as f:subprocess.run(command,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT,check=True)
# Run the original independent verifier against its complete native input artifacts.
script=Path(__file__).resolve().parent.parent/'no-balancing-layer/verify.py'
result=subprocess.check_output([sys.executable,str(script),str(case)],text=True);old=json.loads(result)
(case/'summary.json').write_text(result)
new=json.loads((root/'two_matrix4/no-balancing/summary.json').read_text())
require(old['layer_latency_ps']==new['layer_latency_ps'],'legacy executor latency drift')
require(old['per_npu_assignments']==new['per_npu_load'],'legacy executor load drift')
report=dict(status='PASS',command=command,layer_latency_ps=new['layer_latency_ps'],same_npu_loads=True,model='two-matrix, identical trace and all common parameters')
(root/'legacy-parity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
