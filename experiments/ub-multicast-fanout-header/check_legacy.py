#!/usr/bin/env python3
"""Exact small Debug byte/event parity using original headers and the same fixture."""
import argparse,json,sys,hashlib
from pathlib import Path
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);records=[]
for case,f,strategy in [('singleton',1,'multicast'),('direct',4,'direct'),('chunk',4,'chunk-streaming'),('multicast',8,'multicast')]:
 for label,binary in [('old',a.old),('new',a.new)]:
  dest=a.out/case/label
  result=run([binary,'--out='+str(dest),'--fanout='+str(f),'--bytes=12288','--strategy='+strategy,'--headerModel=full','--logLevel=debug'],a.out/'hosts'/case/label,3600,case=a.out)
  assert result['status']=='PASS',(case,label)
  result=run([sys.executable,X/'verify.py',dest,'--out',dest/'postflight.json'],a.out/'hosts'/case/(label+'-postflight'),3600,case=a.out);assert result['status']=='PASS'
 old=a.out/case/'old';new=a.out/case/'new';files=['events.csv','wire.csv','ta-identity.csv','ta-audit.csv','executed-transfers.csv','task-timeline.csv','receiver-stats.csv','targets.csv','packet-counts.csv','packet-sizes.csv','ports.csv','queue-stats.csv','native-final-state.csv','fanout-summary.json','header-accounting.csv','replication-state.csv']
 checks=[]
 for name in files:
  x=(old/name).read_bytes();y=(new/name).read_bytes();assert x==y,(case,name);checks.append(dict(file=name,sha256=hashlib.sha256(x).hexdigest(),bytes_equal=True))
 s=json.loads((old/'online-summary.json').read_text());t=json.loads((new/'online-summary.json').read_text());s.pop('verification_wall_ns');t.pop('verification_wall_ns');assert s==t
 records.append(dict(case=case,fanout=f,strategy=strategy,status='PASS',online_simulated_fields_equal=True,files=checks));(a.out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
print('LEGACY FULL DEBUG EXACT',len(records))
