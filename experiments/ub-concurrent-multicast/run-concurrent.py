#!/usr/bin/env python3
import argparse,json,sys,subprocess
from pathlib import Path
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for name,scenario,window,pressure,fault in [('same-source','same-source',1000,False,''),('different-source','different-source',1000,False,''),('dynamic','dynamic',1000,False,''),('window','window',1,False,''),('pressure','same-source',1000,True,''),('duplicate','same-source',1000,False,'duplicate'),('wrong','same-source',1000,False,'wrong'),('missing','same-source',1000,False,'missing'),('wrong-task','same-source',1000,False,'wrong-task')]:
 dest=a.out/name;cmd=[a.binary,'--out='+str(dest),'--scenario='+scenario,'--window='+str(window),'--pressure='+str(int(pressure))]+(['--fault='+fault] if fault else [])
 r=run(cmd,a.out/(name+'-host'),3600,case=a.out);row={'case':name,'host':{k:r[k] for k in ('status','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','returncode','guard')}};rows.append(row)
 if fault:
  reason={'duplicate':'duplicate multicast feedback','wrong':'multicast feedback endpoint','missing':'unfinished multicast group','wrong-task':'multicast feedback task/endpoint mismatch'}[fault];assert r['returncode'] and not r['guard'] and reason in (a.out/(name+'-host')/'console.txt').read_text();assert not (dest/'summary.json').exists();row.update(status='EXPECTED_REJECTION',reason=reason)
 else:
  assert r['status']=='PASS';subprocess.run([sys.executable,X/'verify-concurrent.py',dest,'--scenario',scenario if name!='pressure' else 'pressure'],check=True);row.update(status='PASS',validation=json.loads((dest/'independent-validation.json').read_text()))
  if name=='window':assert any(int(g['window_waits'])>0 for g in __import__('csv').DictReader((dest/'groups.csv').open()))
 (a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
