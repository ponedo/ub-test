"""Independent reconstruction from individual token assignments, not solver state."""
from collections import Counter
from fractions import Fraction
class InvariantError(ValueError):pass
def require(ok,msg):
    if not ok:raise InvariantError(msg)
def check(c,o):
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
            extra[r]+=1;require(p['quota']>=c['min_replica_quota'],'new replica floor');require(len(owned)<=p['slot']<len(owned)+c['slots'][r],'replica slot')
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
    require(local==sum(min(expected_lambda[p['rank']][p['expert']],p['quota']) for p in physical),'locality not maximized')
    final=[sum(actual[p['id']] for p in physical if p['rank']==r) for r in range(n)]
    metrics=o['metrics'];require(metrics['initial_rank_load']==initial and metrics['final_rank_load']==final and metrics['slot_usage']==extra,'metrics')
    require(max(final)<=max(initial) and max(final)<=metrics['chosen_threshold'],'invalid threshold witness')
    avg=Fraction(sum(expert_count),n);beta=Fraction(str(c['beta']))
    ceiling=lambda v: -(-v.numerator//v.denominator)
    target=ceiling(beta*(ceiling(avg) if c['rounding']=='paper' else avg))
    require(metrics['target_threshold']==target and metrics['total_assignments']==sum(expert_count) and metrics['local_assignments']==local,'target/count metrics')
    require(metrics['target_met']==(max(final)<=metrics['target_threshold']),'false feasibility')
    deps=o['weight_dependencies'];wanted={(p['expert'],p['weight_source_rank'],p['weight_source_physical'],p['rank'],p['id']) for p in physical if p['kind']=='replica'}
    require(len(deps)==len(wanted) and {(d['expert'],d['from_rank'],d['from_physical'],d['to_rank'],d['to_physical']) for d in deps}==wanted and all(d['requires_weight_ready'] for d in deps),'weight dependencies')
    return {'assignments':sum(actual.values()),'physical_instances':len(physical),'checked':'token-level reconstruction; all row/column margins, placements, quotas and locality'}
