#!/usr/bin/env python3
"""Sequential exact parity gate. A mismatch stops, never becomes a tolerated pass."""
import argparse,json,sys,hashlib,csv
from pathlib import Path
if not __debug__:raise RuntimeError("Correctness checks require assertions enabled")
X=Path(__file__).resolve().parent
sys.path.insert(0,str(X.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--shared',action='store_true');p.add_argument('--binary',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args();a.private.mkdir(parents=True,exist_ok=False)
cases=[('small',64,1,1024,1000,0,False),('multi-ta',4096,1,1024,1000,0,False),('concurrent',16384,3,1024,1000,0,False),('fragmented-ta',16384,3,8192,1000,0,False),('window',16384,8,1024,2,1000,False),('backpressure',32768,3,1024,1000,0,True),('delayed-switch',4096,3,1024,1000,0,False)]
ledger=[]
for name,size,count,seg,window,delay,pressure in cases:
 row={'case':name,'shared_queue':a.shared,'adapter_sha256':hashlib.sha256((X/'adapter.h').read_bytes()).hexdigest(),'harness_sha256':hashlib.sha256((X/'singleton.cc').read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'status':'RUNNING','runs':[]};ledger.append(row)
 for mode in [0,1]:
  out=a.private/name/str(mode)
  cmd=[a.binary,'--out='+str(out),'--adapter='+str(mode),'--bytes='+str(size),'--count='+str(count),'--segment='+str(seg),'--window='+str(window),'--delay='+str(delay),'--pressure='+str(int(pressure)),'--processing='+str(10 if name=='delayed-switch' else 0)]
  if mode and a.shared:cmd+=['--shared=1']
  r=run(cmd,a.private/name/('host-'+str(mode)),3600,case=a.private);row['runs'].append({k:r[k] for k in ['status','returncode','wall_seconds','peak_rss_kib','user_cpu_seconds','system_cpu_seconds','guard']})
  if r['status']!='PASS':
   row['status']='EXECUTION_FAILED';(a.private/'results.json').write_text(json.dumps(ledger,indent=2)+'\n');raise SystemExit(2)
 b=a.private/name/'0';c=a.private/name/'1';names=['wire.csv','events.csv','ports.csv']+[f'payload-{1001+i}.bin' for i in range(count)]
 row['files']=[]
 for file in names:
  x=(b/file).read_bytes();y=(c/file).read_bytes();row['files'].append({'name':file,'equal':x==y,'baseline_sha256':hashlib.sha256(x).hexdigest(),'candidate_sha256':hashlib.sha256(y).hexdigest()})
 row['candidate']=json.loads((c/'summary.json').read_text());row['status']='PASS' if all(f['equal'] for f in row['files']) else 'PARITY_MISMATCH'
 (a.private/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
 if row['status']!='PASS':raise SystemExit(3)
 print('EXACT PARITY',name,flush=True)
