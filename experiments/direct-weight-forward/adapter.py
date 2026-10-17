#!/usr/bin/env python3
"""Convert an accepted Planner plan into the explicit ns3 execution contract."""
import csv,json,sys
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'planner/quota'))
from planner import solve,normalize,validate
from checker import check
KEYS=['npus','experts','top_k','tokens','model_dim','ff_dim','dtype_bytes','segment_bytes','peak_gflops','util_permille','setup_ns','seed','link_gbps','link_delay_ns']
DEFAULT=dict(model_dim=64,ff_dim=128,dtype_bytes=2,segment_bytes=1024,peak_gflops=1000,util_permille=500,setup_ns=100,seed=20261015,link_gbps=100,link_delay_ns=20,matrices=3,planning_ns=200,reroute_ns=100,weight_completion_ns=0,weight_strategy='direct')
def require(ok,message):
    if not ok:raise ValueError(message)
def baseline(c):
    n,e=c['npus'],c['experts'];h=c['main_placement'];counts=Counter(x for row in c['mapping'] for x in row['experts']);physical=[];ids={};offset=0
    for r in range(n):
        for slot,x in enumerate(x for x in range(e) if h[x]==r):
            pid=offset+slot;ids[x]=pid;physical.append(dict(id=pid,expert=x,rank=r,kind='main',slot=slot,quota=counts[x],weight_source_rank=r,weight_source_physical=pid))
        offset+=h.count(r)+c['slots'][r]
    return dict(physical=physical,token_mapping=[dict(token=t,source=row['source'],logical_experts=row['experts'],physical_experts=[ids[x] for x in row['experts']]) for t,row in enumerate(c['mapping'])],weight_dependencies=[])
def emit(c,parameters,mode,out):
    require(mode in ['no-balancing','ultraep'],'execution mode');c=normalize(c);validate(c)
    require(c['mode']=='upstream-compatible','forward requires accepted upstream-compatible planner')
    params=dict(DEFAULT,**parameters);require(params['weight_strategy']=='direct','relay strategy not implemented')
    for key in DEFAULT:
        if key!='weight_strategy':require(type(params[key]) is int and params[key]>=0,'integer parameter '+key)
    require(params['matrices'] in [2,3],'two/three matrix model')
    for key,limit in dict(model_dim=16384,ff_dim=65536,dtype_bytes=8,segment_bytes=65536,peak_gflops=10000000,util_permille=1000,link_gbps=10000).items():require(1<=params[key]<=limit,key)
    for key in ['planning_ns','reroute_ns','weight_completion_ns','setup_ns']:require(params[key]<=100000000,key)
    require(params['link_delay_ns']<=1000000 and params['seed']<=2**32-1,'network/seed bounds')
    # Activation dtype remains independent from transmitted expert weights.
    weight_dtype=params.get('weight_dtype_bytes',params['dtype_bytes'])
    require(type(weight_dtype) is int and 1<=weight_dtype<=8,'weight dtype bytes')
    formula=params['matrices']*params['model_dim']*params['ff_dim']*weight_dtype
    weight_bytes=params.get('weight_bytes',formula);require(type(weight_bytes) is int and 0<weight_bytes<=64*1024*1024,'weight size')
    params['weight_bytes']=weight_bytes;params['weight_size_kind']='matrix_exact' if weight_bytes==formula else 'synthetic_override'
    plan=solve(c) if mode=='ultraep' else baseline(c)
    if mode=='ultraep':check(c,plan)
    physical=plan['physical'];byid={p['id']:p for p in physical};assignments=[]
    for row in plan['token_mapping']:
        require(row['logical_experts']==c['mapping'][row['token']]['experts'],'router unchanged')
        for rank,(expert,pid) in enumerate(zip(row['logical_experts'],row['physical_experts'])):
            p=byid[pid];require(p['expert']==expert,'physical identity');assignments.append(dict(assignment=len(assignments),token=row['token'],rank=rank,expert=expert,physical=pid,source=row['source'],target=p['rank']))
    counts=Counter(a['physical'] for a in assignments)
    require(all(counts[p['id']]==p['quota'] for p in physical),'adapter quota')
    deps={d['to_physical']:d for d in plan['weight_dependencies']}
    for p in physical:
        if p['kind']=='replica':require(p['id'] in deps and deps[p['id']]['from_physical']==p['weight_source_physical'],'adapter dependency')
    token_bytes=params['model_dim']*params['dtype_bytes']
    payload_budget=params.get('payload_budget_bytes',256*1024**2);weight_limit=params.get('weight_task_limit',20000)
    require(type(payload_budget) is int and 0<payload_budget<=8*1024**3,'payload budget range')
    require(type(weight_limit) is int and 0<weight_limit<=1000000,'weight task limit range')
    require(len(deps)<=weight_limit,'weight task count bound')
    logical_bytes=len(assignments)*token_bytes*2+len(deps)*weight_bytes
    require(logical_bytes<2**64,'payload arithmetic overflow')
    require(len(assignments)<=100000 and logical_bytes<=payload_budget,'payload safety bound')
    transfers=[]
    for stage in [0,1]:
        for a in assignments:transfers.append(dict(task=len(transfers),stage=stage,id=a['assignment'],source=a['source'] if stage==0 else a['target'],target=a['target'] if stage==0 else a['source'],physical=a['physical'],bytes=token_bytes))
    for p in physical:
        if p['kind']=='replica':transfers.append(dict(task=len(transfers),stage=2,id=p['id'],source=p['weight_source_rank'],target=p['rank'],physical=p['id'],bytes=weight_bytes))
    runtime=dict(params,planning_ns=params['planning_ns'] if mode=='ultraep' else 0,reroute_ns=params['reroute_ns'] if mode=='ultraep' else 0)
    config=dict(planner_input=c,parameters=params,runtime=runtime,mode=mode,assignments=assignments,transfers=transfers)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for name,value in [('config.json',config),('plan.json',plan)]: (out/name).write_text(json.dumps(value,indent=2)+'\n')
    head=dict(params,npus=c['npus'],experts=c['experts'],top_k=c['top_k'],tokens=len(c['mapping']))
    lines=[' '.join(str(head[key]) for key in KEYS),' '.join(map(str,[params['matrices'],weight_bytes,runtime['planning_ns'],runtime['reroute_ns'],params['weight_completion_ns'],int(mode=='ultraep'),0,len(physical)])),' '.join(map(str,c['main_placement']))]
    for p in physical:lines.append(' '.join(map(str,[p['id'],p['expert'],p['rank'],int(p['kind']=='replica'),p['quota'],p['weight_source_physical'],p['weight_source_rank']])))
    for row in plan['token_mapping']:
        values=[row['source']]
        for x,pid in zip(row['logical_experts'],row['physical_experts']):values.extend([x,pid])
        lines.append(' '.join(map(str,values)))
    (out/'input.txt').write_text('\n'.join(lines)+'\n')
    for name,rows in [('assignments.csv',assignments),('transfers.csv',transfers)]:
        with (out/name).open('w',newline='') as f:
            if rows:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return config,plan
