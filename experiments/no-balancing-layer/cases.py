#!/usr/bin/env python3
"""Synthetic fixed-placement traces; no load balancing or expert replication."""
import argparse,csv,json,random
from pathlib import Path
KEYS=['npus','experts','top_k','tokens','model_dim','ff_dim','dtype_bytes','segment_bytes','peak_gflops','util_permille','setup_ns','seed','link_gbps','link_delay_ns']
DEFAULT=dict(model_dim=256,ff_dim=1024,dtype_bytes=2,segment_bytes=256,peak_gflops=1000,util_permille=500,setup_ns=100,seed=20261015,link_gbps=100,link_delay_ns=20)
class ConfigError(ValueError): pass
def require(ok,msg):
    if not ok: raise ConfigError(msg)
def validate(c):
    for key in KEYS: require(type(c.get(key)) is int and 0<=c[key]<=2**32-1,'invalid integer '+key)
    n,e,k,t=(c[x] for x in KEYS[:4])
    require(1<=n<=256 and 1<=e<=4096 and 1<=k<=e and t<=100000,'invalid dimensions')
    limits={'model_dim':16384,'ff_dim':65536,'dtype_bytes':8,'segment_bytes':65536,'peak_gflops':10000000,'util_permille':1000}
    for key,limit in limits.items():require(1<=c[key]<=limit,'invalid '+key)
    require(c['setup_ns']<=100000000,'invalid setup')
    require(1<=c['link_gbps']<=10000 and c['link_delay_ns']<=1000000,'invalid link')
    require(t*k<=100000 and t*k*c['model_dim']*c['dtype_bytes']<=256*1024*1024,'explicit payload safety bound')
    require(len(c['placement'])==e and all(type(x) is int and 0<=x<n for x in c['placement']),'placement')
    require(len(c['mapping'])==t,'mapping count')
    for row in c['mapping']:
        require(type(row['source']) is int and 0<=row['source']<n,'source')
        experts=row['experts'];require(len(experts)==k and all(type(x) is int and 0<=x<e for x in experts) and len(set(experts))==k,'top-k')
    return c
def generate(n=4,e=None,t=None,k=2,seed=20261015,mode='uniform'):
    e=2*n if e is None else e;t=2*n if t is None else t
    require(1<=n<=256 and 1<=e<=4096 and 1<=k<=e and 0<=t<=100000,'invalid generator dimensions')
    c=dict(DEFAULT,npus=n,experts=e,tokens=t,top_k=k,seed=seed,placement=[i%n for i in range(e)],mapping=[],synthetic=True,mode=mode)
    rng=random.Random(seed)
    if mode=='skew': c['placement']=[0]*e
    for token in range(t):
        source=token%n
        candidates=[x for x in range(e) if c['placement'][x]==source] if mode=='local' else list(range(e))
        require(k<=len(candidates),'insufficient experts for unique top-k')
        c['mapping'].append({'source':source,'experts':rng.sample(candidates,k)})
    return validate(c)
def emit(c,path):
    validate(c);path=Path(path);path.mkdir(parents=True,exist_ok=True)
    (path/'config.json').write_text(json.dumps(c,indent=2)+'\n')
    lines=[' '.join(str(c[x]) for x in KEYS),' '.join(map(str,c['placement']))]
    lines += [' '.join(map(str,[r['source']]+r['experts'])) for r in c['mapping']]
    (path/'input.txt').write_text('\n'.join(lines)+'\n')
    with open(path/'assignments.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['assignment','token','rank','source','expert','target','payload_bytes','local'])
        for token,row in enumerate(c['mapping']):
            for rank,expert in enumerate(row['experts']):
                target=c['placement'][expert]
                w.writerow([token*c['top_k']+rank,token,rank,row['source'],expert,target,c['model_dim']*c['dtype_bytes'],int(row['source']==target)])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--npus',type=int,default=4);p.add_argument('--experts',type=int);p.add_argument('--tokens',type=int);p.add_argument('--top-k',type=int,default=2);p.add_argument('--seed',type=int,default=20261015);p.add_argument('--mode',choices=['uniform','skew','local'],default='uniform');a=p.parse_args()
    emit(json.loads(Path(a.config).read_text()) if a.config else generate(a.npus,a.experts,a.tokens,a.top_k,a.seed,a.mode),a.out)
