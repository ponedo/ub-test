#!/usr/bin/env python3
"""Independent CPU Algorithm-1-style planner. No CUDA/ns3/network dependency."""
import argparse,json,time
from fractions import Fraction
from pathlib import Path
class InputError(ValueError):pass
def need(ok,msg):
    if not ok:raise InputError(msg)
def integer(x,low,high):return type(x) is int and low<=x<=high
def validate(c):
    need(c.get('schema_version')==1,'schema_version')
    n,e=c.get('npus'),c.get('experts');need(integer(n,1,256) and integer(e,1,4096),'npus/experts')
    k=c.get('top_k');need(integer(k,1,e),'top_k')
    h=c.get('main_placement');need(isinstance(h,list) and len(h)==e and all(integer(r,0,n-1) for r in h),'main_placement')
    slots=c.get('slots');need(isinstance(slots,list) and len(slots)==n and all(integer(s,0,e) for s in slots),'per-rank slots')
    need(integer(c.get('min_replica_quota'),1,2**31-1),'min_replica_quota')
    need(type(c.get('allow_zero_main')) is bool,'allow_zero_main')
    need(c.get('rounding') in ('paper','code'),'rounding')
    try:b=Fraction(str(c['beta']))
    except (ValueError,KeyError,ZeroDivisionError):raise InputError('beta')
    need(1<=b<=100,'beta must be finite >=1')
    rows=c.get('mapping');need(isinstance(rows,list) and len(rows)*k<=2000000,'mapping bound')
    for row in rows:
        need(isinstance(row,dict) and integer(row.get('source'),0,n-1),'source')
        ids=row.get('experts');need(isinstance(ids,list) and len(ids)==k and all(integer(x,0,e-1) for x in ids) and len(set(ids))==k,'unique logical top-k')
    return c
def ceil(x):return -(-x.numerator//x.denominator) if isinstance(x,Fraction) else x
def oracle(loads,h,slots,floor,allow_zero,tau):
    """Greedy witness only: failure is NOT a proof of mathematical infeasibility."""
    n=len(slots);initial=[sum(v for e,v in enumerate(loads) if h[e]==r) for r in range(n)]
    excess=[max(0,x-tau) for x in initial];slack=[max(0,tau-x) for x in initial]
    quota=[{h[e]:v} for e,v in enumerate(loads)];used=[0]*n;exports=[]
    if sum(excess)>sum(slack):return None
    for source in sorted(range(n),key=lambda r:(-excess[r],r)):
        for e in sorted((e for e in range(len(loads)) if h[e]==source),key=lambda e:(-loads[e],e)):
            keep=0 if allow_zero or loads[e]==0 else 1
            while excess[source]>0 and quota[e][source]>keep:
                available=quota[e][source]-keep
                candidates=[r for r in range(n) if r not in quota[e] and used[r]<slots[r] and min(excess[source],slack[r],available)>=floor]
                if not candidates:break
                target=min(candidates,key=lambda r:(-slack[r],r));q=min(excess[source],slack[target],available)
                quota[e][source]-=q;quota[e][target]=q;excess[source]-=q;slack[target]-=q;used[target]+=1;exports.append((e,target,q))
    return (quota,exports) if not any(excess) else None

def decompose(demand,hosts,quotas):
    """Maximize local fills, then sequential capacity-updated largest remainder.

    Unlike independent per-source rounding, residual capacities are consumed after
    each source, guaranteeing BOTH margins exactly, without fabricated tokens.
    """
    n=len(demand);q=[[0]*len(hosts) for _ in range(n)];left=demand.copy();cap=quotas.copy()
    for j,host in enumerate(hosts):
        fill=min(left[host],cap[j]);q[host][j]=fill;left[host]-=fill;cap[j]-=fill
    for source,amount in enumerate(left):
        if not amount:continue
        den=sum(cap);need(0<amount<=den,'residual capacity')
        alloc=[amount*x//den for x in cap];rem=amount-sum(alloc)
        order=sorted(range(len(hosts)),key=lambda j:(-(amount*cap[j]%den),hosts[j],j))
        for j in order[:rem]:alloc[j]+=1
        for j,x in enumerate(alloc):need(x<=cap[j],'capacity overflow');q[source][j]+=x;cap[j]-=x
    need(not any(cap),'unconsumed quota');return q

def solve(c):
    begin=time.perf_counter_ns();validate(c);n,e=c['npus'],c['experts'];h=c['main_placement']
    matrix=[[0]*e for _ in range(n)]
    for row in c['mapping']:
        for expert in row['experts']:matrix[row['source']][expert]+=1
    loads=[sum(row[x] for row in matrix) for x in range(e)];initial=[sum(loads[x] for x in range(e) if h[x]==r) for r in range(n)]
    total=sum(loads);beta=Fraction(str(c['beta']));avg=Fraction(total,n)
    target=ceil(beta*(ceil(avg) if c['rounding']=='paper' else avg))
    low=min(target,max(initial));high=max(initial);probes=[]
    best=([{h[x]:loads[x]} for x in range(e)],[])
    while low<high:
        middle=(low+high)//2;candidate=oracle(loads,h,c['slots'],c['min_replica_quota'],c['allow_zero_main'],middle)
        probes.append({'threshold':middle,'greedy_witness_found':candidate is not None})
        if candidate is None:low=middle+1
        else:high=middle;best=candidate
    # Materialize the final upper bound, including a no-probe/empty input.
    candidate=oracle(loads,h,c['slots'],c['min_replica_quota'],c['allow_zero_main'],high)
    probes.append({'threshold':high,'greedy_witness_found':candidate is not None,'final':True})
    if candidate is not None:best=candidate
    quotas,exports=best;physical=[];main_ids={};offsets=[];base=0
    for rank in range(n):
        offsets.append(base);owned=[x for x in range(e) if h[x]==rank]
        for slot,x in enumerate(owned):
            pid=base+slot;main_ids[x]=pid;physical.append(dict(id=pid,expert=x,rank=rank,kind='main',slot=slot,quota=quotas[x][rank],weight_source_rank=rank,weight_source_physical=pid))
        base+=len(owned)+c['slots'][rank]
    used=[0]*n
    for x,rank,q in exports:
        slot=sum(r==rank for r in h)+used[rank];used[rank]+=1
        physical.append(dict(id=offsets[rank]+slot,expert=x,rank=rank,kind='replica',slot=slot,quota=q,weight_source_rank=h[x],weight_source_physical=main_ids[x]))
    physical.sort(key=lambda p:p['id']);pid_index={p['id']:j for j,p in enumerate(physical)}
    Q=[[0]*len(physical) for _ in range(n)]
    for x in range(e):
        group=[p for p in physical if p['expert']==x]
        split=decompose([matrix[r][x] for r in range(n)],[p['rank'] for p in group],[p['quota'] for p in group])
        for r in range(n):
            for j,p in enumerate(group):Q[r][pid_index[p['id']]]=split[r][j]
    # Consume exact source-aware cumulative quotas in input-token order.
    pools={}
    for r in range(n):
        for x in range(e):pools[r,x]=[[p['id'],Q[r][j]] for j,p in enumerate(physical) if p['expert']==x and Q[r][j]>0]
    mapping=[]
    for token,row in enumerate(c['mapping']):
        result=[]
        for x in row['experts']:
            pool=pools[row['source'],x]
            while pool and pool[0][1]==0:pool.pop(0)
            need(bool(pool),'no physical quota for token');result.append(pool[0][0]);pool[0][1]-=1
        mapping.append(dict(token=token,source=row['source'],logical_experts=row['experts'].copy(),physical_experts=result))
    final=[sum(p['quota'] for p in physical if p['rank']==r) for r in range(n)]
    dependencies=[dict(expert=p['expert'],from_rank=p['weight_source_rank'],from_physical=p['weight_source_physical'],to_rank=p['rank'],to_physical=p['id'],requires_weight_ready=True) for p in physical if p['kind']=='replica']
    return dict(schema_version=1,lambda_axes=['source_rank','logical_expert'],lambda_source_expert=matrix,expert_load=loads,physical=physical,q_axes=['source_rank','physical_id_in_q_physical_ids'],q_physical_ids=[p['id'] for p in physical],source_quotas=Q,token_mapping=mapping,weight_dependencies=dependencies,
                metrics=dict(initial_rank_load=initial,final_rank_load=final,slot_usage=used,total_assignments=total,target_threshold=target,chosen_threshold=high,target_met=max(final)<=target,initial_imbalance=float(Fraction(max(initial),1)/avg) if total else 0,final_imbalance=float(Fraction(max(final),1)/avg) if total else 0,local_assignments=sum(Q[p['rank']][j] for j,p in enumerate(physical))),
                probes=probes,optimality='greedy binary-search witness; not a global optimality/infeasibility proof',cpu_wall_ns=time.perf_counter_ns()-begin)

def from_no_balancing(c,slots=1,min_quota=1024,beta='1.01'):
    return dict(schema_version=1,npus=c['npus'],experts=c['experts'],top_k=c['top_k'],main_placement=c['placement'].copy(),slots=[slots]*c['npus'],mapping=c['mapping'],min_replica_quota=min_quota,beta=beta,allow_zero_main=False,rounding='paper')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');p.add_argument('--from-no-balancing',action='store_true');p.add_argument('--slots',type=int,default=1);p.add_argument('--min-quota',type=int,default=1024);a=p.parse_args()
    c=json.loads(Path(a.input).read_text())
    if a.from_no_balancing:c=from_no_balancing(c,a.slots,a.min_quota)
    result=solve(c)
    from checker import check
    check(c,result);Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
