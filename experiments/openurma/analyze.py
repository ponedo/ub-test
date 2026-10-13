# SPDX-License-Identifier: Apache-2.0
"""Analyze actual native-element SystemC output; never invent protocol completions."""
import csv,json,math
from pathlib import Path

def load(path):
    with Path(path).open() as f:return list(csv.DictReader(f))
def quantile(v,q):
    v=sorted(v);p=(len(v)-1)*q;a=math.floor(p);b=math.ceil(p)
    return v[a] if a==b else v[a]*(b-p)+v[b]*(p-a)
def jain(v):return sum(v)**2/(len(v)*sum(x*x for x in v)) if any(v) else None

def intervals(path):
    result=[];begin=None;last=0
    for r in load(path):
        t=int(r['time_ps']);active=all(int(r['q'+str(i)])>0 for i in range(3))
        if active and begin is None:begin=t
        if not active and begin is not None:result.append((begin,t));begin=None
        last=t
    if begin is not None and last>begin:result.append((begin,last))
    return result

def analyze(root):
    root=Path(root);summary=[];windows={}
    for scenario in ['equal','mixed']:
        common=None
        for policy in ['rr','drr']:
            for order in ['forward','reverse']:
                v=intervals(root/'patched'/policy/scenario/order/'component.queues.csv')
                common=v if common is None else [(max(a,c),min(b,d)) for a,b in common for c,d in v if max(a,c)<min(b,d)]
        window=max(common,key=lambda x:(x[1]-x[0],-x[0])) if common else None
        # Predeclared minimum: a full one-WR-per-Jetty service round at the
        # explicit 4 ns/flit sink. Shorter windows remain diagnostics, not claims.
        sizes=[256]*3 if scenario=='equal' else [64,256,1024]
        minimum=sum(2+(n+31)//32 for n in sizes)*4000
        valid=window is not None and window[1]-window[0]>=minimum
        windows[scenario]={'common_window_ps':window,'minimum_comparison_window_ps':minimum,'valid_for_fairness':valid,
            'rule':'longest intersection of sampled positive per-Jetty ring occupancy across both policies and both source orders; earliest tie',
            'occupancy_sampling_ps':1000,'invalid_reason':None if valid else 'common window shorter than one complete service round'}
        for policy in ['rr','drr']:
            for order in ['forward','reverse']:
                d=root/'patched'/policy/scenario/order
                wr=[{k:int(v) for k,v in r.items()} for r in load(d/'component.wr.csv')]
                by_id={r['wr_id']:r for r in wr};seen={};counts={k:0 for k in by_id};current=None;prev_time=-1
                payload=dict.fromkeys(range(3),0);channel=payload.copy();total_payload=payload.copy();total_channel=payload.copy()
                firstseq={};last_seq=-1
                for e in load(d/'component.events.csv'):
                    seq=int(e['event_seq']);t=int(e['time_ps']);assert seq==last_seq+1 and t>=prev_time;last_seq=seq;prev_time=t
                    id=int(e['wr_id']);index=int(e['flit_index']);jet=int(e['jetty']);event=e['event']
                    if event=='submit_flit':seen[id,index]=e['raw_hex']
                    if event=='receive':
                        assert seen[id,index]==e['raw_hex'];assert index==counts[id];counts[id]+=1
                        raw=bytes.fromhex(e['raw_hex']);assert len(raw)==64
                        if raw[32]&1:
                            assert current is None;current=id
                            assert by_id[id]['sequence']==firstseq.get(jet,0);firstseq[jet]=firstseq.get(jet,0)+1
                        assert current==id
                        if raw[32]&2:current=None
                        n=int(e['payload_bytes']);assert n==(32-raw[33] if index>=2 else 0)
                        total_payload[jet]+=n;total_channel[jet]+=64
                        if window and window[0]<=t<window[1]:payload[jet]+=n;channel[jet]+=64
                assert current is None
                for r in wr:assert counts[r['wr_id']]==r['flits']==r['received_flits'] and r['component_complete_ps']>0
                assert sum(total_payload.values())==sum(r['payload_bytes'] for r in wr)
                span=max(r['component_complete_ps'] for r in wr)-10000
                def stats(rs):
                    v=[(r['component_complete_ps']-10000)/1000 for r in rs]
                    wait=[(r['dispatch_ps']-r['submit_ps'])/1000 for r in rs]
                    return {'ready_to_component_eop_p50_ns':quantile(v,.5),'ready_to_component_eop_p99_ns':quantile(v,.99),
                            'submit_to_dispatch_p50_ns':quantile(wait,.5),'submit_to_dispatch_p99_ns':quantile(wait,.99)}
                r={'scenario':scenario,'policy':policy,'source_order':order,'wr_count':len(wr),'payload_bytes':sum(total_payload.values()),
                   'makespan_ns':span/1000,'component_payload_gbps':sum(total_payload.values())*8000/span,
                   'completion_semantics':'scheduler output EOP consumed by a 4 ns/flit sink; NOT target completion/ACK',
                   **stats(wr),'fairness':{**windows[scenario],'payload_bytes':payload,'internal_channel_bytes':channel,
                     'payload_jain':jain(list(payload.values())) if valid else None,'channel_jain':jain(list(channel.values())) if valid else None,
                     'short_window_diagnostic_payload_jain':jain(list(payload.values())),
                     'short_window_diagnostic_channel_jain':jain(list(channel.values()))},
                   'per_jetty':{j:{**stats([x for x in wr if x['jetty']==j]),'full_payload_share':total_payload[j]/sum(total_payload.values()),
                     'full_internal_channel_share':total_channel[j]/sum(total_channel.values()),
                     'window_payload_share':payload[j]/sum(payload.values()) if sum(payload.values()) else None,
                     'window_internal_channel_share':channel[j]/sum(channel.values()) if sum(channel.values()) else None} for j in range(3)}}
                (d/'metrics.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');summary.append(r)
    (root/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    (root/'windows.json').write_text(json.dumps(windows,indent=2,sort_keys=True)+'\n')
    with (root/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['scenario','policy','source_order','component_payload_gbps','makespan_ns','p50_ns','p99_ns','valid_fairness','payload_jain','internal_channel_jain'])
        for r in summary:w.writerow([r['scenario'],r['policy'],r['source_order'],r['component_payload_gbps'],r['makespan_ns'],r['ready_to_component_eop_p50_ns'],r['ready_to_component_eop_p99_ns'],r['fairness']['valid_for_fairness'],r['fairness']['payload_jain'],r['fairness']['channel_jain']])
    print('PASS: eight complete measured runs, raw byte/sequence/EOP audit, shared windows and metrics')
    return summary
if __name__=='__main__':
    import sys
    analyze(sys.argv[1] if len(sys.argv)>1 else 'experiments/openurma/results')
