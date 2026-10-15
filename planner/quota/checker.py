"""Independent reconstruction from individual token assignments, not solver state."""
from collections import Counter
from fractions import Fraction
from ctypes import c_float
import math
class InvariantError(ValueError):pass
def require(ok,msg):
    if not ok:raise InvariantError(msg)
def check(c,o):
    c=dict(c);c.setdefault('mode','upstream-compatible');c.setdefault('allow_zero_main',False);c.setdefault('beta','1.0');c.setdefault('min_replica_quota',1024);c.setdefault('rounding','code' if c['mode']=='upstream-compatible' else 'paper');c.setdefault('locality_aware',True)
    require(o.get('mode')==c['mode'],'wrong planner mode')
    n,e=c['npus'],c['experts'];physical=o['physical'];byid={p['id']:p for p in physical}
    require(len(byid)==len(physical),'duplicate physical id')
    require(len({(p['expert'],p['rank']) for p in physical})==len(physical),'same-rank duplicate expert')
    require(o['q_physical_ids']==[p['id'] for p in physical],'Q column IDs')
    extra=[0]*n;expected_lambda=[[0]*e for _ in range(n)];expert_count=[0]*e;initial=[0]*n
    for row in c['mapping']:
        require(len(row['experts'])==c['top_k'] and len(set(row['experts']))==c['top_k'],'input topk')
        for x in row['experts']:expected_lambda[row['source']][x]+=1;expert_count[x]+=1;initial[c['main_placement'][x]]+=1
    require(o['lambda_source_expert']==expected_lambda and o['expert_load']==expert_count,'Lambda axes or counts')
    for x in range(e):
        mains=[p for p in physical if p['expert']==x and p['kind']=='main']
        require(len(mains)==1 and mains[0]['rank']==c['main_placement'][x],'main moved/missing')
        if expert_count[x] and not c['allow_zero_main']:require(mains[0]['quota']>=1,'positive main rule')
    offsets=[];base=0
    for r in range(n):offsets.append(base);base+=c['main_placement'].count(r)+c['slots'][r]
    for p in physical:
        r,x=p['rank'],p['expert'];require(0<=r<n and 0<=x<e,'physical bounds')
        require(type(p['quota']) is int and p['quota']>=0,'quota integer')
        require(p['id']==offsets[r]+p['slot'],'physical slot id')
        owned=[ex for ex in range(e) if c['main_placement'][ex]==r]
        if p['kind']=='replica':
            extra[r]+=1;floor=1 if c['mode']=='upstream-compatible' and o['metrics']['path']=='fast' else c['min_replica_quota'];require(p['quota']>=floor,'new replica floor');require(len(owned)<=p['slot']<len(owned)+c['slots'][r],'replica slot')
        else:require(p['kind']=='main' and p['slot']==owned.index(x),'main slot')
        main=byid[p['weight_source_physical']];require(main['expert']==x and main['kind']=='main' and p['weight_source_rank']==main['rank'],'wrong weight provenance')
    require(all(a<=b for a,b in zip(extra,c['slots'])),'slots exceeded')
    result=o['token_mapping'];require(len(result)==len(c['mapping']),'lost tokens')
    actual=Counter();sources=Counter()
    for token,(inp,row) in enumerate(zip(c['mapping'],result)):
        require(row['token']==token and row['source']==inp['source'] and row['logical_experts']==inp['experts'],'logical router changed')
        require(len(row['physical_experts'])==len(inp['experts']),'assignment count')
        for x,pid in zip(inp['experts'],row['physical_experts']):
            require(pid in byid and byid[pid]['expert']==x,'wrong physical expert');actual[pid]+=1;sources[inp['source'],pid]+=1
    Q=o['source_quotas'];require(len(Q)==n and all(len(row)==len(physical) for row in Q),'Q dimensions')
    for j,p in enumerate(physical):
        require(actual[p['id']]==p['quota'],'physical actual != quota')
        require(sum(Q[r][j] for r in range(n))==p['quota'],'Q column margin')
        for r in range(n):require(type(Q[r][j]) is int and Q[r][j]>=0 and Q[r][j]==sources[r,p['id']],'source materialization')
    for r in range(n):
        for x in range(e):require(sum(Q[r][j] for j,p in enumerate(physical) if p['expert']==x)==expected_lambda[r][x],'source/expert margin')
    for x in range(e):require(sum(p['quota'] for p in physical if p['expert']==x)==expert_count[x],'expert conservation')
    # Locality maximum at fixed quotas is independently known, independent of rounding.
    local=sum(sources[p['rank'],p['id']] for p in physical)
    if c['locality_aware']:require(local==sum(min(expected_lambda[p['rank']][p['expert']],p['quota']) for p in physical),'locality not maximized')
    final=[sum(actual[p['id']] for p in physical if p['rank']==r) for r in range(n)]
    metrics=o['metrics'];require(metrics['initial_rank_load']==initial and metrics['final_rank_load']==final and metrics['slot_usage']==extra,'metrics')
    require(max(final)<=max(initial) and max(final)<=metrics['chosen_threshold'],'invalid threshold witness')
    avg=Fraction(sum(expert_count),n);beta=Fraction(str(c['beta']))
    ceiling=lambda v: -(-v.numerator//v.denominator)
    target=ceiling(beta*(ceiling(avg) if c['rounding']=='paper' else avg))
    if c['mode']=='upstream-compatible':
        f=lambda x:c_float(x).value
        target=math.ceil(f(f(f(sum(expert_count))/n)*max(f(float(c['beta'])),1.0)))
        check_upstream(c,o)
    require(metrics['target_threshold']==target and metrics['total_assignments']==sum(expert_count) and metrics['local_assignments']==local,'target/count metrics')
    require(metrics['target_met']==(max(final)<=metrics['target_threshold']),'false feasibility')
    deps=o['weight_dependencies'];wanted={(p['expert'],p['weight_source_rank'],p['weight_source_physical'],p['rank'],p['id']) for p in physical if p['kind']=='replica'}
    require(len(deps)==len(wanted) and {(d['expert'],d['from_rank'],d['from_physical'],d['to_rank'],d['to_physical']) for d in deps}==wanted and all(d['requires_weight_ready'] for d in deps),'weight dependencies')
    return {'assignments':sum(actual.values()),'physical_instances':len(physical),'checked':'token-level reconstruction; all row/column margins, placements, quotas and locality'}


def check_upstream(c,o):
    """Audit original source output and minimum-change repair independently."""
    up=o['upstream'];raw=up['replication'];physical=o['physical'];byid={p['id']:p for p in physical}
    require(raw['physical']==[{k:byid[p['id']][k] for k in ['expert','id','rank','quota','kind']} for p in raw['physical']],'upstream placement changed')
    require(len(raw['physical'])==len(physical),'upstream instances lost')
    path='bypass' if not raw['search_enabled'] else 'fast' if raw['fast_success'] else 'fallback'
    require(o['metrics']['path']==path,'upstream path')
    if raw['search_enabled']:require(o['metrics']['chosen_threshold']==raw['threshold'],'upstream threshold')
    else:
        require(raw['threshold'] is None and o['metrics']['chosen_threshold']==max(o['metrics']['final_rank_load']),'bypass threshold convention')
    require(o['probes']==raw['probes'],'upstream probes')
    for f in raw['dynamic_floors']:
        require(f['effective']==max(1,(f['need']+f['feasible_slots']-1)//f['feasible_slots']),'dynamic floor arithmetic')
    column={pid:j for j,pid in enumerate(o['q_physical_ids'])};moved=0
    require(len(up['quota_repairs'])==c['experts'],'missing raw decomposition')
    for x,a in enumerate(up['quota_repairs']):
        require(a['expert']==x,'repair expert identity')
        ids=a['physical_ids'];rawq=a['raw'];fixed=a['corrected'];g=c['npus']
        require([sum(row) for row in rawq]==[o['lambda_source_expert'][r][x] for r in range(g)],'raw source margin')
        delta=[sum(row[j] for row in rawq)-byid[pid]['quota'] for j,pid in enumerate(ids)]
        lower=sum(max(v,0) for v in delta)
        distance=sum(abs(rawq[r][j]-fixed[r][j]) for r in range(g) for j in range(len(ids)))
        require(distance==2*lower and a['minimum_moved_assignments']==lower and a['trigger']==bool(lower),'repair not minimal or not reported')
        replay=[row.copy() for row in rawq]
        for move in a['moves']:
            r,j,k,v=move['source'],move['from_instance'],move['to_instance'],move['assignments']
            require(v>0,'repair move');replay[r][j]-=v;replay[r][k]+=v
        require(replay==fixed,'repair ledger does not reproduce corrected Q')
        for r in range(g):
            for j,pid in enumerate(ids):require(fixed[r][j]==o['source_quotas'][r][column[pid]],'repaired Q differs')
        moved+=lower
    require(moved==up['moved_assignments']==o['metrics']['repaired_assignments'],'repair total')

    # Public sparse-quota ordinal semantics with a deterministic CPU token order.
    seen=Counter();order=o['ordinal_physical_order']
    for row in o['token_mapping']:
        r=row['source']
        for x,pid in zip(row['logical_experts'],row['physical_experts']):
            ordinal=seen[r,x];seen[r,x]+=1;cumulative=0;selected=None
            for candidate in order:
                if byid[candidate]['expert']!=x:continue
                cumulative+=o['source_quotas'][r][column[candidate]]
                if ordinal<cumulative:selected=candidate;break
            require(pid==selected,'sparse quota ordinal mapping')
