#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve())
b=module('direct',H.parent/'direct-weight-forward/adapter.py');r=module('relay',H.parent/'multi-npu-relay/adapter.py');results=[]
for case in ['nb-small','direct-small','chunk-small','multichunk-multita']:
 source=a.fixtures/case;c=json.loads((source/'config.json').read_text());plan=json.loads((source/'plan.json').read_text());dest=a.out/case
 b.solve=lambda _,plan=plan:plan;b.baseline=lambda _,plan=plan:plan
 params=dict(c['parameters'],weight_strategy='direct')
 # Relay metadata must not be injected into the old direct serialization.
 for key in r.DEFAULT_RELAY:params.pop(key,None)
 params.pop('weight_size_kind',None);params.pop('weight_bytes',None)
 b.emit(c['planner_input'],params,c['mode'],dest/'direct')
 r.emit(dest/'direct',c['relay_parameters'],c['weight_strategy'],dest/'run')
 checks={}
 for name in ['input.txt','assignments.csv','transfers.csv','graph-input.txt','weight-edges.csv','plan.json']:
  old=(source/name).read_bytes();new=(dest/'run'/name).read_bytes();assert old==new,(case,name)
  checks[name]=hashlib.sha256(new).hexdigest()
 results.append(dict(case=case,status='PASS',exact_hashes=checks))
(a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS old input graph byte parity',len(results))
