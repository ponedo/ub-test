#!/usr/bin/env python3
"""Same-input summary and full-debug exact-time parity for diagnostic-only app.
No optimization allowed: timers cannot change the event stream or native totals.
"""
import argparse,hashlib,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run
sys.path.insert(0,str(H.parent/'tiered-logging'))
from common import differences
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!="verification_wall_ns"}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--instrumented',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.raw.exists():raise RuntimeError('fresh directory required')
a.raw.mkdir(parents=True);rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for case in ['nb-small','direct-small','chunk-small','multichunk-multita']:
 for mode in ['summary','debug']:
  roots=[]
  for variant,binary in [('control',a.control),('timed',a.instrumented)]:
   root=a.raw/case/mode/variant;out=root/'run';out.mkdir(parents=True);env=dict(os.environ)
   if variant=='timed':env.update(QWEN_CPU_PROFILE='1',QWEN_CPU_PROFILE_OUT=str((root/'timing.json').resolve()))
   command=[str(binary.resolve()),'--input='+str((a.inputs/case/'input.txt').resolve()),'--out='+str(out.resolve()),'--capacityMetrics='+str((out/'simulator-metrics.json').resolve()),'--jettyMode=pair','--logLevel='+mode]
   resource=run(command,root/'host',300,case=root,env=env)
   if resource['status']!='PASS':raise RuntimeError('small regression failed '+str(root))
   roots.append(out)
  checks={}
  for name in ['online-summary.json','validation.json','simulator-metrics.json']:
   left,right=(json.loads((r/name).read_text()) for r in roots);diff=differences(stable(left),stable(right));checks[name]=dict(equal=not diff,differences=diff)
  if mode=='debug':
   for name in ['events.csv','ta-identity.csv','executed-transfers.csv','received-payloads.bin','payload-index.csv']:
    hs=[sha(r/name) for r in roots];checks[name]=dict(equal=hs[0]==hs[1],sha256=hs)
  s=json.loads((roots[0]/'online-summary.json').read_text())
  row=dict(case=case,mode=mode,status='PASS' if all(x['equal'] for x in checks.values()) else 'FAIL',input_sha256=sha(a.inputs/case/'input.txt'),checks=checks,simulator_events=s['simulator_events'],layer_latency_ps=s['layer_latency_ps'],TA_count=s['TA_count'],remote_WQEs=s['remote_WQEs'],packet_tx_per_node=s['packet_tx_per_node'],combine_fnv1a64=s['combine_fnv1a64'])
  rows.append(row)
  if row['status']!='PASS':raise RuntimeError('event/model parity failure '+case)
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(dict(status='PASS',excluded_json_fields=['verification_wall_ns'],tests=rows),indent=2)+'\n')
print('PASS exact small-case event/time/output parity',len(rows))
