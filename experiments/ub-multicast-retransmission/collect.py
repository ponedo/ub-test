#!/usr/bin/env python3
"""Publish compact evidence, never binaries, host inventories or Debug trace."""
import argparse,csv,json,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=a.private.resolve();o=a.out;o.mkdir(parents=True,exist_ok=False)
def write(name,value):(o/name).write_text(json.dumps(value,indent=2)+'\n')
case_results=json.loads((r/'matrix/results.json').read_text());payload=[];times=[]
for case in case_results:
 name=case['case'];c=r/'matrix'/name;dest=o/'cases'/name;dest.mkdir(parents=True)
 for f in ['events.csv','packets.csv','windows.csv','ports.csv','summary.json']:
  if (c/f).exists():shutil.copyfile(c/f,dest/f)
 case['outcome']='EXPECTED_NATIVE_ASSERT' if name=='persistent-exhaust' else json.loads((c/'summary.json').read_text())['status']
 host=json.loads((r/'matrix'/(name+'-host')/'resource.json').read_text());case['returncode']=host['returncode'];case['guard']=host['guard']
 if name=='persistent-exhaust':
  text=(r/'matrix'/(name+'-host')/'console.txt').read_text();(dest/'native-exhaustion.txt').write_text(text.replace(str(r.parent),'$ROOT'))
 for f in sorted(c.glob('payload-*.bin')):
  data=f.read_bytes();payload.append(dict(case=name,file=f.name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),complete=not(name in ['persistent-bounded','retrans-disabled'] and f.name.endswith('-1.bin'))))
 for row in csv.DictReader((c/'events.csv').open()):
  if row['event'] in ['group_submit','sender_complete','group_complete','drop','duplicate','native_retry']:times.append(dict(case=name,**row))
write('cases.json',case_results);write('payloads.json',payload)
with (o/'timeline.csv').open('w') as f:w=csv.DictWriter(f,['case']+list(times[0].keys())[1:]);w.writeheader();w.writerows(times)
resources=[]
for f in sorted(r.rglob('resource.json')):
 x=json.loads(f.read_text());resources.append(dict(stage=str(f.parent.relative_to(r)),**{k:x[k] for k in ['status','returncode','guard','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','limits']}))
write('host-resources.json',resources)
for name,file in [('v2-parity.json',r/'v2-parity.json'),('verifier-mutations.json',r/'verifier-mutations.json'),('v2-regression.json',r/'v2-regression/results.json'),('old-regression.json',r/'old-regression/stages.json')]:
 if file.exists():shutil.copyfile(file,o/name)
for name,sub in [('singleton-parity','singleton-results'),('full-multicast','multi-results'),('network-poc','network-collected'),('concurrent','concurrent-results'),('four-strategy','application')]:
 shutil.copyfile(r/'old-regression'/sub/'results.json',o/(name+'.json'))
print(json.dumps(dict(files=len(list(o.rglob('*'))),bytes=sum(p.stat().st_size for p in o.rglob('*') if p.is_file()))))
