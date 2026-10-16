#!/usr/bin/env python3
import argparse,importlib.util,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','planner','adapter','verify']);p.add_argument('--case',required=True);p.add_argument('--assignments',type=int,default=50000);p.add_argument('--mode',choices=['no-balancing','ultraep'],default='no-balancing');a=p.parse_args();out=Path(a.case);out.mkdir(parents=True,exist_ok=True)
if a.stage=='generate':
 if a.assignments%8 or a.assignments<=0:raise ValueError('A must be positive and divisible by top-k8')
 if 2*a.assignments+20000>2**20:raise ValueError('wire Jetty ID limit: 2*A+20000 exceeds 20-bit task namespace; no remapping authorized')
 rng=random.Random(20261016);weights=[(e+1)**-1.1 for e in range(128)];mapping=[]
 for t in range(a.assignments//8):
  experts=[]
  while len(experts)<8:
   e=rng.choices(range(128),weights=weights,k=1)[0]
   if e not in experts:experts.append(e)
  mapping.append(dict(source=t%64,experts=experts))
 c=dict(schema_version=1,npus=64,experts=128,top_k=8,main_placement=[e//2 for e in range(128)],slots=[2]*64,mapping=mapping,beta='1.01',min_replica_quota=1024)
 (out/'planner-input.json').write_text(json.dumps(c)+'\n');print('synthetic T',len(mapping),'A',len(mapping)*8)
elif a.stage in ['planner','adapter']:
 base=module('capacity_direct',REPO/'experiments/direct-weight-forward/adapter.py');c=base.normalize(json.loads((out/'planner-input.json').read_text()));base.validate(c)
 if a.stage=='planner':
  plan=base.solve(c) if a.mode=='ultraep' else base.baseline(c)
  if a.mode=='ultraep':base.check(c,plan)
  (out/'measured-plan.json').write_text(json.dumps(plan)+'\n');print('planner mode',a.mode,'physical',len(plan['physical']))
 else:
  plan=json.loads((out/'measured-plan.json').read_text());base.solve=lambda _:plan;base.baseline=lambda _:plan
  base.emit(c,{},a.mode,out/'direct-input')
  relay=module('capacity_relay',REPO/'experiments/multi-npu-relay/adapter.py');relay.emit(out/'direct-input',{},'chunk-streaming' if a.mode=='ultraep' else 'direct',out/'run');print('adapter complete')
else:
 verify=module('capacity_verify',REPO/'experiments/multi-npu-relay/verify.py');summary=verify.verify(out/'run');(out/'run/summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('strict verify PASS',summary['tokens'],summary['assignments'],summary['layer_latency_ps'])
