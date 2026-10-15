#!/usr/bin/env python3
"""Accepted fixed-source goldens, integration differentials, independent invariants."""
import copy,itertools,json,random,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from planner import solve,InputError
from checker import check,InvariantError
from upstream import repair_margins
OUT=R/'evidence/compatible';OUT.mkdir(parents=True,exist_ok=True)
def need(ok,message):
    if not ok:raise RuntimeError(message)
def config(g,m,loads,slots=1,**kw):
    c=dict(schema_version=1,npus=g,experts=g*m,top_k=1,main_placement=[x//m for x in range(g*m)],slots=[slots]*g,
           mapping=[dict(source=(e+i)%g,experts=[e]) for e,n in enumerate(loads) for i in range(n)],
           beta='1.01',min_replica_quota=1024,allow_zero_main=False,rounding='code')
    c.update(kw);return c

def normalize_physical(items):
    return sorted([{k:p[k] for k in ['id','expert','rank','kind','quota']} for p in items],key=lambda p:p['id'])

def run(name,c,save=True):
    o=solve(c);check(c,o)
    raw=o['upstream']['replication']
    need(normalize_physical(o['physical'])==normalize_physical(raw['physical']),'placement mismatch')
    # Separately invoke the pinned source executable with saved stdin. This is an
    # integration check of the reused engine, not an independent second algorithm.
    direct=subprocess.run([str(R/'reference/replication_cpu')],input=o['upstream']['replication_stdin'],text=True,capture_output=True,check=True,timeout=60)
    ref=json.loads(direct.stdout)
    need(normalize_physical(ref['physical'])==normalize_physical(o['physical']),'direct source X/U differ')
    need(sorted(ref['probes'],key=lambda p:(-p['dynamic'],-p['store'],p['threshold']))==raw['probes'],'source probe drift')
    need(ref['threshold']==raw['threshold'] and ref['fast_success']==raw['fast_success'] and ref['dynamic_floors']==raw['dynamic_floors'],'source threshold/path/floor drift')
    strict_c=dict(c,mode='strict-floor',locality_aware=True)
    if any(v>c['experts'] for v in c['slots']):
        strict={'unsupported':'legacy strict-floor rejects per-rank slots > E'}
    else:
        strict=solve(strict_c);check(strict_c,strict)
    classification='integer-conservation correction' if o['metrics']['repaired_assignments'] else 'exact placement and source quota'
    summary=dict(classification=classification,upstream_metrics=o['metrics'],strict_metrics=strict.get('metrics'),strict_unsupported=strict.get('unsupported'),
                 same_strict_placement=normalize_physical(o['physical'])==normalize_physical(strict['physical']) if 'physical' in strict else None,
                 token_identity_limit='deterministic input ordinals; GPU atomic ordering is not compared')
    if save:
        d=OUT/name;d.mkdir(exist_ok=True)
        for filename,value in [('input.json',c),('upstream-compatible.json',o),('strict-floor.json',strict),('comparison.json',summary)]:
            (d/filename).write_text(json.dumps(value,indent=2)+'\n')
        (d/'direct-reference-stdout.txt').write_text(direct.stdout)
    return o,summary

cases={};summaries={}
gold=json.loads((R/'tests/upstream-goldens.json').read_text())
for name,entry in gold['cases'].items():
    c=dict(entry['input'],mode='upstream-compatible',oracle_epsilon=entry['parameters']['epsilon'],kernel_stage=entry['parameters']['kernel_stage'])
    o,s=run(name,c);summaries[name]=s;cases[name]=o
    expected=entry['upstream']
    need(normalize_physical(o['physical'])==normalize_physical(expected['physical']),'accepted golden X/U changed: '+name)
    need(o['upstream']['replication']['threshold']==expected['threshold'],'accepted threshold changed')
    need(o['upstream']['replication']['dynamic_floors']==expected['dynamic_floors'],'accepted dynamic floor changed')
need(sum(cases['extreme_hot']['metrics']['slot_usage'])==7 and max(cases['extreme_hot']['metrics']['final_rank_load'])==1046,'extreme-hot acceptance')

more={
 'shared_fallback':config(65,4,[3]*4+[0]*256,min_replica_quota=1,beta='1',oracle_epsilon='0'),
 'empty':config(4,2,[0]*8),
 'slots_zero':config(4,2,[19]+[0]*7,slots=0),
 'extra_unused_slots':config(2,1,[3,0],slots=5),
 'one_rank':config(1,3,[3,0,2],slots=2),
 'multiple_slots':config(4,8,[100]*8+[0]*24,slots=2,min_replica_quota=1),
 'float32_boundary':config(4,1,[4,0,0,0],beta='1.00000001',oracle_epsilon='0.00000001',min_replica_quota=1),
 'zero_main':config(2,2,[1,1,0,0],beta='1',oracle_epsilon='0',allow_zero_main=True,min_replica_quota=1),
 'positive_main':config(2,2,[1,1,0,0],beta='1',oracle_epsilon='0',min_replica_quota=1),
 'no_locality':config(4,2,[11,1,0,0,0,0,0,1],locality_aware=False,min_replica_quota=1),
 'margin_counterexample':config(4,1,[0]*4,beta='1',oracle_epsilon='0',min_replica_quota=1,mapping=[dict(source=2,experts=[0]),dict(source=3,experts=[0])]),
 'main_last_order':config(4,1,[0]*4,beta='1',oracle_epsilon='0',min_replica_quota=1,locality_aware=False,mapping=[dict(source=1,experts=[3]),dict(source=2,experts=[3])]),
}
for g in [33,64,65,72]:
    more['g'+str(g)]=config(g,1,[g*4]+[0]*(g-1),beta='1',oracle_epsilon='0')
more['e512']=config(64,8,[256]+[0]*511,beta='1',oracle_epsilon='0')
for name,c in more.items():
    o,s=run(name,c);summaries[name]=s;cases[name]=o
    if name.startswith('g') or name=='e512':
        need(o['metrics']['final_rank_load']==[4]*c['npus'],'extended-rank analytical load witness')
        need(sum(o['metrics']['slot_usage'])==c['npus']-1,'extended-rank all replicas')
        need(max(p['rank'] for p in o['physical'] if p['kind']=='replica')==c['npus']-1,'high rank not covered')
need(cases['shared_fallback']['metrics']['path']=='fallback' and max(cases['shared_fallback']['metrics']['final_rank_load'])==4,'shared-state fallback')
need(max(cases['multiple_slots']['metrics']['slot_usage'])==2,'multiple slots unused')
need(cases['float32_boundary']['metrics']['target_threshold']==1,'float32 converted to exact Fraction incorrectly')
need(cases['margin_counterexample']['metrics']['repaired_assignments']==1,'rounding correction not exercised')
a=cases['margin_counterexample']['upstream']['quota_repairs'][0]
need(a['raw']==[[0,0],[0,0],[1,0],[1,0]] and a['corrected']==[[0,0],[0,0],[0,1],[1,0]],'minimal correction changed')
for name in ['slots_zero','one_rank']:
    need(cases[name]['upstream']['replication']['threshold'] is None and cases[name]['metrics']['path']=='bypass','bypass convention')

random_cases=[]
for seed in range(60):
    r=random.Random(812000+seed);g=r.randint(2,8);m=r.randint(1,4);k=r.randint(1,min(3,g*m))
    c=config(g,m,[0]*(g*m),slots=r.randint(0,min(3,g*m)),min_replica_quota=r.choice([1,2,1024]),top_k=k,allow_zero_main=bool(seed%2),locality_aware=bool(seed%3),oracle_epsilon=r.choice(['0','.01','.1']))
    c['mapping']=[dict(source=r.randrange(g),experts=r.sample(range(g*m),k)) for _ in range(r.randint(0,40))]
    o,_=run('random',c,save=False)
    random_cases.append(dict(seed=seed,input=c,metrics=o['metrics'],correction=o['metrics']['repaired_assignments']))

# Independent enumeration of feasible quota allocations for tiny upstream inputs.
def parts(total,n):
    if n==1:yield (total,);return
    for v in range(total+1):
        for rest in parts(total-v,n-1):yield (v,)+rest
small=[]
for seed in range(20):
    r=random.Random(1900+seed);g=r.randint(2,3);loads=[r.randint(0,3) for _ in range(g)]
    c=config(g,1,loads,min_replica_quota=1,beta='1',oracle_epsilon='0')
    o=solve(c);check(c,o);options=[]
    for e,count in enumerate(loads):options.append([v for v in parts(count,g) if not count or v[e]>=1])
    best=sum(loads)
    for plan in itertools.product(*options):
        if any(sum(v[r]>0 and e!=r for e,v in enumerate(plan))>1 for r in range(g)):continue
        best=min(best,max(sum(v[r] for v in plan) for r in range(g)))
    actual=max(o['metrics']['final_rank_load']);need(actual>=best,'exhaustive feasibility contradiction')
    small.append(dict(seed=seed,input=c,optimum=best,actual=actual))

# Exhaust the tiny rounding repair's feasible transportation tables independently.
repair_optima=[]
for a in range(4):
 for b in range(4):
  for q0 in range(a+b+1):
   total=a+b
   if not total:continue
   def rounded(d):
    row=[d*q0//total,d*(total-q0)//total];rem=d-sum(row)
    if rem:row[0 if (d*q0%total)>=(d*(total-q0)%total) else 1]+=1
    return row
   raw=[rounded(a),rounded(b)]
   fixed,audit=repair_margins(raw,[a,b],[0,1],[q0,total-q0],False)
   candidates=[[[x,a-x],[q0-x,b-(q0-x)]] for x in range(a+1) if 0<=q0-x<=b]
   dist=lambda v:sum(abs(v[r][j]-raw[r][j]) for r in range(2) for j in range(2))
   need(dist(fixed)==min(map(dist,candidates)),'repair not minimum-distance transport')
   repair_optima.append([a,b,q0])

base=more['margin_counterexample'];invalid=[]
for key,value in [('main_placement',[1,0,2,3]),('slots',[1,0,1,1]),('npus',73),('experts',513),('kernel_stage',2),('oracle_epsilon','nan'),('reroute_mode','dense-interleave'),('ep_domains',2),('ep_degree',2)]:
    c=copy.deepcopy(base);c[key]=value;invalid.append(c)
c=config(72,1,[0]*72,slots=8);invalid.append(c) # G * slots > 512
c=config(3,1,[0]*3);c['experts']=4;c['main_placement']=[0,1,2,2];invalid.append(c)
for c in invalid:
    try:solve(c)
    except InputError:pass
    else:raise RuntimeError('unsupported upstream input silently accepted')
# The legacy general layout remains available explicitly.
c=dict(base,mode='strict-floor',main_placement=[1,0,2,3],slots=[1,0,1,1]);check(c,solve(c))
mutated=copy.deepcopy(cases['margin_counterexample']);mutated['upstream']['quota_repairs'][0]['minimum_moved_assignments']=0
try:check(base,mutated)
except InvariantError:pass
else:raise RuntimeError('unreported correction accepted')
report=dict(status='PASS',scenario_count=len(summaries),accepted_goldens=len(gold['cases']),cases=summaries,random=random_cases,exhaustive=small,
            repair_exhaustive_cases=len(repair_optima),unsupported_inputs_rejected=len(invalid),placement_differences=0,
            classifications=dict(exact=sum(s['classification'].startswith('exact') for s in summaries.values()),integer_correction=sum(s['classification'].startswith('integer') for s in summaries.values()),substantial_placement_difference=0,
                                 unaligned=['GPU atomic token ordinal identity','multi-domain layout and noncontiguous/nonuniform inputs rejected']),
            independence='accepted prior-commit goldens + analytical large-rank witnesses + independent invariants/enumeration; direct source re-execution shares production engine and is an integration check')
(OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','scenario_count','accepted_goldens','repair_exhaustive_cases','unsupported_inputs_rejected','placement_differences','classifications']},indent=2))
