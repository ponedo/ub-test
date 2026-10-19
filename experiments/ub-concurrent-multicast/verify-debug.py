#!/usr/bin/env python3
import argparse,importlib.util,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--debug',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();E=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('pair_verify',E/'pair-jetty/verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);rows=[]
for strategy in ['direct','chunk-streaming','multicast']:
 d=a.debug/strategy;s=a.summary/strategy;v=m.verify(d,'pair')
 x=json.loads((s/'online-summary.json').read_text());y=json.loads((d/'online-summary.json').read_text())
 for row in (x,y):
  for field in ['verification_wall_ns','log_level']:row.pop(field,None)
 assert x==y,strategy
 rows.append(dict(strategy=strategy,status='PASS',all_simulation_summary_fields_identical=True,strict_debug_verifier='PASS',layer_latency_ps=x['layer_latency_ps']))
a.out.write_text(json.dumps(rows,indent=2)+'\n');print('PASS strict Debug and summary parity')
