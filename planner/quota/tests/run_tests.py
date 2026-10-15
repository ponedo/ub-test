#!/usr/bin/env python3
import copy,itertools,json,random,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from planner import solve,decompose,oracle,from_no_balancing,InputError
from checker import check,InvariantError
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
def require(ok,msg):
 if not ok:raise RuntimeError(msg)
def config(n,e,rows,slots=1,floor=1,beta='1.01',placement=None,zero=False):
 return dict(schema_version=1,npus=n,experts=e,top_k=len(rows[0]['experts']) if rows else 1,main_placement=placement if placement is not None else [x%n for x in range(e)],slots=[slots]*n,mapping=rows,min_replica_quota=floor,beta=beta,allow_zero_main=zero,rounding='paper')
def rows(loads,n):return [dict(source=(i+x)%n,experts=[x]) for x,amount in enumerate(loads) for i in range(amount)]
def save(name,c):
 o=solve(c);check(c,o);p=OUT/name;p.mkdir(exist_ok=True);(p/'input.json').write_text(json.dumps(c,indent=2)+'\n');(p/'output.json').write_text(json.dumps(o,indent=2)+'\n');return o
cases={
 'uniform':config(4,8,rows([8]*8,4)),
 'skew':config(4,8,rows([41,1,2,3,20,0,0,1],4)),
 'extreme_hot':config(8,16,rows([8192]+[0]*15,8),floor=1024),
 'slots_insufficient':config(4,4,rows([31,0,0,0],4),slots=0),
 'empty':config(4,8,[]),
 'nondivisible':config(3,6,rows([17,5,2,0,0,1],3),floor=2),
 'zero_main_allowed':config(2,2,rows([1,1],2),beta='1',placement=[0,0],zero=True),
 'positive_main':config(2,2,rows([1,1],2),beta='1',placement=[0,0]),
 'paper_floor':config(4,4,rows([20,0,0,0],4),floor=1024),
}
no_balancing=json.loads((ROOT.parents[1]/'experiments/no-balancing-layer/evidence/n64/config.json').read_text())
cases['n64_adapter']=from_no_balancing(no_balancing,slots=2,min_quota=1)
summary={name:save(name,c)['metrics'] for name,c in cases.items()}
# Independent exhaustive mathematical enumeration; no oracle/greedy code reused.
def compositions(v,n):
 if n==1:yield (v,);return
 for first in range(v+1):
  for rest in compositions(v-first,n-1):yield (first,)+rest
def optimum(c):
 n,e=c['npus'],c['experts'];loads=[sum(x in row['experts'] for row in c['mapping']) for x in range(e)];options=[]
 for x,count in enumerate(loads):
  h=c['main_placement'][x];valid=[]
  for v in compositions(count,n):
   if count and not c['allow_zero_main'] and v[h]<1:continue
   if any(0<v[r]<c['min_replica_quota'] for r in range(n) if r!=h):continue
   valid.append(v)
  options.append(valid)
 best=sum(loads)
 for allocation in itertools.product(*options):
  if any(sum(v[r]>0 and c['main_placement'][x]!=r for x,v in enumerate(allocation))>c['slots'][r] for r in range(n)):continue
  best=min(best,max(sum(v[r] for v in allocation) for r in range(n)))
 return best
fuzz=[];gaps=[]
for seed in range(250):
 r=random.Random(seed);n=r.randint(1,6);e=r.randint(1,10);k=r.randint(1,min(3,e));t=r.randint(0,60)
 c=config(n,e,[dict(source=r.randrange(n),experts=r.sample(range(e),k)) for _ in range(t)],floor=r.choice([1,2,5,1024]),placement=[r.randrange(n) for _ in range(e)],zero=bool(seed%2));c['slots']=[r.randint(0,min(3,e)) for _ in range(n)]
 o=solve(c);check(c,o);again=solve(c);o.pop('cpu_wall_ns');again.pop('cpu_wall_ns');require(o==again,'non-deterministic plan');fuzz.append(seed)
for seed in range(80):
 r=random.Random(1000+seed);n=r.randint(2,3);e=r.randint(1,3);load=[r.randint(0,3) for _ in range(e)]
 c=config(n,e,rows(load,n),floor=r.randint(1,2),placement=[r.randrange(n) for _ in range(e)],beta='1',zero=bool(seed%2));c['slots']=[r.randint(0,1) for _ in range(n)]
 o=solve(c);check(c,o);opt=optimum(c);actual=max(o['metrics']['final_rank_load']);require(actual>=opt,'claimed impossible load');
 if actual>opt:gaps.append(dict(seed=seed,input=c,optimal_max=opt,planner_max=actual,target=o['metrics']['target_threshold']))
# Explicitly demonstrate why a failed greedy probe is not a feasibility proof.
# Two experts on rank 1, loads 3 and 1, one destination slot, floor 2.
# Threshold 2 admits transfer 2, but threshold 3 asks for transfer 1 and fails.
nonmonotonic=[oracle([3,1],[1,1],[1,0],2,True,t) is not None for t in [2,3,4]]
require(nonmonotonic==[True,False,True],'oracle nonmonotonic regression')
# Both documented threshold rounding modes, checked independently.
round_case=config(3,1,rows([4],3),slots=1)
for mode,expected in [('paper',3),('code',2)]:
 round_case['rounding']=mode
 rounded=solve(round_case);check(round_case,rounded)
 require(rounded['metrics']['target_threshold']==expected,'threshold rounding')

# Corrupt valid outputs to prove the checker detects loss/changed router/margins/provenance.
c=cases['skew'];o=solve(c);mutations=[]
v=copy.deepcopy(o);v['token_mapping'].pop();mutations.append(v)
v=copy.deepcopy(o);v['physical'][0]['quota']+=1;mutations.append(v)
v=copy.deepcopy(o);v['source_quotas'][0][0]+=1;mutations.append(v)
v=copy.deepcopy(o);v['token_mapping'][0]['logical_experts']=[7];mutations.append(v)
v=copy.deepcopy(o);v['physical'][-1]['weight_source_rank']=999;mutations.append(v)
for v in mutations:
 try:check(c,v)
 except (InvariantError,KeyError):pass
 else:raise RuntimeError('checker accepted corruption')
# Invalid input parameters must fail in normal and -O execution.
for key,value in [('slots',[-1]*4),('min_replica_quota',0),('beta','nan'),('main_placement',[99]*8),('top_k',0)]:
 v=copy.deepcopy(c);v[key]=value
 try:solve(v)
 except InputError:pass
 else:raise RuntimeError('accepted invalid '+key)
v=copy.deepcopy(c);v['mapping'][0]['experts']=[0,0];v['top_k']=2
try:solve(v)
except InputError:pass
else:raise RuntimeError('accepted duplicate topk')
# Actual compiled upstream fast/slow scalar blocks, NOT a rewritten Python reference.
def reference(d,h,q,local=True):
 text=' '.join(map(str,[len(d),len(h),int(local)]+d+h+q))+'\n'
 run=subprocess.run([str(ROOT/'reference/reference_cpu')],input=text,text=True,capture_output=True,check=True)
 result=[list(map(int,line.split())) for line in run.stdout.splitlines()]
 require(result[:len(d)]==result[len(d):],'upstream fast/slow disagreement');return result[:len(d)]
differences=[]
fixtures=[('exact',[0,0,4,4],[0,1],[4,4]),('rounding_counterexample',[0,0,1,1],[0,1],[1,1]),('local',[3,2,4,1],[0,1],[5,5]),('nondivisible',[0,1,2,4],[0,1],[3,4])]
for name,d,h,q in fixtures:
 ref=reference(d,h,q);ours=decompose(d,h,q);cols=[sum(row[j] for row in ref) for j in range(len(h))]
 require([sum(row) for row in ref]==d,'upstream source margin');require([sum(row[j] for row in ours) for j in range(len(h))]==q,'our column margin')
 differences.append(dict(name=name,demand=d,hosts=h,quota=q,upstream_cpu_extracted=ref,ours=ours,upstream_column_sum=cols,column_margin_matches=cols==q,outputs_match=ref==ours))
require(differences[0]['outputs_match'],'exact fixture mismatch');require(not differences[1]['column_margin_matches'],'counterexample did not reproduce')
report=dict(cases=summary,random_seeds=fuzz,exhaustive_cases=80,exhaustive_gaps=gaps,checker_negative_cases=len(mutations),invalid_input_cases=6,reference_differences=differences,
 validation_level='CPU execution of unmodified upstream scalar fast/slow decomposition bodies and sparse ordinal lookup; no GPU end-to-end placement run',cuda=False,nonmonotonic_probe_results=nonmonotonic,rounding_mode_cases=2)
(OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'PASS','scenarios':len(cases),'random':len(fuzz),'exhaustive':80,'greedy_optimality_gaps':len(gaps),'reference_fixtures':len(fixtures),'negative_checker':len(mutations),'invalid':6},indent=2))
