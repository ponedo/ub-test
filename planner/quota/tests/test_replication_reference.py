#!/usr/bin/env python3
"""Differential execution of the pinned replication kernel's extracted bodies."""
import json,math,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from planner import solve
from checker import check

def require(condition,message):
    if not condition:raise RuntimeError(message)

def run_case(name,g,m,loads,floor,eps='0.01',stage=1):
    # All cases meet upstream's contiguous equally sized main and uniform-slot layout.
    c=dict(schema_version=1,mode='strict-floor',npus=g,experts=g*m,top_k=1,
           main_placement=[e//m for e in range(g*m)],slots=[1]*g,
           mapping=[dict(source=(i+e)%g,experts=[e]) for e,count in enumerate(loads) for i in range(count)],
           min_replica_quota=floor,beta='1.01',allow_zero_main=False,rounding='code')
    command_input=' '.join(map(str,[g,m,1,c['beta'],floor,0,eps,stage]+loads))+'\n'
    run=subprocess.run([str(R/'reference/replication_cpu')],input=command_input,text=True,capture_output=True,check=True,timeout=60)
    upstream=json.loads(run.stdout)
    # Parallel fallback warps may append logs in any order; do not change raw file.
    upstream['probes']=sorted(upstream['probes'],key=lambda p:(-p['dynamic'],-p['store'],p['threshold']))
    ours=solve(c);check(c,ours)
    paper_c=dict(c,rounding='paper');paper=solve(paper_c);check(paper_c,paper)
    def normalize(physical):
        require(len({p['id'] for p in physical})==len(physical),'duplicate physical slot')
        X=[[0]*g for _ in loads];U=[[0]*g for _ in loads];rank_load=[0]*g;slots=[0]*g
        for p in physical:
            e,r=p['expert'],p['rank']
            require(0<=e<len(loads) and 0<=r<g,'reference physical bounds')
            require(X[e][r]==0,'reference duplicate expert/rank');X[e][r]=1
            require(type(p['quota']) is int and p['quota']>=0,'reference quota')
            U[e][r]=p['quota'];rank_load[r]+=p['quota']
            if p['kind']=='replica':slots[r]+=1
            else:require(r==e//m,'reference main moved')
        require([sum(row) for row in U]==loads,'reference expert conservation')
        require(all(X[e][e//m]==1 for e in range(len(loads))),'reference main absent')
        require(all(x<=1 for x in slots),'reference slot overrun')
        return dict(X=X,U=U,rank_load=rank_load,replica_count=sum(slots),slot_usage=slots)
    ref_norm=normalize(upstream['physical']);ours_norm=normalize(ours['physical'])
    require(ref_norm['replica_count']==upstream['replica_count'],'reference replica count')
    require(max(ref_norm['rank_load'])<=upstream['threshold'],'reference threshold witness')
    require(all(q['quota']>=floor for q in ours['physical'] if q['kind']=='replica'),'our configured floor relaxed')
    floor_violations=[p for p in upstream['physical'] if p['kind']=='replica' and p['quota']<floor]
    if not upstream['fast_success']:
        require(not floor_violations,'upstream fallback must keep configured floor')
    for f in upstream['dynamic_floors']:
        require(f['effective']==max(1,math.ceil(f['need']/f['feasible_slots'])),'original dynamic floor formula')
    comparison=dict(name=name,upstream_parameters=dict(beta=c['beta'],epsilon=eps,kernel_stage=stage,configured_floor=floor),
                    upstream=ref_norm,ours_code_bound=ours_norm,ours_paper_bound=dict(threshold=paper['metrics']['chosen_threshold'],target=paper['metrics']['target_threshold'],rank_load=paper['metrics']['final_rank_load']),
                    upstream_threshold=upstream['threshold'],ours_threshold=ours['metrics']['chosen_threshold'],ours_lower_bound=ours['metrics']['target_threshold'],
                    equal_X=ref_norm['X']==ours_norm['X'],equal_U=ref_norm['U']==ours_norm['U'],equal_threshold=upstream['threshold']==ours['metrics']['chosen_threshold'],
                    fast_success=bool(upstream['fast_success']),probes=upstream['probes'],dynamic_floors=upstream['dynamic_floors'],upstream_below_configured_floor=floor_violations)
    out=R/'evidence/replication'/name;out.mkdir(parents=True,exist_ok=True)
    for filename,obj in [('input.json',c),('upstream.json',upstream),('ours.json',ours),('comparison.json',comparison)]:
        (out/filename).write_text(json.dumps(obj,indent=2)+'\n')
    (out/'reference-stdin.txt').write_text(command_input)
    (out/'reference-stdout.txt').write_text(run.stdout)
    return comparison

cases=[
    ('uniform',4,2,[8]*8,1024),
    ('skew',4,2,[41,1,2,3,20,0,0,1],1),
    ('extreme_hot',8,2,[8192]+[0]*15,1024),
    ('floor_sensitive',4,1,[20,0,0,0],1024),
    ('nondivisible',3,2,[17,5,2,0,0,1],2),
    ('fallback',4,8,[100]*8+[0]*24,1),
    ('fallback_floor',4,8,[100]*8+[0]*24,1024),
    ('epsilon_zero',8,2,[8192]+[0]*15,1024,'0'),
    ('stage_zero',4,8,[100]*8+[0]*24,1,'0.01',0),
]
results={args[0]:run_case(*args) for args in cases}
require(results['uniform']['equal_X'] and results['uniform']['equal_U'],'uniform X/U mismatch')
require(results['skew']['fast_success'] and len(results['skew']['probes'])==2,'fast retry coverage')
require(results['extreme_hot']['fast_success'] and results['extreme_hot']['upstream_threshold']==1046,'fast epsilon threshold')
require(results['epsilon_zero']['upstream_threshold']==1035,'epsilon-zero threshold')
require(results['floor_sensitive']['upstream_below_configured_floor'] and results['floor_sensitive']['ours_code_bound']['replica_count']==0,'floor divergence coverage')
for name in ['fallback','fallback_floor','stage_zero']:
    r=results[name]
    require(not r['fast_success'] and sum(p['dynamic'] for p in r['probes'])==3,'three fast failures before fallback')
    require(any(not p['dynamic'] and not p['store'] for p in r['probes']),'parallel fallback probes missing')
require(results['fallback']['upstream']==results['stage_zero']['upstream'],'stage 0/1 placement discrepancy')
require(results['fallback']['upstream_threshold']==503 and results['fallback_floor']['upstream_threshold']==800,'fallback witness regression')
report=dict(status='PASS',validation_level='CPU semantic execution of extracted upstream replication/search/materialization bodies; not GPU execution',cases=results)
(R/'evidence/replication-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS',replication_scenarios=len(results),fast_retry=True,epsilon=True,dynamic_floor_below_configured=True,fallback=True,kernel_stages=[0,1]),indent=2))
