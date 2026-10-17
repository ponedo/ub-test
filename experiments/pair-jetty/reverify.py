#!/usr/bin/env python3
"""Replay final strengthened oracle over retained completed experiment outputs."""
import argparse,importlib.util,json,time
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('pair_oracle',H/'verify.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
p=argparse.ArgumentParser();p.add_argument('roots',nargs='+',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[]
for root in a.roots:
 for path in sorted(root.glob('*/*/run/pair-validation.json')):
  case=path.parent;mode=case.parent.name;start=time.monotonic();v.verify(case,mode)
  row={'case':str(case),'mode':mode,'status':'PASS','wall_seconds':time.monotonic()-start,'validation':json.loads(path.read_text())};rows.append(row)
  a.out.write_text(json.dumps(rows,indent=2)+'\n')
print(len(rows),'PASS')
