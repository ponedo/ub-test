#!/usr/bin/env python3
"""Publish compact synthetic validation evidence, never whole private run directories."""
import argparse,csv,json,hashlib,shutil
from collections import defaultdict
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--single',type=Path,required=True);p.add_argument('--multi',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
def write(name,data):
 if not data:return
 with (a.out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
single=json.loads((a.single/'results.json').read_text());multi=json.loads((a.multi/'results.json').read_text());assert len(single)==7 and all(r['status']=='PASS' and r['shared_queue'] for r in single)
assert len(multi)==8 and all(r['status'] in ['PASS','EXPECTED_REJECTION'] for r in multi)
(a.out/'singleton-parity.json').write_text(json.dumps(single,indent=2)+'\n');(a.out/'multitarget-results.json').write_text(json.dumps(multi,indent=2)+'\n')
timing=[]
for item in single:
 e=rows(a.single/item['case']/'1/events.csv')
 for task in sorted({r['task'] for r in e if r['event']=='submit'}):
  ts={r['event']:int(r['time_ps']) for r in e if r['task']==task and r['event'] in ['submit','receiver_ready','sender_complete']}
  timing.append(dict(case=item['case'],task=task,**ts,receiver_elapsed_ps=ts['receiver_ready']-ts['submit'],sender_elapsed_ps=ts['sender_complete']-ts['submit']))
write('singleton-times.csv',timing)
timing=[];packets=[];ports=[];windows=[];negative=[]
for item in multi:
 case=a.multi/item['case'];e=rows(case/'events.csv')
 if item['status']=='EXPECTED_REJECTION':
  log=(a.multi/(item['case']+'-host')/'console.txt').read_text();negative.append({'case':item['case'],'status':item['status'],'returncode':item['host']['returncode'],'reason':item['reason'],'no_group_success':not any(r['event']=='group_complete' for r in e),'console_excerpt':log[:1800]})
  continue
 for row in [r for r in e if r['event']=='receiver_ready']:
  task,rank=row['task'],row['rank'];select=lambda name,rank=None:next(int(r['time_ps']) for r in e if r['event']==name and r['task']==task and (rank is None or r['rank']==rank))
  timing.append(dict(case=item['case'],task=task,rank=rank,submit_ps=select('group_submit'),receiver_ready_ps=int(row['time_ps']),sender_complete_ps=select('sender_complete',rank),group_complete_ps=select('group_complete')))
 counts=defaultdict(lambda:[0,0])
 for r in rows(case/'wire.csv'):
  key=(r['node'],r['port'],r['event'],r['packet_class'],r['bytes']);counts[key][0]+=1;counts[key][1]+=int(r['bytes'])
 for (node,port,event,cls,size),(count,total) in sorted(counts.items()):packets.append(dict(case=item['case'],node=node,port=port,event=event,packet_class=cls,packet_bytes=size,packets=count,total_bytes=total))
 for r in rows(case/'ports.csv'):ports.append(dict(case=item['case'],**r))
 w=rows(case/'windows.csv')
 for rank in ['1','2','3']:
  r=[x for x in w if x['rank']==rank];last=r[-1]
  windows.append(dict(case=item['case'],rank=rank,peak_tp_packets=max(int(x['tp_nxt'])-int(x['tp_una']) for x in r),peak_ta_outstanding=max(int(x['ta_nxt'])-int(x['ta_una']) for x in r),peak_tp_segments=max(int(x['tp_outstanding']) for x in r),final_tp_outstanding=int(last['tp_nxt'])-int(last['tp_una']),final_ta_outstanding=int(last['ta_nxt'])-int(last['ta_una'])))
write('multitarget-times.csv',timing);write('packet-counts.csv',packets);write('ports.csv',ports);write('windows-summary.csv',windows)
(a.out/'negative-feedback.json').write_text(json.dumps(negative,indent=2)+'\n')
# Small exact A/B wire proof and one application-level multi-target timeline.
for mode in ['0','1']:
 for name in ['wire.csv','events.csv','ports.csv']:shutil.copyfile(a.single/'small'/mode/name,a.out/f'singleton-small-{mode}-{name}')
for name in ['events.csv','wire.csv','ports.csv','independent-validation.json']:shutil.copyfile(a.multi/'three-target'/name,a.out/('three-target-'+name))
shutil.copyfile(a.multi/'window/windows.csv',a.out/'window-events.csv')
manifest=[]
for f in sorted(a.out.iterdir()):manifest.append({'path':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(a.out/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
