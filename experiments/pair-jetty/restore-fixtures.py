#!/usr/bin/env python3
"""Extract immutable input-only fixtures from this delivery's retained gate outputs."""
import argparse,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);count=0
for gate in ['gate-b','gate-c']:
 for source in sorted((a.raw/gate).glob('*/per-wqe/run/input.txt')):
  source=source.parent;case=source.parents[1].name
  mode=next((m for m in ['no-balancing','chunk-streaming','two-stage','direct'] if case.endswith('-'+m)),None)
  if mode is None:raise ValueError('Unrecognized fixture '+case)
  dest=a.out/case[:-len(mode)-1]/mode;dest.mkdir(parents=True)
  for name in ['input.txt','config.json','plan.json','assignments.csv','transfers.csv','graph-input.txt','weight-edges.csv']:
   if (source/name).exists():shutil.copy2(source/name,dest/name)
  count+=1
if count!=48:raise ValueError('Expected all 48 retained fixtures, found '+str(count))
print('Restored',count,'input-only fixtures')
