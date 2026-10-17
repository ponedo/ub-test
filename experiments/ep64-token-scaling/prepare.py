#!/usr/bin/env python3
"""Generate unchanged capacity routing, solve once, adapt shared plan to strategies."""
import argparse,csv,hashlib,importlib.util,json,os,subprocess,sys,time
from collections import Counter
from pathlib import Path
H=Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jain(v):return sum(v)**2/(len(v)*sum(x*x for x in v)) if any(v) else 1.0
p=argparse.ArgumentParser();p.add_argument('--tokens',type=int,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args()
assert 0<a.tokens<=12500 and a.tokens*8<=100000
out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve())
subprocess.run([sys.executable,str(H.parent/'prefill-capacity/stage.py'),'generate','--case',str(out),'--assignments',str(a.tokens*8)],check=True)
b=module('scaling_direct',H.parent/'direct-weight-forward/adapter.py');r=module('scaling_relay',H.parent/'multi-npu-relay/adapter.py')
c=b.normalize(json.loads((out/'planner-input.json').read_text()));b.validate(c)
fixed=json.loads((H/'fixed-config.json').read_text())
for key,value in fixed['normalized_planner_parameters'].items():assert c[key]==value,(key,c[key],value)
for key in ['main_placement','slots']:assert c[key]==fixed[key]
assert all(len(x['experts'])==8 and len(set(x['experts']))==8 for x in c['mapping'])
with (out/'routing.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['token','source_npu','topk_index','expert'])
 for t,row in enumerate(c['mapping']):
  for k,e in enumerate(row['experts']):w.writerow([t,row['source'],k,e])
load=Counter(e for row in c['mapping'] for e in row['experts']);loads=[load[e] for e in range(128)]
(out/'expert-load.json').write_text(json.dumps({'loads':loads,'max':max(loads),'jain':jain(loads),'routing_sha256':sha(out/'routing.csv'),'tokens':a.tokens,'assignments':8*a.tokens},indent=2)+'\n')
params=json.loads((H/'fixed-config.json').read_text())['application_parameters'];relay=json.loads((H/'fixed-config.json').read_text())['relay_parameters']
plans={};wall={};original_solve=b.solve;original_baseline=b.baseline
for mode in ['no-balancing','ultraep']:
 start=time.perf_counter();plan=original_baseline(c) if mode=='no-balancing' else original_solve(c);wall[mode]=time.perf_counter()-start
 if mode=='ultraep':b.check(c,plan)
 plans[mode]=plan;(out/(mode+'-plan.json')).write_text(json.dumps(plan)+'\n')
 # emit receives precisely the measured plan, never solves a second time.
 b.solve=lambda _,plan=plan:plan;b.baseline=lambda _,plan=plan:plan
 b.emit(c,params,mode,out/(mode+'-direct-input'))
 for strategy in (['direct'] if mode=='no-balancing' else ['direct','chunk-streaming']):
  name='no-balancing' if mode=='no-balancing' else strategy
  r.emit(out/(mode+'-direct-input'),relay,strategy,out/name)
assert sha(out/'direct/plan.json')==sha(out/'chunk-streaming/plan.json')
assert sha(out/'direct/assignments.csv')==sha(out/'chunk-streaming/assignments.csv')
for strategy in ['no-balancing','direct','chunk-streaming']:
 cc=json.loads((out/strategy/'config.json').read_text());assert cc['planner_input']==c
(out/'preparation-metrics.json').write_text(json.dumps({'planner_cpu_wall_seconds':wall,'shared_routing_sha256':sha(out/'routing.csv'),'ultraep_plan_sha256':sha(out/'direct/plan.json'),'ultraep_assignments_sha256':sha(out/'direct/assignments.csv')},indent=2)+'\n')
