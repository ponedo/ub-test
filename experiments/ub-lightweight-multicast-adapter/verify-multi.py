#!/usr/bin/env python3
"""Independent CSV/received-byte verifier; no adapter code or success counters as oracle."""
import argparse,csv,json,hashlib
from pathlib import Path
if not __debug__:raise RuntimeError("Correctness checks require assertions enabled")
p=argparse.ArgumentParser();p.add_argument('case',type=Path);p.add_argument('--scenario',required=True);p.add_argument('--bytes',type=int,required=True);p.add_argument('--window',type=int,default=1000);a=p.parse_args()
def read(name):
 with (a.case/name).open() as f:return list(csv.DictReader(f))
events=read('events.csv');wire=read('wire.csv');ports=read('ports.csv');summary=json.loads((a.case/'summary.json').read_text())
expected={1001:[1,2] if a.scenario=='dynamic' else [1,2,3]}
if a.scenario=='dynamic':expected[1002]=[2,3]
def ev(name,task,rank=None):return [r for r in events if r['event']==name and int(r['task'])==task and (rank is None or int(r['rank'])==rank)]
hashes=[]
for task,members in expected.items():
 submit=ev('group_submit',task);end=ev('group_complete',task);assert len(submit)==len(end)==1
 last_sender=0
 for rank in members:
  ta=ev('target_complete',task,rank);assert sorted((int(r['offset']),int(r['bytes'])) for r in ta)==[(off,min(1024,a.bytes-off)) for off in range(0,a.bytes,1024)]
  chunks=ev('chunk_ready',task,rank)
  assert sorted((int(r['offset']),int(r['bytes'])) for r in chunks)==[(off,min(4096,a.bytes-off)) for off in range(0,a.bytes,4096)]
  for chunk in chunks:
   start=int(chunk['offset']);chunk_end=start+int(chunk['bytes']);assert int(chunk['time_ps'])==max(int(r['time_ps']) for r in ta if start<=int(r['offset'])<chunk_end)
  ready=ev('receiver_ready',task,rank);sender=ev('sender_complete',task,rank);feedback=ev('feedback_received',task,rank)
  assert len(ready)==len(sender)==1 and len(feedback)==len(ta)
  assert int(ready[0]['time_ps'])==max(int(r['time_ps']) for r in ta)
  assert int(sender[0]['time_ps'])>=int(ready[0]['time_ps'])
  assert int(sender[0]['time_ps'])>=max(int(r['time_ps']) for r in feedback)
  assert len({r['offset'] for r in feedback})==len(feedback)
  last_sender=max(last_sender,int(sender[0]['time_ps']))
  actual=(a.case/f'payload-{task}-{rank}.bin').read_bytes();want=bytes((task*73+i*131+(i>>8)*17)%251 for i in range(a.bytes));assert actual==want
  hashes.append({'task':task,'rank':rank,'bytes':len(actual),'sha256':hashlib.sha256(actual).hexdigest()})
 assert int(end[0]['time_ps'])==last_sender
 for rank in set(range(1,5))-set(members):assert not ev('target_complete',task,rank) and not (a.case/f'payload-{task}-{rank}.bin').exists()
 src=[r for r in wire if r['event']=='tx' and int(r['node'])==0 and r['packet_class']=='multicast_data' and int(r['task'])==task]
 assert len(src)==a.bytes//1024
 assert all(int(r['bytes'])==4+28+len(members)*137+1024 for r in src)
 for rank in members:
  branch=[r for r in wire if r['event']=='rx' and int(r['node'])==rank and r['packet_class']=='multicast_data' and int(r['task'])==task]
  assert len(branch)==len(src)
if a.scenario=='dynamic':assert int(ev('group_submit',1002)[0]['time_ps'])>=int(ev('group_complete',1001)[0]['time_ps'])
# Every physical link packet takes actual serialization + propagation, with FIFO wire order.
for rank in range(5):
 for sender,sp,receiver,rp in [(rank,0,5,rank),(5,rank,rank,0)]:
  tx=[r for r in wire if r['event']=='tx' and int(r['node'])==sender and int(r['port'])==sp]
  rx=[r for r in wire if r['event']=='rx' and int(r['node'])==receiver and int(r['port'])==rp]
  assert len(tx)==len(rx)
  for t,r in zip(tx,rx):
   assert all(t[k]==r[k] for k in ['bytes','packet_class','task','tp_opcode','ta_opcode'])
   assert int(r['time_ps'])-int(t['time_ps'])==int(t['bytes'])*80+20000
for row in ports:
 n,p=int(row['node']),int(row['port']);tx=[r for r in wire if r['event']=='tx' and int(r['node'])==n and int(r['port'])==p and r['packet_class']!='credit'];rx=[r for r in wire if r['event']=='rx' and int(r['node'])==n and int(r['port'])==p and r['packet_class']!='credit']
 assert int(row['consumed'])==sum((int(r['bytes'])+159)//160 for r in tx)
 assert int(row['returned'])==sum((int(r['bytes'])+159)//160 for r in rx)
assert summary['source_payload_bytes']==a.bytes*len(expected)
assert summary['branches']==sum(len(v)*a.bytes//1024 for v in expected.values())
win=read('windows.csv')
assert all(0<=int(r['tp_nxt'])-int(r['tp_una'])<=a.window for r in win)
assert all(0<=int(r['ta_nxt'])-int(r['ta_una'])<=512 for r in win)
assert all(int(r['tp_outstanding'])<=1000 for r in win)
if a.window==1:assert max(int(r['tp_nxt'])-int(r['tp_una']) for r in win)==1
final=[r for r in win if r['event']=='final_drain'];assert len(final)==3 and all(r['tp_nxt']==r['tp_una'] and r['ta_nxt']==r['ta_una'] and int(r['tp_outstanding'])==0 for r in final)
assert not any(r['event']=='fault_injected' for r in events)
result={'status':'PASS','checks':['actual_received_payload','per_target_TA_coverage','receiver_and_sender_causality','exact_member_set','source_single_payload','paid_envelope_bytes','native_feedback_count','link_serialization_and_propagation','credit_wire_accounting','group_completion'],'payloads':hashes}
(a.case/'independent-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('INDEPENDENT MULTI PASS')
