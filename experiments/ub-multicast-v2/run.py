#!/usr/bin/env python3
import argparse,csv,json,sys,resource
from pathlib import Path
if not __debug__:raise RuntimeError('Assertions must remain enabled')
h=Path(__file__).resolve().parent
sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out=a.out.resolve();a.build=a.build.resolve()
if a.out.exists():raise SystemExit('fresh output required')
a.out.mkdir(parents=True);resource.setrlimit(resource.RLIMIT_CORE,(0,0));rows=[]
def stage(cmd,name,negative=None):
 r=run(cmd,a.out/(name+'-host'),3600,case=a.out)
 if negative:
  assert r['returncode']!=0 and not r['guard'] and negative in (a.out/(name+'-host/console.txt')).read_text()
 else:assert r['status']=='PASS',name
 return r
stage([a.build/'codec-test'],'codec')
stage([a.build/'association-test'],'association')
for fault,reason in [('duplicate','unknown/consumed'),('missing','unknown/consumed'),('expired','expired/duplicate'),('member','expired/duplicate'),('header','actual protocol identity')]:
 stage([a.build/'association-test',fault],'association-'+fault,reason)
for label,n,scenario,pressure,window in [('12k',12288,'basic',0,1000),('64k',65536,'basic',0,1000),('dynamic',12288,'dynamic',0,1000),('competition',12288,'competition',0,1000),('pressure',12288,'basic',1,1000),('window',12288,'basic',0,2),('mixed',12288,'basic',0,1000),('dwrr',12288,'basic',1,1000)]:
 for mode in (['v2'] if label in ['mixed','dwrr'] else ['v1','v2']):
  name=label+'-'+mode;case=a.out/name
  r=stage([a.build/'micro','--out='+str(case),'--mode='+mode,'--bytes='+str(n),'--scenario='+scenario,'--pressure='+str(pressure),'--window='+str(window),'--mixed='+str(int(label=='mixed')),'--dwrr='+str(int(label=='dwrr'))],name)
  stage([sys.executable,h/'verify.py',case],name+'-verify')
  s=json.loads((case/'summary.json').read_text());v=json.loads((a.out/(name+'-verify-host/console.txt')).read_text())
  ev=list(csv.DictReader((case/'events.csv').open()));ports=list(csv.DictReader((case/'ports.csv').open()))
  row=dict(case=name,mode=mode,bytes=n,source_data_bytes=s['source_data_wire_bytes'],switch_data_bytes=v['switch_data_wire'],source_packets=s['envelopes'],branches=s['branches'],group_complete_ps=max(int(e['time_ps']) for e in ev if e['event']=='group_complete'),receiver_ready_ps={str(rank):max(int(e['time_ps']) for e in ev if e['event']=='receiver_ready' and int(e['rank'])==rank) for rank in [1,2,3]},sender_complete_ps={str(rank):max(int(e['time_ps']) for e in ev if e['event']=='sender_complete' and int(e['rank'])==rank) for rank in [1,2,3]},wall_seconds=r['wall_seconds'],cpu_seconds=r['user_cpu_seconds']+r['system_cpu_seconds'],rss_kib=r['peak_rss_kib'],blocked_queries=s['blocked_queries'],peak_egress_bytes=max(int(x['peak']) for x in ports),status='PASS')
  rows.append(row);(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
for mode in ['v1','v2']:
 for fault,reason in [('missing','unfinished group'),('duplicate','duplicate feedback detected'),('wrong','feedback kind/member')]:
  name='fault-'+mode+'-'+fault
  stage([a.build/'micro','--out='+str(a.out/name),'--mode='+mode,'--bytes=12288','--fault='+fault],name,reason)
stage([a.build/'micro','--out='+str(a.out/'fault-v2-payload'),'--mode=v2','--bytes=12288','--fault=payload'],'fault-v2-payload','target payload')
print('PASS bounded matrix')
