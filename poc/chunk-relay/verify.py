"""Fail closed on incomplete, early, duplicate or non-overlapping relay evidence."""
import csv, json, sys
from pathlib import Path

class EvidenceError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise EvidenceError(str(message))

def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))

def verify(path, sizes=(65536, 262144), segment=8192, compute_ns=5000):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for index, r in enumerate(rows):
        r["index"] = index
        for k in ('time_ps', 'hop', 'chunk', 'offset', 'bytes'):
            r[k] = int(r[k])
    require(all((a['time_ps'] <= b['time_ps'] for a, b in zip(rows, rows[1:]))), 'time reversal')

    def select(e, h, c):
        return [r for r in rows if r['event'] == e and r['hop'] == h and (r['chunk'] == c)]

    def one(e, h, c):
        rs = select(e, h, c)
        require(len(rs) == 1, (e, h, c, len(rs)))
        return rs[0]['time_ps']
    for h in range(2):
        for c, n in enumerate(sizes):
            send = one('chunk_send', h, c)
            done = one('chunk_complete', h, c)
            sender = one('sender_wqe_complete', h, c)
            received = select('target_ta_received', h, c)
            completed = select('target_ta_complete', h, c)
            checked = select('payload_bytes_verified', h, c)
            expected = [(o, min(segment, n - o)) for o in range(0, n, segment)]
            require(sorted(((r['offset'], r['bytes']) for r in completed)) == expected, 'missing/duplicate/wrong TA')
            require(sorted(((r['offset'], r['bytes']) for r in checked)) == expected, 'missing byte verification')
            require([(r['offset'], r['bytes'], r['time_ps']) for r in received] == [(r['offset'], r['bytes'], r['time_ps']) for r in completed], 'invalid event evidence')
            require(all((send < r['time_ps'] <= done for r in completed)), 'early completion')
            require(done == max((r['time_ps'] for r in completed)) and sender > done, 'invalid event evidence')
            stages = ['ta_send_admitted','target_ta_received','payload_bytes_verified','target_ta_complete']
            paired=[]
            for stage in stages:
                records=select(stage,h,c)
                require(sorted((r['offset'],r['bytes']) for r in records)==expected, 'wrong identity/range: '+stage)
                paired.append({r['offset']:r for r in records})
            for offset,length in expected:
                chain=[p[offset] for p in paired]
                require(all(a['index']<b['index'] and a['time_ps']<=b['time_ps'] for a,b in zip(chain,chain[1:])), 'TA stage ordering')
                require(chain[0]['time_ps']>=send and chain[0]['time_ps']<chain[1]['time_ps'], 'TA admission/receive timing')
    for c in range(2):
        ready = one('chunk_complete', 0, c)
        require(one('forward', 0, c) == one('chunk_send', 1, c) == ready, 'forward dependency')
        require(one('compute_start', 0, c) == ready, 'invalid event evidence')
        require(one('compute_end', 0, c) - ready == compute_ns * 1000, 'invalid event evidence')
    require(one('forward', 0, 0) < one('chunk_complete', 0, 1), 'chunk barrier')
    start = max(min((r['time_ps'] for r in select('ta_send_admitted', 0, 1))), min((r['time_ps'] for r in select('ta_send_admitted', 1, 0))))
    end = min(one('chunk_complete', 0, 1), one('chunk_complete', 1, 0))
    require(overlap((start, end), (start, end)) > 0, 'no communication overlap')
    for h, c in ((0, 1), (1, 0)):
        require(any((start < r['time_ps'] < end for r in select('target_ta_received', h, c))), 'invalid event evidence')
    compute_overlap = overlap((one('compute_start', 0, 0), one('compute_end', 0, 0)), (start, end))
    require(compute_overlap > 0, 'no compute/communication overlap')
    return {'communication_overlap_ps': end - start, 'compute_overlap_ps': compute_overlap, 'C_chunks': 2, 'target_TAs': sum((len(select('target_ta_complete', h, c)) for h in range(2) for c in range(2))), 'integrity': 'explicit payload bytes checked individually at B and C; B forwards received bytes; identity, coverage and length checked'}
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('path')
    p.add_argument('--sizes', type=int, nargs=2, default=[65536, 262144])
    p.add_argument('--segment', type=int, default=8192)
    p.add_argument('--compute-ns', type=int, default=5000)
    a = p.parse_args()
    print(json.dumps(verify(a.path, a.sizes, a.segment, a.compute_ns), indent=2))
