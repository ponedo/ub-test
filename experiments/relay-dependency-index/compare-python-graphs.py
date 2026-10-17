#!/usr/bin/env python3
"""Exact whole-artifact comparisons, including every ordered dependency list."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('preflight',ROOT/'experiments/tiered-logging/preflight.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--accepted',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
old=json.loads((a.accepted/'config.json').read_text());new=json.loads((a.new/'config.json').read_text());assert old==new
checks={}
for name in ('input.txt','config.json','transfers.csv','weight-edges.csv'):
    before=(a.accepted/name).read_bytes();after=(a.new/name).read_bytes();assert before==after,name
    checks[name]=dict(exact_bytes_equal=True,sha256=hashlib.sha256(after).hexdigest())
p1=json.loads((a.accepted/'plan.json').read_text());p2=json.loads((a.new/'plan.json').read_text());timing={}
for plan,key in ((p1,'accepted'),(p2,'new')):timing[key]=plan.pop('cpu_wall_ns',None)
assert p1==p2,'planner semantic difference'
canonical=m.canonical_graph(new['transfers']).encode();weight=[x for x in new['transfers'] if x['stage']==2]
result=dict(status='PASS',files=checks,planner_exact_except_cpu_wall_ns=True,planner_diagnostic_cpu_wall_ns=timing,all_transfers_and_ordered_dependency_lists_equal=old['transfers']==new['transfers'],transfers=len(new['transfers']),weight_wqes=len(weight),dependency_count=sum(len(x['dependencies']) for x in weight),weight_bytes=sum(x['bytes'] for x in weight),weight_tas=sum((x['bytes']+new['runtime']['segment_bytes']-1)//new['runtime']['segment_bytes'] for x in weight),canonical_graph_sha256=hashlib.sha256(canonical).hexdigest(),canonical_graph_fnv1a64=m.fnv1a64(canonical))
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
