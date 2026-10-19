#!/usr/bin/env python3
"""Independent checks on actual packet/target events and reconstructed received bytes."""
import csv,json,argparse,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('path',type=Path);p.add_argument('--scenario',default='same-source');a=p.parse_args();r=a.path
rows=lambda name:list(csv.DictReader((r/name).open()))
events=rows('events.csv');wire=rows('wire.csv');groups=rows('groups.csv');report=[]
for g in groups:
 gid=int(g['group']);src=int(g['source']);N=int(g['payload_bytes']);fanout=int(g['fanout']);assert fanout==2
 ev=[x for x in events if int(x['group'])==gid];submitted=[int(x['time_ps']) for x in ev if x['event']=='group_submit'];finished=[int(x['time_ps']) for x in ev if x['event']=='group_complete'];assert len(submitted)==len(finished)==1
 members=dict(tuple(map(int,x.split(':'))) for x in g['members'].split(';') if x);tasks=sorted(members.values());assert len(tasks)==fanout and set(tasks)=={int(x['task']) for x in ev if x['event']=='sender_complete'}
 hashes={}
 for task in tasks:
  te=[x for x in ev if int(x['task'])==task];completed=sorted((int(x['offset']),int(x['bytes']),int(x['time_ps'])) for x in te if x['event']=='target_complete');assert [x[0] for x in completed]==list(range(0,N,1024));assert all(x[1]==min(1024,N-x[0]) for x in completed)
  ready=[int(x['time_ps']) for x in te if x['event']=='receiver_ready'];done=[int(x['time_ps']) for x in te if x['event']=='sender_complete'];assert len(ready)==len(done)==1 and max(x[2] for x in completed)==ready[0]<=done[0]<=finished[0]
  b=(r/f'payload-{task}.bin').read_bytes();assert b==bytes((gid*73+i*131+(i>>8)*17)%251 for i in range(N));hashes[task]=hashlib.sha256(b).hexdigest()
  assert sum(x['event']=='feedback' for x in te)==len(completed)
 packets=[x for x in wire if int(x['group'])==gid and x['kind']=='envelope'];source=[x for x in packets if x['event']=='tx' and int(x['node'])==src];assert len(source)==(N+1023)//1024
 assert [int(x['sequence']) for x in source]==list(range(len(source)))
 assert all(int(x['bytes'])==32+137*fanout+min(1024,N-int(x['sequence'])*1024) for x in source)
 assert sum(int(x['bytes']) for x in source)==int(g['wire_bytes'])
 for seq in range(len(source)):
  packet=[x for x in packets if int(x['sequence'])==seq];assert len([x for x in packet if x['event']=='tx'])==1+fanout;assert len([x for x in packet if x['event']=='rx'])==1+fanout;assert {int(x['node']) for x in packet if x['event']=='rx'}=={5}|set(members)
 report.append(dict(group=gid,source=src,start_ps=submitted[0],complete_ps=finished[0],payload_sha256=hashes,source_payload_bytes=N,source_wire_bytes=int(g['wire_bytes'])))
# First two groups overlap in flight; distinct source paths can progress independently.
assert max(x['start_ps'] for x in report[:2])<min(x['complete_ps'] for x in report[:2])
if a.scenario=='same-source':
 seq=[int(x['group']) for x in wire if x['event']=='tx' and int(x['node'])==0 and x['kind']=='envelope']
 assert set(seq)=={1001,1002} and seq[:6]==[1001,1002]*3
 # Native RR grants include control feedback; data-only sequence need not alternate.
 grants=[int(x['group']) for x in events if x['event'] in ('data_grant','control_grant') and x['node']=='0'];assert grants[:6]==[1001,1002]*3
if a.scenario=='window':
 data1=[int(x['time_ps']) for x in events if x['event']=='data_grant' and x['group']=='1001'];data2=[int(x['time_ps']) for x in events if x['event']=='data_grant' and x['group']=='1002'];assert any(data1[0]<time<data1[-1] for time in data2)
if a.scenario=='dynamic':assert report[2]['start_ps']<min(x['complete_ps'] for x in report[:2])
if a.scenario=='different-source':assert {x['source'] for x in report}=={0,4}
for row in rows('ports.csv'):
 assert int(row['consumed'])>=0 and int(row['returned'])>=0
 initial=10 if a.scenario=='pressure' else 6553;assert initial-int(row['consumed'])+int(row['restored'])==int(row['free'])
 expected_tx=sum((int(x['bytes'])+159)//160 for x in wire if x['event']=='tx' and x['node']==row['node'] and x['port']==row['port'] and x['kind']!='credit');expected_rx=sum((int(x['bytes'])+159)//160 for x in wire if x['event']=='rx' and x['node']==row['node'] and x['port']==row['port'] and x['kind']!='credit');assert expected_tx==int(row['consumed']) and expected_rx==int(row['returned'])
out={'status':'PASS','groups':report,'checks':['actual_payload_sha256','per_task_exact_segment_coverage','target_before_sender','all_child_before_group','single_source_payload','paid_metadata','physical_branch_counts','overlap','native_port_conservation_assertions']}
(r/'independent-validation.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS concurrent independent validation')
