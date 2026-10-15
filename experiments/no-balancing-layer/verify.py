#!/usr/bin/env python3
"""Independent input/event conservation and dependency checker, safe under -O."""
import csv,json,math
from pathlib import Path
from cases import validate
class EvidenceError(ValueError):pass
def require(ok,msg):
    if not ok:raise EvidenceError(str(msg))
def union(intervals):
    out=[]
    for a,b in sorted(intervals):
        if b<=a:continue
        if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(b,out[-1][1]))
        else:out.append((a,b))
    return out
def duration(intervals):return sum(b-a for a,b in union(intervals))
def intersection(a,b):return duration([(max(x,u),min(y,v)) for x,y in union(a) for u,v in union(b) if min(y,v)>max(x,u)])
def verify(case):
    case=Path(case);c=validate(json.loads((case/'config.json').read_text()))
    with open(case/'events.csv') as f:rows=list(csv.DictReader(f))
    for i,r in enumerate(rows):
        for key in ['time_ps','stage','id','node','offset','bytes']:r[key]=int(r[key])
        r['i']=i;require(r['time_ps']>=0,'negative time')
    require(all(a['time_ps']<=b['time_ps'] for a,b in zip(rows,rows[1:])),'time reversal')
    used=set()
    def select(event,stage=None,identity=None,node=None):
        rs=[r for r in rows if r['event']==event and (stage is None or r['stage']==stage) and (identity is None or r['id']==identity) and (node is None or r['node']==node)]
        used.update(r['i'] for r in rs);return rs
    def one(event,stage=None,identity=None,node=None):
        rs=select(event,stage,identity,node);require(len(rs)==1,(event,stage,identity,node,len(rs)));return rs[0]
    def before(a,b,strict_time=False):
        require(a['i']<b['i'] and (a['time_ps']<b['time_ps'] if strict_time else a['time_ps']<=b['time_ps']),'dependency order')
    start=one('layer_start');end=one('layer_end');require(start['time_ps']==1000,'layer start');before(start,end)
    n,e,k,t=c['npus'],c['experts'],c['top_k'],c['tokens'];size=c['model_dim']*c['dtype_bytes'];seg=c['segment_bytes']
    assignments=[]
    for token,r in enumerate(c['mapping']):
        for rank,expert in enumerate(r['experts']):assignments.append(dict(assignment=token*k+rank,token=token,rank=rank,source=r['source'],expert=expert,target=c['placement'][expert],payload_bytes=size,local=int(r['source']==c['placement'][expert])))
    with open(case/'assignments.csv') as f:raw=[{key:int(v) for key,v in r.items()} for r in csv.DictReader(f)]
    require(raw==assignments,'raw trace differs from config')
    # Verify the actual executable input is identical to the independently read JSON.
    actual=list(map(int,(case/'input.txt').read_text().split()))
    from cases import KEYS
    expected=[c[key] for key in KEYS]+c['placement']+[v for r in c['mapping'] for v in [r['source']]+r['experts']]
    require(actual==expected,'input.txt differs from config')
    arrivals={};sends={};communication={0:[],1:[]};remote=0
    for a in assignments:
        aid=a['assignment']
        for stage in (0,1):
            src,dst=(a['source'],a['target']) if not stage else (a['target'],a['source'])
            send=one('send',stage,aid,src);ready=one('data_ready',stage,aid,dst);before(start,send);before(send,ready)
            require(send['bytes']==ready['bytes']==size and send['offset']==ready['offset']==0,'transfer bytes')
            sends[stage,aid]=send;arrivals[stage,aid]=ready
            if a['local']:
                local=one('local_verified',stage,aid,src);before(send,local);before(local,ready)
                require(local['bytes']==size and local['offset']==0 and local['time_ps']==send['time_ps']==ready['time_ps'],'local copy model')
            else:
                if not stage:remote+=1
                terminal=one('sender_complete',stage,aid,src);before(ready,terminal,True)
                expected_ranges=[(off,min(seg,size-off)) for off in range(0,size,seg)]
                groups=[]
                for event,node in [('ta_admitted',src),('target_received',dst),('payload_verified',dst),('target_complete',dst)]:
                    rs=select(event,stage,aid,node)
                    require(sorted((r['offset'],r['bytes']) for r in rs)==expected_ranges,'TA identity/ranges '+event)
                    groups.append({r['offset']:r for r in rs})
                for off,length in expected_ranges:
                    chain=[g[off] for g in groups];before(send,chain[0]);before(chain[0],chain[1],True);before(chain[1],chain[2]);before(chain[2],chain[3]);before(chain[3],ready)
                responses=select('ta_response_admitted',stage,aid,dst)
                require(sorted((r['offset'],r['bytes']) for r in responses)==[(off,0) for off,length in expected_ranges],'response identities')
                for r in responses:before(groups[2][r['offset']],r);before(r,terminal,True)
                require(ready['time_ps']==max(r['time_ps'] for r in groups[3].values()),'ready must follow last TA')
                communication[stage].append((min(r['time_ps'] for r in groups[0].values()),ready['time_ps']))
    compute=[];loads=[];busy=[0]*n
    for node in range(n):
        assigned=[a for a in assignments if a['target']==node];loads.append(len(assigned))
        if not assigned:
            idle=one('compute_idle',node=node);require(idle['time_ps']==start['time_ps'],'idle compute');continue
        begin=one('compute_start',node=node);finish=one('compute_end',node=node);before(begin,finish,True)
        require(begin['bytes']==finish['bytes']==len(assigned),'compute count')
        for a in assigned:before(arrivals[0,a['assignment']],begin);before(finish,sends[1,a['assignment']])
        require(begin['time_ps']==max(arrivals[0,a['assignment']]['time_ps'] for a in assigned),'dispatch barrier')
        prev=begin;total=0
        for expert in sorted({a['expert'] for a in assigned}):
            count=sum(a['expert']==expert for a in assigned)
            first=one('expert_start',identity=expert,node=node);last=one('expert_end',identity=expert,node=node)
            before(prev,first);before(first,last,True)
            require(first['time_ps']==prev['time_ps'] and first['bytes']==last['bytes']==count,'serialized resource budget')
            flops=count*4*c['model_dim']*c['ff_dim'];den=c['peak_gflops']*c['util_permille']
            dt=c['setup_ns']*1000+(flops*1000000+den-1)//den
            require(last['time_ps']-first['time_ps']==dt,'compute formula');prev=last;total+=dt
        before(prev,finish);require(finish['time_ps']==prev['time_ps'] and finish['time_ps']-begin['time_ps']==total,'compute end')
        busy[node]=total
        compute.append((begin['time_ps'],finish['time_ps']))
    token_ends=[]
    for token,r in enumerate(c['mapping']):
        done=one('token_complete',identity=token,node=r['source']);token_ends.append(done)
        for rank in range(k):before(arrivals[1,token*k+rank],done)
        require(done['time_ps']==max(arrivals[1,token*k+rank]['time_ps'] for rank in range(k)),'top-k barrier');before(done,end)
    require(end['time_ps']==(max(r['time_ps'] for r in token_ends) if t else start['time_ps']),'layer boundary')
    require(used==set(range(len(rows))),('unknown/extra/duplicate/misrouted event',[r for r in rows if r['i'] not in used][:5]))
    def span(stage):
        if not assignments:return 0
        return max(arrivals[stage,a['assignment']]['time_ps'] for a in assignments)-min(sends[stage,a['assignment']]['time_ps'] for a in assignments)
    local=len(assignments)-remote
    return dict(npus=n,tokens=t,assignments=len(assignments),layer_latency_ps=end['time_ps']-start['time_ps'],
      dispatch_envelope_ps=span(0),compute_envelope_ps=max((b for a,b in compute),default=0)-min((a for a,b in compute),default=0),compute_total_busy_ps=sum(b-a for a,b in compute),combine_envelope_ps=span(1),
      dispatch_remote_payload_bytes=remote*size,dispatch_local_payload_bytes=local*size,combine_remote_payload_bytes=remote*size,combine_local_payload_bytes=local*size,
      sender_completions=2*remote,target_TAs=2*remote*math.ceil(size/seg),per_npu_assignments=loads,per_npu_compute_ps=busy,
      per_expert_assignments=[sum(a['expert']==ex for a in assignments) for ex in range(e)],
      dispatch_compute_overlap_ps=intersection(communication[0],compute),compute_combine_overlap_ps=intersection(compute,communication[1]),dispatch_combine_overlap_ps=intersection(communication[0],communication[1]),
      byte_integrity='Every explicit payload byte checked at target; synthetic deterministic result transform, not numerical MLP or reduction',seed=c['seed'])
if __name__=='__main__':
    import sys
    result=verify(sys.argv[1]);print(json.dumps(result,indent=2))
