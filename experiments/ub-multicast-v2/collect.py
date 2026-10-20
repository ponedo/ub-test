#!/usr/bin/env python3
"""Publish compact evidence only; leave payload and full trace files private."""
import argparse,csv,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);m=a.private/'matrix'
def dump(name,obj):(a.out/name).write_text(json.dumps(obj,indent=2)+'\n')
rows=json.loads((m/'results.json').read_text());dump('microbench.json',rows)
resources=[]
for f in sorted(a.private.rglob('resource.json')):
 r=json.loads(f.read_text());resources.append(dict(stage=str(f.parent.relative_to(a.private)),**{k:r[k] for k in ['status','returncode','guard','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','limits']}))
dump('host-resources.json',resources)
dump('codec.json',json.loads((m/'codec-host/console.txt').read_text()))
negative=[]
for f in sorted(m.glob('*-host/resource.json')):
 if f.parent.name.startswith(('association-', 'fault-')) and f.parent.name!='association-host':
  r=json.loads(f.read_text());text=(f.parent/'console.txt').read_text();assert r['returncode']!=0 and r['guard'] is None
  negative.append(dict(case=f.parent.name,observed_status=r['status'],returncode=r['returncode'],guard=r['guard'],interpretation='EXPECTED_REJECTION',diagnostic=text[:1800]))
dump('negative.json',negative)
summaries={};target=[];port=[];packet=[];hashes=[]
for r in rows:
 case=m/r['case'];summaries[r['case']]=json.loads((case/'summary.json').read_text())
 ev=list(csv.DictReader((case/'events.csv').open()))
 submit={e['task']:int(e['time_ps']) for e in ev if e['event']=='group_submit'}
 for e in ev:
  if e['event'] in ['receiver_ready','sender_complete','group_complete']:target.append(dict(case=r['case'],**e,duration_ps=int(e['time_ps'])-submit[e['task']]))
 for x in csv.DictReader((case/'ports.csv').open()):port.append(dict(case=r['case'],**x))
 counts={}
 for x in csv.DictReader((case/'wire.csv').open()):
  if x['event']!='tx':continue
  key=(x['node'],x['port'],x['packet_class']);v=counts.setdefault(key,[0,0]);v[0]+=1;v[1]+=int(x['bytes'])
 for (node,prt,kind),(count,size) in sorted(counts.items()):packet.append(dict(case=r['case'],node=node,port=prt,kind=kind,packets=count,wire_bytes=size))
 for f in sorted(case.iterdir()):
  if f.is_file():hashes.append(dict(case=r['case'],file=f.name,bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
for name,data in [('targets.csv',target),('ports.csv',port),('packet-counts.csv',packet)]:
 with (a.out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
dump('case-checks.json',summaries);dump('private-evidence-hashes.json',hashes)
reg=a.private/'regressions'
if (reg/'stages.json').exists():dump('regression-stages.json',json.loads((reg/'stages.json').read_text()))
for src,name in [('singleton-results/results.json','singleton-parity.json'),('multi-results/results.json','full-multicast.json'),('application/results.json','direct-chunk.json')]:
 if (reg/src).exists():dump(name,json.loads((reg/src).read_text()))
if (a.private/'native-tests/summary.json').exists():dump('native-tests.json',json.loads((a.private/'native-tests/summary.json').read_text()))
