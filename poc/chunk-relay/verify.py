#!/usr/bin/env python3
"""Fail closed on incomplete, early, duplicate or non-overlapping relay evidence."""
import csv, json, sys
from pathlib import Path

def overlap(a,b):
    return max(0,min(a[1],b[1])-max(a[0],b[0]))

def verify(path, sizes=(65536,262144), segment=8192, compute_ns=5000):
    with open(path) as f: rows=list(csv.DictReader(f))
    for r in rows:
        for k in ('time_ps','hop','chunk','offset','bytes'): r[k]=int(r[k])
    assert all(a['time_ps']<=b['time_ps'] for a,b in zip(rows,rows[1:])), 'time reversal'
    def select(e,h,c): return [r for r in rows if r['event']==e and r['hop']==h and r['chunk']==c]
    def one(e,h,c):
        rs=select(e,h,c); assert len(rs)==1,(e,h,c,len(rs)); return rs[0]['time_ps']
    for h in range(2):
        for c,n in enumerate(sizes):
            send=one('chunk_send',h,c)
            done=one('chunk_complete',h,c)
            sender=one('sender_wqe_complete',h,c)
            received=select('target_ta_received',h,c)
            completed=select('target_ta_complete',h,c)
            checked=select('payload_bytes_verified',h,c)
            expected=[(o,min(segment,n-o)) for o in range(0,n,segment)]
            assert sorted((r['offset'],r['bytes']) for r in completed)==expected,'missing/duplicate/wrong TA'
            assert sorted((r['offset'],r['bytes']) for r in checked)==expected,'missing byte verification'
            assert [(r['offset'],r['bytes'],r['time_ps']) for r in received]==[(r['offset'],r['bytes'],r['time_ps']) for r in completed]
            assert all(send<r['time_ps']<=done for r in completed),'early completion'
            assert done==max(r['time_ps'] for r in completed) and sender>done
            assert len(select('ta_send_admitted',h,c))==len(expected)
    for c in range(2):
        ready=one('chunk_complete',0,c)
        assert one('forward',0,c)==one('chunk_send',1,c)==ready,'forward dependency'
        assert one('compute_start',0,c)==ready
        assert one('compute_end',0,c)-ready==compute_ns*1000
    assert one('forward',0,0)<one('chunk_complete',0,1),'chunk barrier'
    # Communication intervals use actual TA admission and target events, not just WQE submission.
    start=max(min(r['time_ps'] for r in select('ta_send_admitted',0,1)),
              min(r['time_ps'] for r in select('ta_send_admitted',1,0)))
    end=min(one('chunk_complete',0,1),one('chunk_complete',1,0))
    assert overlap((start,end),(start,end))>0,'no communication overlap'
    # Witness actual target traffic on BOTH hops within the overlap interval.
    for h,c in ((0,1),(1,0)):
        assert any(start<r['time_ps']<end for r in select('target_ta_received',h,c))
    compute_overlap=overlap((one('compute_start',0,0),one('compute_end',0,0)),(start,end))
    assert compute_overlap>0,'no compute/communication overlap'
    return {'communication_overlap_ps':end-start,'compute_overlap_ps':compute_overlap,
            'C_chunks':2,'target_TAs':sum(len(select('target_ta_complete',h,c)) for h in range(2) for c in range(2)),
            'integrity':'explicit payload bytes checked individually at B and C; B forwards received bytes; identity, coverage and length checked'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('path'); p.add_argument('--sizes',type=int,nargs=2,default=[65536,262144])
    p.add_argument('--segment',type=int,default=8192); p.add_argument('--compute-ns',type=int,default=5000)
    a=p.parse_args()
    print(json.dumps(verify(a.path,a.sizes,a.segment,a.compute_ns),indent=2))
