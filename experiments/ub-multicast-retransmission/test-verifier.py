#!/usr/bin/env python3
"""Mutation-test the evidence gate using actual completed single-loss evidence."""
import csv,json,sys,tempfile,shutil
from pathlib import Path
from verify import verify
if not __debug__:raise RuntimeError('Assertions must remain enabled')
source=Path(sys.argv[1]);assert verify(source,'data-once')['status']=='VERIFIED'
def mutate(root,file,fn):
 p=root/file
 with p.open() as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
 fn(rows)
 with p.open('w') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def remove(rows,pred):rows[:]=[r for r in rows if not pred(r)]
def edit(rows,pred,key,value):next(r for r in rows if pred(r))[key]=value
tests=[
 ('packets.csv',lambda r:remove(r,lambda x:x['event']=='tx' and x['node']=='0' and x['envelope']=='0' and x['payload_bytes']=='1024')),
 ('packets.csv',lambda r:edit(r,lambda x:x['event']=='native_retry','payload_hash','0')),
 ('packets.csv',lambda r:remove(r,lambda x:x['event']=='drop')),
 ('packets.csv',lambda r:edit(r,lambda x:x['event']=='drop','tp_opcode','2')),
 ('packets.csv',lambda r:edit(r,lambda x:x['event']=='native_retry','ssn','999')),
 ('packets.csv',lambda r:edit(r,lambda x:x['event']=='tx' and x['node']=='0' and x['payload_bytes']=='1024','payload_hash','0')),
 ('ports.csv',lambda r:r.clear()),
 ('packets.csv',lambda r:r.append(next(x.copy() for x in r if x['event']=='rx' and x['node']=='2' and x['payload_bytes']=='1024'))),
 ('events.csv',lambda r:r.append(next(x.copy() for x in r if x['event']=='group_complete'))),
 ('events.csv',lambda r:edit(r,lambda x:x['event']=='group_complete','time_ps','0')),
 ('events.csv',lambda r:remove(r,lambda x:x['event']=='target_complete' and x['rank']=='1')),
 ('ports.csv',lambda r:edit(r,lambda x:x['node']=='0','consumed','0')),
 ('windows.csv',lambda r:edit(r,lambda x:x['event']=='final_state' and x['rank']=='1','request_descriptors','1')),
]
for file,fn in tests:
 with tempfile.TemporaryDirectory(prefix='retx-gate-') as td:
  root=Path(td)/'case';shutil.copytree(source,root);mutate(root,file,fn)
  try:verify(root,'data-once')
  except (AssertionError,StopIteration):pass
  else:raise RuntimeError('invalid evidence accepted: '+file)
with tempfile.TemporaryDirectory(prefix='retx-payload-') as td:
 root=Path(td)/'case';shutil.copytree(source,root);p=root/'payload-1001-1.bin';b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b)
 try:verify(root,'data-once')
 except AssertionError:pass
 else:raise RuntimeError('wrong payload accepted')
try:verify(source,'ack-once')
except AssertionError:pass
else:raise RuntimeError('data loss accepted as ACK loss')
print(json.dumps(dict(valid=1,rejected=len(tests)+2,status='PASS')))
