#!/usr/bin/env python3
"""Summarize measured SystemC event files, never synthesize simulation results."""
import csv, math, pathlib, sys, collections, json
root = pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'eval/e2e')
start, end = 2_000_000, 6_000_000  # ps; fixed before comparing policies

def read(path):
    with path.open() as f:
        return [{k: (v if k=='event' else int(v)) for k,v in row.items()} for row in csv.DictReader(f)]
def quantile(values, p):
    return sorted(values)[math.ceil(p*len(values))-1]
def jain(values):
    return sum(values)**2/(len(values)*sum(v*v for v in values))
summaries, per_jetty = [], []
for load in ('mixed','equal'):
    for policy in ('fifo','rr','drr'):
        prefix=root/f'{policy}_{load}'
        wr=read(prefix.with_suffix('.wr.csv')); ev=read(prefix.with_suffix('.events.csv'))
        assert len(wr)==768 and len({r['wr_id'] for r in wr})==768
        finish=max(r['complete_ps'] for r in wr); begin=min(r['submit_ps'] for r in wr)
        assert all(r['submit_ps']==0 for r in wr)
        latency=[(r['complete_ps']-r['submit_ps'])/1000 for r in wr]
        wire=[0.]*3; payload=[0.]*3; requests=[0]*3; peak=[0]*3; minimum=[10**9]*3; queued=[0]*3
        counts=collections.Counter(e['event'] for e in ev)
        for event in ('submit','enqueue','dequeue','dispatch','ordered','tx_start','tx_end','rx_wire','memory_commit','ack_tx_start','ack_tx_end','ack_rx_wire','complete'):
            assert counts[event]==len(wr), (prefix,event,counts[event])
        by_wr=collections.defaultdict(list)
        for e in ev: by_wr[e['wr_id']].append(e)
        for r in wr:
            timeline=by_wr[r['wr_id']]
            for event,column in [('submit','submit_ps'),('dispatch','dispatch_ps'),('ordered','ordered_ps'),('tx_start','tx_start_ps'),('tx_end','tx_end_ps'),('memory_commit','memory_ps'),('complete','complete_ps')]:
                matches=[e for e in timeline if e['event']==event]
                assert len(matches)==1 and matches[0]['time_ps']==r[column]
            chunks=[e for e in timeline if e['event']=='tx_chunk']
            offset=0; last=r['tx_start_ps']
            for e in chunks:
                assert e['offset']==offset and e['psn']==r['psn']
                assert e['time_ps']-last==e['bytes']*80
                offset+=e['bytes']; last=e['time_ps']
            assert offset==64+r['payload_bytes'] and last==r['tx_end_ps']
        for e in ev:
            t=e['time_ps']; j=e['jetty']-1
            if e['event']=='enqueue': queued[j]+=1; peak[j]=max(peak[j],queued[j])
            if e['event']=='dequeue': queued[j]-=1
            if start<=t<=end:
                for k in range(3): minimum[k]=min(minimum[k],queued[k])
            if e['event']=='tx_end' and start<=t<end: requests[j]+=1
            if e['event']=='tx_chunk':
                # 100 Gbps = 80 ps/byte, overlap removes window edge bias.
                duration=e['bytes']*80
                overlap=max(0,min(t,end)-max(t-duration,start))
                wire[j]+=overlap/80
                if e['offset']>=64: payload[j]+=overlap/80
        assert all(v==0 for v in queued)
        # Exact enqueue/dequeue callbacks: every Jetty retains ready work
        # throughout the entire measurement window (with >1 WR margin).
        assert min(minimum)>1, (prefix,'fairness window lacks backlog',minimum)
        bits=sum(r['payload_bytes'] for r in wr)*8
        result=dict(workload=load,policy=policy,wr_count=len(wr),payload_bytes=bits//8,
            makespan_ns=(finish-begin)/1000,payload_gbps=bits*1000/(finish-begin),
            p50_ns=quantile(latency,.50),p99_ns=quantile(latency,.99),
            wire_jain=jain(wire),payload_jain=jain(payload),request_jain=jain(requests),
            window_start_ns=start/1000,window_end_ns=end/1000,
            window_link_utilization=sum(wire)*80/(end-start))
        summaries.append(result)
        for j in range(3):
            group=[r for r in wr if r['jetty']==j+1]
            lat=[(r['complete_ps']-r['submit_ps'])/1000 for r in group]
            per_jetty.append(dict(workload=load,policy=policy,jetty=j+1,
                batch_payload_gbps=sum(r['payload_bytes'] for r in group)*8*1000/(finish-begin),
                p50_ns=quantile(lat,.5),p99_ns=quantile(lat,.99),
                window_wire_bytes=wire[j],window_payload_bytes=payload[j],
                window_wire_gbps=wire[j]*8000/(end-start),
                window_payload_gbps=payload[j]*8000/(end-start),
                window_completed_wire_wrs=requests[j],
                peak_queued_wr=peak[j],window_min_queued_wr=minimum[j]))
for name,rows in [('summary.csv',summaries),('per_jetty.csv',per_jetty)]:
    with (root/name).open('w') as f:
        out=csv.DictWriter(f,fieldnames=list(rows[0])); out.writeheader(); out.writerows(rows)
for r in summaries:
    print(f"{r['workload']:5} {r['policy']:4} {r['payload_gbps']:.3f} Gbps  P50 {r['p50_ns']:.2f} ns  P99 {r['p99_ns']:.2f} ns  wire J {r['wire_jain']:.5f}  payload J {r['payload_jain']:.5f}")

# Optional controlled link-rate perturbation: same SystemC workload at 50 Gbps.
slow=root/'drr_mixed_50gbps.wr.csv'
if slow.exists():
    rows=read(slow)
    duration=max(r['complete_ps'] for r in rows)-min(r['submit_ps'] for r in rows)
    base=next(r for r in summaries if r['workload']=='mixed' and r['policy']=='drr')
    assert duration/1000 > 1.9*base['makespan_ns']
    result={'100': {'makespan_ns':base['makespan_ns'],'payload_gbps':base['payload_gbps']},
            '50': {'makespan_ns':duration/1000,'payload_gbps':sum(r['payload_bytes'] for r in rows)*8000/duration}}
    (root/'bottleneck_check.json').write_text(json.dumps(result,indent=2)+'\n')
