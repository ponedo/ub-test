#!/usr/bin/env python3
"""Independent aggregate, physical-byte, lifecycle and readiness checks."""
import argparse,csv,json
from pathlib import Path
if not __debug__:raise RuntimeError('Assertions must remain enabled')
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--fault',choices=['data-once','ack-once']);p.add_argument('--grant',action='store_true');a=p.parse_args();r=a.root
read=lambda f:list(csv.DictReader((r/f).open()))
c=json.loads((r/'config.json').read_text());s=json.loads((r/'online-summary.json').read_text());v=json.loads((r/'validation.json').read_text());assert v['status']=='PASS'
n=c['planner_input']['npus'];replicas=[x for x in json.loads((r/'plan.json').read_text())['physical'] if x['kind']=='replica']
assert s['sender_completions']==s['remote_WQEs'] and s['completed_tokens']==len(c['planner_input']['mapping'])
keys={(x['source'],x['target']) for x in c['transfers'] if x['source']!=x['target']};assert s['jettys']==len(keys),'pair Jetty reuse'
ready=read('replica-ready.csv');assert len(ready)==len(replicas)
assert {int(x['physical']) for x in ready}=={x['id'] for x in replicas}
t=s['timeline'];assert t['dispatch_gate']==max(t['reroute_end'],t['weights_end'])
assert max([int(x['ready_ps']) for x in ready]+[t['planning_end']])==t['weights_end']
resources=read('network-resources.csv');assert len(resources)==2*n and {(int(x['node']),int(x['port'])) for x in resources}=={(i,0) for i in range(n)}|{(n,i) for i in range(n)}
for x in resources:
 node,port=int(x['node']),int(x['port']);peer=(n,node) if node!=n else (port,0);y=next(q for q in resources if (int(q['node']),int(q['port']))==peer)
 assert int(x['consumed'])==int(y['returned'])==int(x['restored'])+int(y['pending'])
 assert int(x['peak_ingress_bytes'])<=1048576 and int(x['peak_egress_bytes'])<=524288
states=read('pair-state.csv');expected=keys|{(b,a) for a,b in keys};assert len(states)==len(expected) and {(int(x['source']),int(x['target'])) for x in states}==expected
for x in states:
 assert x['send_una']==x['send_nxt'];assert all(int(x[k])==0 for k in ['unacked','descriptors','timer','active_wqes']);assert x['ta_una']==x['ta_nxt']
packets=read('packet-counts.csv');sumbytes=sum(int(x['wire_bytes']) for x in packets);assert sumbytes==sum(s['byte_tx_per_node'])
if c['weight_strategy']=='multicast-v2':
 life=json.loads((r/'multicast-lifecycle.json').read_text());assert life['status']=='PASS' and life['pending_associations']==0 and life['pair_jetties']==len(keys)
 assert life['invalidated_grants']==int(a.grant)
 groups=read('multicast-groups.csv');stats=read('multicast-stats.csv');want=c['multicast_groups'];assert len(stats)==len(want) and len(groups)==len(replicas)
 reservations=[]
 envelopes=branches=sourcepayload=sourcewire=0
 for x,g in zip(stats,want):
  fan=len(g['members']);w=c['runtime']['weight_bytes'];seg=c['runtime']['segment_bytes'];count=(w+seg-1)//seg
  assert int(x['group'])==g['group'] and int(x['fanout'])==fan
  assert int(x['envelopes'])==(count if fan>1 else 0) and int(x['native_singleton_packets'])==(count if fan==1 else 0)
  overhead=78 if fan==1 else 24+76*fan
  assert int(x['payload_bytes'])==w and int(x['header_bytes'])==overhead*count and int(x['wire_bytes'])==w+overhead*count
  assert int(x['association_peak'])<=int(x['association_limit']) and int(x['association_restored'])==(fan*count if fan>1 else 0)
  children=[q for q in groups if int(q['group'])==g['group']];assert len(children)==fan
  admission,release=int(x['admitted_ps']),int(x['first_send_done_ps']);assert admission<=release<=min(int(q['receiver_ready_ps']) for q in children)
  edges={tuple(sorted((g['source'],m['target']))) for m in g['members']};reservations.append((admission,release,edges))
  done=max(int(q['sender_complete_ps']) for q in children);assert all(int(q['group_complete_ps'])==done and int(q['receiver_ready_ps'])<=int(q['sender_complete_ps']) for q in children)
  envelopes+=count if fan>1 else 0;branches+=fan*count if fan>1 else 0;sourcepayload+=w;sourcewire+=w+overhead*count
 for i,(start,end,edges) in enumerate(reservations):
  for otherstart,otherend,otheredges in reservations[i+1:]:
   assert not edges&otheredges or max(start,otherstart)>=min(end,otherend),'shared-pair first-send overlap'
 assert life['envelopes']==envelopes and life['branches']==branches
 physicalenv=sum(int(x['packets']) for x in packets if x['kind']=='multicast_v2');assert physicalenv==envelopes
 assert not any(x['kind']=='multicast_v2' and int(x['node'])==n for x in packets),'switch must reconstruct native WRITE'
 measuredsource=sum(int(x['wire_bytes']) for x in packets if int(x['node'])<n and x['kind'] in ['multicast_v2','weight_write'])
 down=sum(int(x['wire_bytes']) for x in packets if int(x['node'])==n and x['kind']=='weight_write')
 expecteddown=len(replicas)*(c['runtime']['weight_bytes']+78*((c['runtime']['weight_bytes']+c['runtime']['segment_bytes']-1)//c['runtime']['segment_bytes']))
 if not a.fault:assert measuredsource==sourcewire and down==expecteddown and life['native_retry_packets']==0 and life['injected_losses']==0
 else:
  assert life['injected_losses']==1
  if a.fault=='data-once':assert life['native_retry_packets']==1
  wire=read('weight-packets.csv');retry=[x for x in wire if x['kind']=='native_retry'];drops=[x for x in wire if x['kind']=='drop'];assert len(drops)==1 and len(retry)==life['native_retry_packets']
  for x in retry:
   if a.fault=='data-once':assert all(x[k]==drops[0][k] for k in ['task','src_tpn','dst_tpn','psn','ssn','payload_bytes'])
   first=[y for y in wire if y['kind']=='first_native' and all(x[k]==y[k] for k in ['task','src_tpn','dst_tpn','psn','ssn','payload_bytes'])];assert len(first)==1
   hop=[y for y in wire if y['kind']=='native' and all(x[k]==y[k] for k in ['task','src_tpn','dst_tpn','psn','ssn','payload_bytes']) and int(y['time_ps'])>=int(x['time_ps'])]
   assert any(int(y['node'])==int(x['node']) for y in hop) and any(int(y['node'])==n for y in hop),'retry physical source and switch transmission'
print(json.dumps(dict(status='PASS',pair_jetties=len(keys),targets=len(replicas),completed_tokens=s['completed_tokens'],all_network_wire_bytes=sumbytes)))
