"""Unified WR results 1.0: timestamps and byte service from actual SystemC events."""
import argparse
import csv
import json
import math
from collections import Counter,defaultdict
from pathlib import Path


def percentile(values,q):
    if not values:return None
    values=sorted(values);x=(len(values)-1)*q;a=math.floor(x);b=math.ceil(x)
    return (values[a]*(b-x)+values[b]*(x-a)) if a!=b else values[a]


def jain(values):
    return sum(values)**2/(len(values)*sum(v*v for v in values)) if values and any(values) else None


def common_backlogged_window(directories):
    """Longest intersection of all-Jetty queued intervals; no service/Jain input."""
    intersection=None
    for directory in directories:
        directory=Path(directory)
        with (directory/'systemc.wr.csv').open() as f:jets={int(r['jetty_id']) for r in csv.DictReader(f)}
        queues=dict.fromkeys(jets,0);intervals=[];begin=None
        with (directory/'systemc.events.csv').open() as f:
            for e in csv.DictReader(f):
                event=e['event']
                if event not in ('enqueue','dequeue'):continue
                j=int(e['jetty']);t=int(e['time_ps']);queues[j]+=1 if event=='enqueue' else -1
                active=bool(jets) and all(v>0 for v in queues.values())
                if active and begin is None:begin=t
                if not active and begin is not None:
                    if t>begin:intervals.append((begin,t))
                    begin=None
        if intersection is None:intersection=intervals
        else:
            intersection=[(max(a,c),min(b,d)) for a,b in intersection for c,d in intervals if max(a,c)<min(b,d)]
    if not intersection:return None
    # Conservative inward integer-ns rounding avoids same-timestamp queue transients.
    windows=[(a//1000+1,b//1000) for a,b in intersection if a//1000+1<b//1000]
    return max(windows,key=lambda v:(v[1]-v[0],-v[0])) if windows else None


def analyze(directory,start_ns,end_ns):
    directory=Path(directory)
    manifest=json.loads((directory/'run.json').read_text())
    with (directory/'systemc.wr.csv').open() as f:
        rows=[{k:(v if k=='phase' else int(v)) for k,v in r.items()} for r in csv.DictReader(f)]
    by_id={r['wr_id']:r for r in rows};assert len(by_id)==len(rows)
    jets=sorted({r['jetty_id'] for r in rows});queues=dict.fromkeys(jets,0);minimum=dict.fromkeys(jets,math.inf)
    wire=dict.fromkeys(jets,0.);payload=dict.fromkeys(jets,0.)
    counts=Counter();per_wr=defaultdict(Counter);tx_end_bytes=Counter();ack_end_bytes=Counter()
    start,end=int(start_ns*1000),int(end_ns*1000);assert 0<=start<end
    opened=False;previous=-1
    timestamps={'ready':'ready_ps','eligible':'eligible_ps','submit':'submit_ps','enqueue':'enqueue_ps','dequeue':'dequeue_ps',
                'dispatch':'dispatch_ps','ordered':'ordered_ps','tx_start':'tx_start_ps','tx_end':'tx_end_ps','memory_commit':'memory_ps','complete':'complete_ps'}
    with (directory/'systemc.events.csv').open() as f:
        for e in csv.DictReader(f):
            t=int(e['time_ps']);assert t>=previous;previous=t
            event=e['event'];r=by_id[int(e['wr_id'])];j=int(e['jetty']);n=int(e['bytes']);offset=int(e['offset'])
            assert j==r['jetty_id'] and int(e['src_node'])==r['src_node'] and int(e['dst_node'])==r['dst_node'] and int(e['sequence'])==r['sequence']
            if not opened and t>=start:minimum=queues.copy();opened=True
            if event=='enqueue':queues[j]+=1
            if event=='dequeue':queues[j]-=1;assert queues[j]>=0
            if start<=t<end:
                for jet in jets:minimum[jet]=min(minimum[jet],queues[jet])
            counts[event]+=1;per_wr[r['wr_id']][event]+=1
            if event in timestamps:assert t==r[timestamps[event]]
            if event=='tx_chunk':
                assert offset==tx_end_bytes[r['wr_id']]
                tx_end_bytes[r['wr_id']]+=n
                assert t==r['tx_start_ps']+(offset+n)*80 # 100 Gbps; integer ps.
                a=t-n*80;b=t
                wire[j]+=max(0,min(b,end)-max(a,start))/80
                pa=max(a,r['tx_start_ps']+64*80)
                payload[j]+=max(0,min(b,end)-max(pa,start))/80
            if event=='ack_chunk':
                assert offset==ack_end_bytes[r['wr_id']];ack_end_bytes[r['wr_id']]+=n
    for r in rows:
        for e in timestamps:assert per_wr[r['wr_id']][e]==1,(r['wr_id'],e)
        for e in ('rx_wire','ack_tx_start','ack_tx_end','ack_rx_wire'):assert per_wr[r['wr_id']][e]==1
        assert tx_end_bytes[r['wr_id']]==r['payload_bytes']+64
        assert ack_end_bytes[r['wr_id']]==64
    assert not any(queues.values())
    if not opened:minimum=queues.copy()
    origin=min((r['ready_ps'] for r in rows),default=0);finish=max((r['complete_ps'] for r in rows),default=origin)
    span=finish-origin
    def latency(rs):
        result={}
        for label,a,b in [('ready_to_complete','ready_ps','complete_ps'),('submit_to_complete','submit_ps','complete_ps'),
                          ('queue_wait','submit_ps','dequeue_ps'),('admission_wait','ready_ps','submit_ps'),
                          ('scheduler_wait','enqueue_ps','dequeue_ps')]:
            v=[(r[b]-r[a])/1000 for r in rs]
            result[label+'_ns']={'p50':percentile(v,.5),'p99':percentile(v,.99),'mean':sum(v)/len(v) if v else None}
        return result
    valid=bool(rows) and opened and end<=finish and all(v>0 for v in minimum.values())
    result={'result_schema':'wr-results/1.0','policy':manifest['policy'],'trace_sha256':manifest['trace_sha256'],
            'wr_count':len(rows),'payload_bytes':sum(r['payload_bytes'] for r in rows),'origin_ps':origin,'finish_ps':finish,
            'makespan_ns':span/1000,'payload_throughput_gbps':sum(r['payload_bytes'] for r in rows)*8000/span if span else None,
            **latency(rows),'per_jetty':{str(j):{'wr_count':sum(r['jetty_id']==j for r in rows),
              'payload_bytes':sum(r['payload_bytes'] for r in rows if r['jetty_id']==j),
              'payload_throughput_gbps':sum(r['payload_bytes'] for r in rows if r['jetty_id']==j)*8000/span if span else None,
              **latency([r for r in rows if r['jetty_id']==j])} for j in jets},
            'fairness':{'window_ns':[start_ns,end_ns],'valid_all_jetties_backlogged':valid,
                        'minimum_scheduler_queue':minimum,'wire_bytes':wire,'payload_bytes':payload,
                        'wire_jain':jain(list(wire.values())) if valid else None,'payload_jain':jain(list(payload.values())) if valid else None,
                        'invalid_reason':None if valid else 'all active Jetties were not continuously queued over the whole requested window'},
            'event_counts':dict(counts)}
    (directory/'metrics.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory');p.add_argument('--window-ns',nargs=2,type=int,required=True);a=p.parse_args()
    print(json.dumps(analyze(a.directory,*a.window_ns),indent=2,sort_keys=True))
if __name__=='__main__':main()
