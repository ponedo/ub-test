#!/usr/bin/env python3
"""Compare current measured unicast arms with checked historical private archives."""
import argparse,json,hashlib,tarfile,io
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--historical',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[]
def digest(b):return hashlib.sha256(b).hexdigest()
for l in [0,37,52]:
 for strategy in ['no-balancing','direct','chunk-streaming']:
  archive=a.historical/f'layer-{l}'/strategy/'prepared-evidence';manifest=json.loads((archive/'manifest.json').read_text());parts=[]
  for p in manifest['parts']:
   b=(archive/p['name']).read_bytes();assert len(b)==p['bytes'] and digest(b)==p['sha256'];parts.append(b)
  data=b''.join(parts);assert digest(data)==manifest['archive_sha256'];current=a.private/f'L{l}'/strategy/'prepared/run'
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as t:
   def old(name):
    b=t.extractfile('run/'+name).read();m=manifest['files']['run/'+name];assert len(b)==m['bytes'] and digest(b)==m['sha256'];return b
   summary=json.loads(old('online-summary.json'));new=json.loads((current/'online-summary.json').read_text());summary.pop('verification_wall_ns',None);new.pop('verification_wall_ns',None);assert summary==new,(l,strategy,'summary')
   assert json.loads(old('simulator-metrics.json'))==json.loads((current/'simulator-metrics.json').read_text())
   files={}
   for name in ['input.txt','graph-input.txt','assignments.csv','weight-edges.csv']:
    before=old(name);after=(current/name).read_bytes();assert before==after,(l,strategy,name);files[name]=digest(after)
   old_plan=json.loads(old('plan.json'));new_plan=json.loads((current/'plan.json').read_text());old_plan.pop('cpu_wall_ns',None);new_plan.pop('cpu_wall_ns',None);assert old_plan==new_plan
   validation=json.loads((current/'validation.json').read_text());assert validation['status']=='PASS'
   rows.append(dict(layer=l,strategy=strategy,status='PASS',simulated_summary_equal=True,excluded_host_field='verification_wall_ns',metrics_equal=True,byte_exact_inputs=files,plan_equal_except_host_cpu_wall_ns=True,archive_sha256=manifest['archive_sha256']))
a.out.write_text(json.dumps(dict(status='PASS',cases=rows,historical_commit='6a870170b0519267efff6a73a6be38ee575280ae',current_implementation='a848419aa4324668c7a17cefbf1ee601ce60d9eb'),indent=2)+'\n');print('All nine historical baseline comparisons PASS')
