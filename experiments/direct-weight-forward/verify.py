#!/usr/bin/env python3
"""Independent event reconstruction, no reliance on executor PASS text."""
import csv,json,sys
from collections import Counter
from pathlib import Path

def require(ok,message):
    if not ok:raise ValueError(message)
def verify(path):
    path=Path(path);c=json.loads((path/'config.json').read_text());plan=json.loads((path/'plan.json').read_text());p=c['runtime'];pc=c['planner_input']
    assignments=c['assignments'];transfers=c['transfers'];physical={x['id']:x for x in plan['physical']}
    with (path/'events.csv').open() as f:events=[{k:(v if k=='event' else int(v)) for k,v in row.items()} for row in csv.DictReader(f)]
    require(events and all(a['time_ps']<=b['time_ps'] for a,b in zip(events,events[1:])),'clock order')
    require(not any(x['event']=='error' for x in events),'executor error')
    def find(name,**match):return [x for x in events if x['event']==name and all(x[k]==v for k,v in match.items())]
    def one(name,**match):
        rows=find(name,**match);require(len(rows)==1,f'{name}/{match}: expected once, got {len(rows)}');return rows[0]
    def time(name,**match):return one(name,**match)['time_ps']
    start=time('layer_start');end=time('layer_end');planning=time('planning_end');reroute=time('reroute_end');weights=time('weights_end');gate=time('dispatch_gate')
    require(time('planning_start')==start and planning-start==p['planning_ns']*1000,'planning duration')
    require(time('reroute_start')==time('weights_start')==planning and reroute-planning==p['reroute_ns']*1000,'overlap start/reroute duration')
    for row in events:
        if row['task']>=0:
            require(row['task']<len(transfers),'unknown task event');x=transfers[row['task']]
            require(row['stage']==x['stage'] and row['id']==x['id'],'task metadata drift')
    require(len(find('send'))==len(transfers) and len(find('data_ready'))==2*len(assignments) and len(find('weight_ready'))==sum(x['stage']==2 for x in transfers),'unexpected send/ready event')
    ready={};weight_senders=[];verified_bytes=[0,0,0];remote_bytes=[0,0,0];local_bytes=[0,0,0]
    for x in transfers:
        task=x['task'];send=one('send',task=task);require(send['node']==x['source'] and send['stage']==x['stage'] and send['id']==x['id'] and send['bytes']==x['bytes'],'send identity/size')
        r=one('weight_ready' if x['stage']==2 else 'data_ready',task=task);require(r['node']==x['target'] and r['bytes']==x['bytes'],'target ready identity');ready[task]=r['time_ps']
        require(send['time_ps']>=planning and r['time_ps']>=send['time_ps'],'transfer causality')
        if x['source']==x['target']:
            v=one('local_verified',task=task);require(v['bytes']==x['bytes'] and v['node']==x['target'] and v['time_ps']==r['time_ps'],'local verification')
            require(not find('target_received',task=task) and not find('sender_complete',task=task),'local must not use network')
            local_bytes[x['stage']]+=x['bytes']
        else:
            expected={off:min(p['segment_bytes'],x['bytes']-off) for off in range(0,x['bytes'],p['segment_bytes'])}
            for name in ['ta_admitted','target_received','payload_verified','target_complete']:
                rows=find(name,task=task);require({v['offset']:v['bytes'] for v in rows}==expected,'segment coverage '+name)
                require(len(rows)==len(expected),'unexpected duplicate segment '+name)
                require(all(v['node']==(x['source'] if name=='ta_admitted' else x['target']) for v in rows),'segment endpoint')
            for off,length in expected.items():
                rec=one('target_received',task=task,offset=off);ver=one('payload_verified',task=task,offset=off);done=one('target_complete',task=task,offset=off)
                require(send['time_ps']<=rec['time_ps']<=ver['time_ps']<=done['time_ps']<=r['time_ps'],'TA execution ordering')
                require(done['time_ps']-ver['time_ps']==(p['weight_completion_ns']*1000 if x['stage']==2 else 0),'target completion service delay')
            require(r['time_ps']==max(v['time_ps'] for v in find('target_complete',task=task)),'ready must aggregate target completes')
            sender=one('sender_complete',task=task);require(sender['node']==x['source'] and sender['time_ps']>=send['time_ps'],'sender completion')
            if x['stage']==2:weight_senders.append(sender['time_ps'])
            remote_bytes[x['stage']]+=x['bytes']
        verified_bytes[x['stage']]+=x['bytes']
        if x['stage']==0:require(send['time_ps']==gate,'dispatch global gate')
        if x['stage']==2:require(send['time_ps']==planning,'direct weight start')
    weight_tasks=[x for x in transfers if x['stage']==2]
    require(len(weight_tasks)==sum(x['kind']=='replica' for x in physical.values()),'weight replica cardinality')
    require(len({x['physical'] for x in weight_tasks})==len(weight_tasks),'duplicate weight destination')
    for x in weight_tasks:
        ph=physical[x['physical']];require(x['source']==ph['weight_source_rank'] and x['target']==ph['rank'] and x['bytes']==p['weight_bytes'],'main-to-replica weight identity')
    require(weights==max([planning]+[ready[x['task']] for x in weight_tasks]),'global weights completion')
    require(gate==max(weights,reroute),'Figure 8 dispatch gate')
    for ph in physical.values():
        if ph['kind']=='main':require(time('main_weight_ready',id=ph['id'])==start,'main weights resident')
    counts=Counter(a['physical'] for a in assignments);require(all(counts[pid]==ph['quota'] for pid,ph in physical.items()),'quota assignment mismatch')
    for aid,a in enumerate(assignments):
        row=pc['mapping'][a['token']];require(a['assignment']==aid and a['expert']==row['experts'][a['rank']] and a['source']==row['source'] and physical[a['physical']]['expert']==a['expert'] and physical[a['physical']]['rank']==a['target'],'router identity')
        require(transfers[aid]['stage']==0 and transfers[len(assignments)+aid]['stage']==1,'assignment WQE rule')
    per_rank=[sum(a['target']==r for a in assignments) for r in range(pc['npus'])];compute_intervals=[]
    for node,count in enumerate(per_rank):
        if not count:
            one('compute_idle',node=node);require(not find('compute_start',node=node),'idle compute');continue
        begin=time('compute_start',node=node);finish=time('compute_end',node=node)
        require(begin>=gate and all(ready[a['assignment']]<=begin for a in assignments if a['target']==node),'compute tokens ready')
        require(all(ready[x['task']]<=begin for x in weight_tasks if x['target']==node),'compute weights ready')
        intervals=[]
        for ph in physical.values():
            if ph['rank']!=node or not ph['quota']:continue
            a=time('expert_start',id=ph['id']);b=time('expert_end',id=ph['id'])
            num=ph['quota']*2*p['matrices']*p['model_dim']*p['ff_dim']*1000000;den=p['peak_gflops']*p['util_permille']
            duration=(num+den-1)//den+p['setup_ns']*1000
            require(b-a==duration,'FLOP duration');intervals.append((a,b))
        intervals.sort();require(intervals[0][0]==begin and intervals[-1][1]==finish and all(a[1]==b[0] for a,b in zip(intervals,intervals[1:])),'NPU serialized batch resource')
        compute_intervals.append(dict(node=node,start_ps=begin,end_ps=finish))
        for a in assignments:
            if a['target']==node:require(time('send',task=len(assignments)+a['assignment'])==finish,'combine compute gate')
    for token,row in enumerate(pc['mapping']):
        ids=[a['assignment'] for a in assignments if a['token']==token]
        require(len(ids)==pc['top_k'],'topk lost')
        require(time('token_complete',id=token)==max(ready[len(assignments)+i] for i in ids),'source topk completion')
    require(len(find('token_complete'))==len(pc['mapping']),'token cardinality')
    require(end==max([gate]+[x['time_ps'] for x in find('token_complete')]),'layer completion')
    require(len(transfers)==2*len(assignments)+len(weight_tasks),'per-assignment WQE cardinality')
    require(verified_bytes[0]==verified_bytes[1]==len(assignments)*p['model_dim']*p['dtype_bytes'],'dispatch/combine byte conservation')
    return dict(mode=c['mode'],npus=pc['npus'],tokens=len(pc['mapping']),assignments=len(assignments),layer_latency_ps=end-start,
                replicas=len(weight_tasks),max_npu_load=max(per_rank),per_npu_load=per_rank,weight_target_duration_ps=weights-planning,
                weight_sender_end_ps=max(weight_senders,default=planning),weight_bytes=verified_bytes[2],verified_bytes=verified_bytes,
                remote_bytes=remote_bytes,local_bytes=local_bytes,target_segments=len(find('target_complete')),remote_WQEs=sum(x['source']!=x['target'] for x in transfers),
                timeline=dict(layer_start=start,planning_end=planning,reroute_end=reroute,weights_end=weights,dispatch_gate=gate,layer_end=end),compute_intervals=compute_intervals,
                computation='three-matrix SwiGLU GEMM FLOPs' if p['matrices']==3 else 'legacy two-matrix functional model',
                payload='every explicit byte checked at target; synthetic weights/results, no numerical MLP',empty=not pc['mapping'])
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),indent=2))
