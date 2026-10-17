#!/usr/bin/env python3
"""Compare plans exactly, excluding only measured host planner wall time."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
x=json.loads(a.old.read_text());y=json.loads(a.new.read_text());excluded={'cpu_wall_ns'}
changes=[k for k in x.keys()|y.keys() if x.get(k)!=y.get(k)];assert set(changes)<=excluded,changes
result=dict(status='PASS',changed_fields=changes,excluded_fields=sorted(excluded),compared_fields=sorted(x.keys()-excluded),old_sha256=hashlib.sha256(a.old.read_bytes()).hexdigest(),new_sha256=hashlib.sha256(a.new.read_bytes()).hexdigest(),note='cpu_wall_ns is measured host time, not modeled Planning Latency')
a.out.write_text(json.dumps(result,indent=2)+'\n');print('PASS exact logical plan')
