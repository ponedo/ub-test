#!/usr/bin/env python3
"""Check actual physical paths, native identities, payload and completion evidence."""
import csv,json,argparse
from pathlib import Path
if not __debug__:raise RuntimeError('Assertions must remain enabled')
def rows(p):return list(csv.DictReader(p.open()))
def verify(root,case):
 p=rows(root/'packets.csv');ev=rows(root/'events.csv');w=rows(root/'windows.csv')
 def match(event,**kw):return [x for x in p if x['event']==event and all(x[k]==str(v) for k,v in kw.items())]
 def events(name,rank=None):return [x for x in ev if x['event']==name and (rank is None or x['rank']==str(rank))]
 first=match('first_native');assert len(first)==36
 assert len(match('tx',node=0,envelope=1))==12
 original={(x['src_tpn'],x['dst_tpn'],x['psn']):x for x in first};assert len(original)==36
 assert set(original)=={(str(100+r),str(200+r),str(psn)) for r in [1,2,3] for psn in range(12)}
 retries=match('native_retry')
 drops=match('drop');duplicates=match('duplicate')
 if case=='duplicate':assert not drops
 else:assert not duplicates
 for x in drops+duplicates:
  assert x['psn']=='11' and x['envelope']=='0'
  if case in ['ack-once','response-once']:
   assert (x['node'],x['src_tpn'],x['dst_tpn'])==('0','201','101')
   assert (x['tp_opcode'],x['ta_opcode'])==(('2','999') if case=='ack-once' else ('1','17'))
  else:
   assert (x['node'],x['src_tpn'],x['dst_tpn'],x['tp_opcode'],x['ta_opcode'])==('1','101','201','1','3')
 def same_identity(a,b):
  for k in ['src_tpn','dst_tpn','psn','ssn','tp_opcode','ta_opcode','task','payload_bytes','payload_hash']:assert a[k]==b[k],k
 for index,r in enumerate(retries):
  assert r['dst_tpn']=='201' and r['envelope']=='0'
  old=original[(r['src_tpn'],r['dst_tpn'],r['psn'])]
  for key in ['psn','ssn','tp_opcode','ta_opcode','task','payload_bytes','payload_hash']:assert r[key]==old[key],key
  path=[('egress_enqueue',0,0),('tx',0,0),('rx',5,0),('egress_enqueue',5,1),('tx',5,1),('rx',1,0)]
  last=-1
  for event,node,port in path:
   hit=[x for x in match(event,uid=r['uid'],node=node,port=port,src_tpn=r['src_tpn'],dst_tpn=r['dst_tpn'],psn=r['psn']) if int(x['time_ps'])>=int(r['time_ps']) and (index+1==len(retries) or int(x['time_ps'])<int(retries[index+1]['time_ps']))];assert len(hit)==1,(r,path,event,hit)
   same_identity(hit[0],r);assert int(hit[0]['time_ps'])>=last;last=int(hit[0]['time_ps'])
 # No extra physical request data to C/D; coalesced initial packets are only decoded downstream.
 for rank in [2,3]:
  writes=[x for x in match('rx',node=rank) if x['src_tpn']==str(100+rank) and x['payload_bytes']=='1024']
  assert len(writes)==12 and {int(x['psn']) for x in writes}==set(range(12))
  assert len(events('sender_complete',rank))==1 and len(events('receiver_ready',rank))==1
 incomplete=case in ['persistent-bounded','persistent-exhaust','retrans-disabled']
 assert len(events('group_complete'))==(0 if incomplete else 1)
 for rank in [1,2,3]:
  target=events('target_complete',rank);expected=11 if incomplete and rank==1 else 12
  assert len(target)==expected and len({x['offset'] for x in target})==expected
  assert len(events('sender_complete',rank))==(0 if incomplete and rank==1 else 1)
 # Native WRITE success requires every TA response to have been delivered to A,
 # not merely physically received and then deliberately discarded.
 def delivery_key(x):return tuple(x[k] for k in ['time_ps','node','uid','src_tpn','dst_tpn','psn','tp_opcode','ta_opcode'])
 suppressed={delivery_key(x) for x in drops}
 for rank in [1,2,3]:
  complete=events('sender_complete',rank)
  if complete:
   delivered=[x for x in match('tp_boundary',node=0,src_tpn=200+rank,dst_tpn=100+rank,ta_opcode=17) if delivery_key(x) not in suppressed and int(x['time_ps'])<=int(complete[0]['time_ps'])]
   assert {int(x['ssn']) for x in delivered}==set(range(12)),('WQE before all real TA responses',rank)
 if not incomplete:
  group=int(events('group_complete')[0]['time_ps'])
  for rank in [1,2,3]:assert group>=int(events('sender_complete',rank)[0]['time_ps'])>=int(events('receiver_ready',rank)[0]['time_ps'])
 if case=='normal':assert not retries and not match('drop') and not match('duplicate')
 if case=='data-once':
  assert len(match('drop'))==1 and len(retries)==1 and retries[0]['psn']=='11'
  assert int(events('sender_complete',1)[0]['time_ps'])>max(int(events('sender_complete',r)[0]['time_ps']) for r in [2,3])
 if case=='duplicate':assert len(match('duplicate'))==1 and not retries
 if case=='response-once':
  assert len(match('drop'))==1 and not retries
  # Reverse-direction response replay has its own original native TP. Match actual UID path.
  b=[x for x in match('tx',node=1,src_tpn=201,psn=11) if x['payload_bytes']=='0' and x['ta_opcode']!='999']
  assert len(b)==2 and all(x['ssn']==b[0]['ssn'] for x in b)
  replay=b[1];last=-1
  enqueued=match('egress_enqueue',node=1,src_tpn=201,psn=11,ta_opcode=17)
  assert len(enqueued)==2
  start=int(enqueued[1]['time_ps'])
  for event,node,port in [('egress_enqueue',1,0),('tx',1,0),('rx',5,1),('egress_enqueue',5,0),('tx',5,0),('rx',0,0)]:
   hit=[x for x in match(event,uid=replay['uid'],node=node,port=port,src_tpn=replay['src_tpn'],dst_tpn=replay['dst_tpn'],psn=replay['psn']) if int(x['time_ps'])>=start];assert len(hit)==1
   same_identity(hit[0],replay);assert int(hit[0]['time_ps'])>=last;last=int(hit[0]['time_ps'])
 if case=='ack-once':assert len(match('drop'))==1
 if case=='retrans-disabled':assert len(match('drop'))==1 and not retries
 if case.startswith('persistent'):assert len(match('drop'))>=2 and len(retries)>=1 and not events('receiver_ready',1)
 if case=='persistent-exhaust':
  host=root.parent/(root.name+'-host');resource=json.loads((host/'resource.json').read_text())
  assert resource['returncode']==-6 and not resource['guard'] and resource['status']=='FAIL'
  assert 'Avaliable retransmission attempts exhausted' in (host/'console.txt').read_text()
 if case!='persistent-exhaust':
  s=json.loads((root/'summary.json').read_text());assert s['status']==('BOUNDED_INCOMPLETE' if incomplete else 'PASS')
  for rank in [1,2,3]:
   data=(root/f'payload-1001-{rank}.bin').read_bytes();exp=bytes((1001*73+i*131+(i>>8)*17)%251 for i in range(12288))
   assert data==exp if not incomplete or rank!=1 else data[:11264]==exp[:11264]
  ports=rows(root/'ports.csv')
  assert len(ports)==10 and {(int(x['node']),int(x['port'])) for x in ports}=={(n,0) for n in range(5)}|{(5,p) for p in range(5)}
  for r in ports:
   n,port=int(r['node']),int(r['port']);peer=(5,n) if n!=5 else (port,0)
   other=next(x for x in ports if (int(x['node']),int(x['port']))==peer)
   assert int(r['consumed'])==int(other['returned'])==int(r['restored'])+int(other['pending'])
  for rank in [1,2,3]:
   end=next(x for x in reversed(w) if x['rank']==str(rank) and x['event']=='final_state')
   if incomplete and rank==1:
    assert int(end['tp_outstanding'])==1 and end['tp_una']=='11' and end['tp_nxt']=='12'
    assert int(end['request_descriptors'])==(0 if case=='retrans-disabled' else 1)
    assert int(end['request_timer'])==(0 if case=='retrans-disabled' else 1)
    assert int(end['response_descriptors'])==int(end['response_timer'])==0
   else:
    assert end['tp_una']==end['tp_nxt'] and end['ta_una']==end['ta_nxt']
    for k in ['tp_outstanding','request_descriptors','request_timer','response_descriptors','response_timer','pending_selective']:assert int(end[k])==0,(rank,k,end)
 return dict(case=case,status='VERIFIED',request_retries=len(retries),drops=len(match('drop')),duplicates=len(match('duplicate')),group_completions=len(events('group_complete')),packets=len(p),events=len(ev))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('root',type=Path);a.add_argument('case');x=a.parse_args();print(json.dumps(verify(x.root,x.case),indent=2))
