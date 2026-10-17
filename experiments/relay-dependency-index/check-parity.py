#!/usr/bin/env python3
"""Fresh baseline versus independent C++ treatments, full Debug exact outputs."""
import argparse,hashlib,json,sys,os
from pathlib import Path
H=Path(__file__).resolve().parent; W=H.parents[2]
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
sys.path.insert(0,str(H.parent/'tiered-logging'));from common import differences,sha
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,default=W/'relay-dependency-index-raw/build/pair-layer');p.add_argument('--name',default='parity');p.add_argument('--timed',action='store_true');a=p.parse_args()
raw=W/'relay-dependency-index-raw'/a.name
assert not raw.exists();raw.mkdir(parents=True)
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!='verification_wall_ns'}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
inputs={c:W/'tiered-logging-raw/validation-final/inputs'/c/'input.txt' for c in ['nb-small','direct-small','chunk-small','multichunk-multita']}
inputs['two-stage']=W/'pair-jetty-raw/restored-fixtures/multi4_force/two-stage/input.txt'
rows=[]
for case,inp in inputs.items():
 baseline=None
 for variant,dep,online in [('baseline',None,None),('scan-scan','scan','scan'),('index-scan','index','scan'),('scan-index','scan','index'),('index-index','index','index')]:
  root=raw/case/variant;out=root/'run';out.mkdir(parents=True)
  binary=W/'qwen-model-size-raw/build-capacity-v2/pair-layer' if variant=='baseline' else a.binary
  cmd=[str(binary),'--input='+str(inp),'--out='+str(out),'--logLevel=debug','--jettyMode=pair','--capacityMetrics='+str(out/'simulator-metrics.json')]
  if dep:cmd+=['--dependencyMode='+dep,'--onlineMembershipMode='+online]
  env=dict(os.environ)
  if a.timed and dep:env.update(QWEN_CPU_PROFILE='1',QWEN_CPU_PROFILE_OUT=str(root/'timing.json'),QWEN_PROFILE_HISTORY='')
  r=run(cmd,root/'host',300,case=root,env=env);assert r['status']=='PASS',(case,variant)
  if baseline is None:baseline=out;continue
  if a.timed:
   timing=json.loads((root/'timing.json').read_text());assert timing['complete'] and timing['terminal']
   assert timing['dependency_mode']==dep and timing['online_membership_mode']==online
  checks={}
  for name in ['online-summary.json','validation.json','simulator-metrics.json']:
   checks[name]=differences(stable(json.loads((baseline/name).read_text())),stable(json.loads((out/name).read_text())))
  hashes={}
  files=[x.relative_to(baseline) for x in baseline.rglob('*') if x.is_file() and x.suffix!='.json']
  for name in files:
   hashes[str(name)]=[sha(baseline/name),sha(out/name)];assert hashes[str(name)][0]==hashes[str(name)][1],(case,variant,name)
  assert not any(checks.values()),(case,variant,checks)
  summary=json.loads((out/'online-summary.json').read_text())
  rows.append(dict(case=case,variant=variant,status='PASS',input_sha256=sha(inp),checks=checks,byte_exact_hashes=hashes,layer_latency_ps=summary['layer_latency_ps'],simulator_events=summary['simulator_events'],TA_count=summary['TA_count'],completed_tokens=summary['completed_tokens'],executed_graph_fnv1a64=summary['executed_graph_fnv1a64']))
result=dict(status='PASS',timed=a.timed,excluded_json_fields=['verification_wall_ns'],tests=rows)
(H/(a.name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print('PASS',len(rows),'full Debug comparisons')
