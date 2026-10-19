#!/usr/bin/env python3
import argparse,json,sys,subprocess,hashlib
from pathlib import Path
if not __debug__:raise RuntimeError("Correctness checks require assertions enabled")
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--private',type=Path,required=True);p.add_argument('--singleton-gate',type=Path,required=True);a=p.parse_args()
gate=json.loads(a.singleton_gate.read_text());assert len(gate)==7 and all(r['status']=='PASS' and r['shared_queue'] and r['adapter_sha256']==hashlib.sha256((X/'adapter.h').read_bytes()).hexdigest() and r['harness_sha256']==hashlib.sha256((X/'singleton.cc').read_bytes()).hexdigest() for r in gate)
a.private.mkdir(parents=True,exist_ok=False);ledger=[]
cases=[('three-target','basic',16384,1000,False,''),('dynamic','dynamic',8192,1000,False,''),('competition','competition',16384,1000,False,''),('window','basic',32768,1,False,''),('pressure','competition',16384,1000,True,''),('duplicate','basic',4096,1000,False,'duplicate'),('missing','basic',4096,1000,False,'missing'),('wrong','basic',4096,1000,False,'wrong')]
for name,scenario,size,window,pressure,fault in cases:
 out=a.private/name;cmd=[a.binary,'--out='+str(out),'--scenario='+scenario,'--bytes='+str(size),'--window='+str(window),'--pressure='+str(int(pressure))]
 if fault:cmd+=['--fault='+fault]
 r=run(cmd,a.private/(name+'-host'),3600,case=a.private);row={'case':name,'scenario':scenario,'bytes':size,'status':r['status'],'host':{k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','returncode','guard']}};ledger.append(row)
 if fault:
  text=(a.private/(name+'-host')/'console.txt').read_text();expected={'duplicate':'duplicate feedback detected','missing':'unfinished group: missing feedback','wrong':'feedback kind/member'}[fault]
  assert r['returncode']!=0 and not r['guard'] and expected in text
  assert not (out/'summary.json').exists()
  assert ',group_complete,' not in (out/'events.csv').read_text()
  row['status']='EXPECTED_REJECTION';row['reason']=expected
 else:
  if r['status']!='PASS':(a.private/'results.json').write_text(json.dumps(ledger,indent=2)+'\n');raise SystemExit(2)
  subprocess.run([sys.executable,X/'verify-multi.py',out,'--scenario',scenario,'--bytes',str(size),'--window',str(window)],check=True)
  row['summary']=json.loads((out/'summary.json').read_text());
  if name=='window':assert row['summary']['window_waits']>0
  row['validation']=json.loads((out/'independent-validation.json').read_text())
 (a.private/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
