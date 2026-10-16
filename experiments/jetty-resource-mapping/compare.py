#!/usr/bin/env python3
"""Read-only summary/parity comparison; prints JSON, never alters runs or launches work."""
import argparse
import json
from pathlib import Path
from harness import parity

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--raw', type=Path, required=True)
p.add_argument('--a', type=Path)
p.add_argument('--b', type=Path)
p.add_argument('--mode', choices=['bytewise','logical'], default='bytewise')
a = p.parse_args()
rows = []
for path in sorted(a.raw.glob('*/attempt.json')):
    r = json.loads(path.read_text())
    resource = r.get('stages',{}).get('ns3',{})
    rows.append(dict(path=str(path.parent), arm=r['arm'],assignments=r['assignments'],phase=r['phase'],
                     status=r['status'],error=r.get('error'),wall_seconds=resource.get('wall_seconds'),
                     cpu_seconds=resource.get('user_cpu_seconds',0)+resource.get('system_cpu_seconds',0),
                     peak_rss_kib=resource.get('peak_rss_kib'),guard=resource.get('guard'),parity=r.get('parity')))
result = {'attempts':rows,'note':'Fresh single trials; profiler runs are not timing controls. Failed and incomplete attempts are retained.'}
if bool(a.a) != bool(a.b):
    p.error('Pass both --a and --b')
if a.a:
    result['comparison'] = parity(a.a,a.b,a.mode)
    records = [json.loads((path / 'attempt.json').read_text()) for path in (a.a,a.b)]
    result['comparison']['successful_attempts'] = all(r['status']=='success' for r in records)
    result['comparison']['same_inputs'] = records[0]['input_hashes'] == records[1]['input_hashes']
    result['comparison']['eligible'] = result['comparison']['pass'] and result['comparison']['successful_attempts'] and result['comparison']['same_inputs']
    resources = [r.get('stages',{}).get('ns3',{}) for r in records]
    for metric in ('wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib'):
        av,bv = (r.get(metric) for r in resources)
        result['comparison'][metric] = {'a':av,'b':bv,'b_over_a':bv/av if av and bv is not None else None}
print(json.dumps(result,indent=2))
