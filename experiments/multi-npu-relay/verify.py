#!/usr/bin/env python3
"""Independent event reconstruction, no reliance on executor PASS text."""
import csv,json,sys,hashlib
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
    index={}
    for row in events:
        index.setdefault((row['event'],None),[]).append(row)
        if row['task']>=0:index.setdefault((row['event'],row['task']),[]).append(row)
    def find(name,**match):return [x for x in index.get((name,match.get('task')),[]) if all(x[k]==v for k,v in match.items())]
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
    require(len(find('send'))==len(transfers) and len(find('data_ready'))==2*len(assignments) and len(find('edge_ready'))==sum(x['stage']==2 for x in transfers),'unexpected send/ready event')
    ready={};weight_senders=[];verified_bytes=[0,0,0];remote_bytes=[0,0,0];local_bytes=[0,0,0]
    for x in transfers:
        task=x['task'];send=one('send',task=task);require(send['node']==x['source'] and send['stage']==x['stage'] and send['id']==x['id'] and send['bytes']==x['bytes'],'send identity/size')
        r=one('edge_ready' if x['stage']==2 else 'data_ready',task=task);require(r['node']==x['target'] and r['bytes']==x['bytes'],'target ready identity');ready[task]=r['time_ps']
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
                require(send['time_ps']<=time('ta_admitted',task=task,offset=off)<=rec['time_ps']<=ver['time_ps']<=done['time_ps']<=r['time_ps'],'TA execution ordering')
                require(done['time_ps']-ver['time_ps']==((p['weight_completion_ns']+(p['reorder_ns'] if x['offset']==0 and physical[x['source_physical']]['kind']=='main' else 0)+(p['slow_relay_ns'] if x['target']==p['slow_relay_rank'] and physical[x['source_physical']]['kind']=='main' else 0))*1000 if x['stage']==2 else 0),'target completion service delay')
            require(r['time_ps']==max(v['time_ps'] for v in find('target_complete',task=task)),'ready must aggregate target completes')
            sender=one('sender_complete',task=task);require(sender['node']==x['source'] and sender['time_ps']>=send['time_ps'],'sender completion')
            if x['stage']==2:weight_senders.append(sender['time_ps'])
            remote_bytes[x['stage']]+=x['bytes']
        verified_bytes[x['stage']]+=x['bytes']
        if x['stage']==0:require(send['time_ps']==gate,'dispatch global gate')
        if x['stage']==2:
            deps=x['dependencies'];require(send['time_ps']==max([planning]+[time('edge_ready',task=j) for j in deps]),'relay target dependency and immediate forwarding')
            reads=find('relay_buffer_read',task=task)
            require(len(reads)==int(bool(deps)),'relay reads actual buffer')
            if reads:require(reads[0]['offset']==x['offset'] and reads[0]['bytes']==x['bytes'] and reads[0]['node']==x['source'],'buffer read range')
    weight_tasks=[x for x in transfers if x['stage']==2]
    replicas=[ph for ph in physical.values() if ph['kind']=='replica']
    require(len(find('weight_ready'))==len(replicas),'final replica cardinality')
    for ph in replicas:
        incoming=sorted([x for x in weight_tasks if x['physical']==ph['id']],key=lambda x:x['offset'])
        cursor=0
        for x in incoming:
            require(x['offset']==cursor and x['target']==ph['rank'],'replica coverage duplicate/gap')
            src=physical[x['source_physical']]
            require(x['source']==src['rank'] and src['expert']==ph['expert'],'edge provenance')
            cursor+=x['bytes']
        require(cursor==p['weight_bytes'],'replica full bytes')
        require(time('weight_ready',id=ph['id'])==max(ready[x['task']] for x in incoming),'final ready requires all chunks')
    require(weights==max([planning]+[time('weight_ready',id=ph['id']) for ph in replicas]),'global weights completion')
    group_keys=set();group_waits=[]
    for x in weight_tasks:
        src=physical[x['source_physical']]
        if src['kind']=='main':require(not x['dependencies'],'main cannot wait');continue
        if c['weight_strategy']=='chunk-streaming':
            required=[y['task'] for y in weight_tasks if physical[y['source_physical']]['kind']=='main' and physical[y['physical']]['expert']==src['expert'] and (y['offset'],y['bytes'])==(x['offset'],x['bytes'])]
            key=(src['expert'],x['offset'],x['bytes']);group_keys.add(key)
            group=time('group_chunk_ready',id=src['expert'],offset=x['offset'],bytes=x['bytes'])
            require(group==max(ready[j] for j in required),'group ready must wait all Stage-I relay targets')
            require(time('send',task=x['task'])==group,'Stage-II must wait upstream group')
            own=[j for j in required if transfers[j]['physical']==x['source_physical']]
            require(bool(own),'own relay dependency missing')
            group_waits.append(dict(task=x['task'],own_ready_ps=max(ready[j] for j in own),group_ready_ps=group,wait_ps=group-max(ready[j] for j in own)))
        else:required=[y['task'] for y in weight_tasks if y['physical']==x['source_physical']]
        require(x['dependencies']==required,'incomplete or extraneous source/group dependency list')
    require(len(find('group_chunk_ready'))==len(group_keys),'group ready cardinality')
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
    with (path/'executed-transfers.csv').open() as f:executed=list(csv.DictReader(f))
    require(len(executed)==len(transfers),'executed graph cardinality')
    for a,b in zip(executed,transfers):
        for key in a:
            value=[int(v) for v in a[key].split(';') if v] if key=='dependencies' else int(a[key])
            require(value==b[key],'executed graph differs '+key)
    raw=(path/'received-payloads.bin').read_bytes()
    payloads={};cursor=0
    with (path/'payload-index.csv').open() as f:
        for row in csv.DictReader(f):
            task,off,size=map(int,(row['task'],row['offset'],row['bytes']))
            require(task not in payloads and off==cursor and size==transfers[task]['bytes'],'payload index')
            payloads[task]=raw[off:off+size];require(len(payloads[task])==size,'payload truncation');cursor+=size
    require(len(payloads)==len(transfers) and cursor==len(raw),'payload completeness')
    for x in transfers:
        if x['stage']==2:
            ph=physical[x['physical']]
            expected=bytes((p['seed']+ph['expert']*71+ph['weight_source_rank']*131+ph['weight_source_physical']*43+i*17+(i>>8)*29)%256 for i in range(x['offset'],x['offset']+x['bytes']))
            require(payloads[x['task']]==expected,'raw weight payload')
            if x['dependencies']:
                buf=bytearray(p['weight_bytes'])
                for parent in x['dependencies']:
                    src=transfers[parent]
                    if src['physical']==x['source_physical']:buf[src['offset']:src['offset']+src['bytes']]=payloads[parent]
                require(payloads[x['task']]==buf[x['offset']:x['offset']+x['bytes']],'relay raw received buffer provenance')
        else:
            a=assignments[x['id']]
            data=bytes((p['seed']+a['token']*131+a['expert']*71+a['rank']*43+i*17+(i>>8)*29)%256 for i in range(x['bytes']))
            if x['stage']==1:data=bytes(b^((a['expert']*37+165)%256) for b in data)
            require(payloads[x['task']]==data,'raw token result')
    send_bytes=[sum(x['bytes'] for x in weight_tasks if x['source']==r) for r in range(pc['npus'])]
    overlaps=[]
    for x in weight_tasks:
        if not x['dependencies']:continue
        send=time('send',task=x['task']);finish=ready[x['task']]
        for incoming in weight_tasks:
            if incoming['physical']!=x['source_physical'] or incoming['offset']<=x['offset']:continue
            other_send=time('send',task=incoming['task']);other_end=ready[incoming['task']]
            if max(send,other_send)<min(finish,other_end):
                overlaps.append(dict(outgoing=x['task'],incoming=incoming['task'],overlap_ps=min(finish,other_end)-max(send,other_send)))
                break
    native_overlaps=[]
    first_admit={x['task']:min(v['time_ps'] for v in find('ta_admitted',task=x['task'])) for x in weight_tasks}
    for x in weight_tasks:
        if not x['dependencies']:continue
        for incoming in weight_tasks:
            if incoming['physical']!=x['source_physical'] or incoming['offset']<=x['offset']:continue
            begin=max(first_admit[x['task']],first_admit[incoming['task']])
            finish=min(ready[x['task']],ready[incoming['task']])
            if begin<finish:
                native_overlaps.append(dict(outgoing=x['task'],incoming=incoming['task'],overlap_ps=finish-begin))
                break
    combine_hash=hashlib.sha256(b''.join(payloads[len(assignments)+i] for i in range(len(assignments)))).hexdigest()
    return dict(mode=c['mode'],strategy=c['weight_strategy'],readiness=c['readiness'],group_chunk_count=len(group_keys),group_waits=group_waits,weight_WQEs=len(weight_tasks),weight_TAs=sum((x['bytes']+p['segment_bytes']-1)//p['segment_bytes'] for x in weight_tasks),weight_send_bytes_per_npu=send_bytes,pipeline_overlaps=overlaps,native_pipeline_overlaps=native_overlaps,combine_sha256=combine_hash,npus=pc['npus'],tokens=len(pc['mapping']),assignments=len(assignments),layer_latency_ps=end-start,
                replicas=len(replicas),max_npu_load=max(per_rank),per_npu_load=per_rank,weight_target_duration_ps=weights-planning,
                weight_sender_end_ps=max(weight_senders,default=planning),weight_bytes=verified_bytes[2],verified_bytes=verified_bytes,
                remote_bytes=remote_bytes,local_bytes=local_bytes,target_segments=len(find('target_complete')),remote_WQEs=sum(x['source']!=x['target'] for x in transfers),
                timeline=dict(layer_start=start,planning_end=planning,reroute_end=reroute,weights_end=weights,dispatch_gate=gate,layer_end=end),compute_intervals=compute_intervals,
                computation='three-matrix SwiGLU GEMM FLOPs' if p['matrices']==3 else 'legacy two-matrix functional model',
                payload='every explicit byte checked at target; synthetic weights/results, no numerical MLP',empty=not pc['mapping'])
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),indent=2))
