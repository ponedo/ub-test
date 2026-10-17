#!/usr/bin/env python3
"""Guarded original fault suite plus one accepted Qwen30B Zipf regression."""
import argparse, hashlib, json, os, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent / 'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser()
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--lib',type=Path,required=True)
p.add_argument('--fault-inputs',type=Path,required=True)
p.add_argument('--zipf-input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,LD_LIBRARY_PATH=str(a.lib.resolve()))
r=run([sys.executable,H.parent/'qwen3-model-size/test-faults.py','--binary',a.binary.resolve(),'--inputs',a.fault_inputs.resolve(),'--out',a.out/'faults'],a.out/'fault-host',3600,case=a.out,env=env)
if r['status']!='PASS':raise RuntimeError('original fault suite failed or stopped by protection')
faults=json.loads((a.out/'faults/results.json').read_text())
out=a.out/'zipf-run';out.mkdir()
r2=run([a.binary.resolve(),'--input='+str((a.zipf_input/'input.txt').resolve()),'--out='+str(out.resolve()),'--logLevel=summary','--jettyMode=pair','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000','--capacityMetrics='+str((out/'simulator-metrics.json').resolve())],a.out/'zipf-host',3600,case=a.out,env=env)
if r2['status']!='PASS':raise RuntimeError('Zipf regression failed or stopped by protection')
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!='verification_wall_ns'}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
proofs={}
for name in ['online-summary.json','validation.json','simulator-metrics.json']:
 old=(a.zipf_input/name).read_bytes();new=(out/name).read_bytes()
 if stable(json.loads(old))!=stable(json.loads(new)):raise ValueError('regression mismatch: '+name)
 proofs[name]={'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),'equal_except_verification_wall_ns':True}
summary={'status':'PASS','faults':faults,'zipf_qwen30b_nb_256':{'status':'PASS','checks':proofs},'fault_host':r,'zipf_host':r2}
(a.out/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
print('PASS: original failure injections and unchanged Qwen30B Zipf NB 256')
