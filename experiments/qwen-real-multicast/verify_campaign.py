#!/usr/bin/env python3
"""Final independent aggregate consistency, group readiness, and credit checks."""
import argparse,csv,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();ledger=json.loads((a.private/'run-ledger.json').read_text());expected={(l,s) for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming','multicast']};assert len(ledger)==12 and {(r['layer'],r['strategy']) for r in ledger}==expected
checks=[]
def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
for l in [0,37,52]:
 cases=[r for r in ledger if r['layer']==l];assert all(r['status']=='PASS' for r in cases)
 assert len({r['routing_sha256'] for r in cases})==1 and len({r['mapping_sha256'] for r in cases})==1
 balanced=[r for r in cases if r['strategy']!='no-balancing'];assert len({r['plan_semantic_sha256'] for r in balanced})==1 and len({r['assignments_sha256'] for r in balanced})==1
 assert len({r['summary']['combine_fnv1a64'] for r in cases})==1
 for r in cases:
  case=a.private/f'L{l}'/r['strategy'];d=case/'prepared'/('multicast-run' if r['strategy']=='multicast' else 'run');s=json.loads((d/'online-summary.json').read_text());assert s==r['summary'];assert s['completed_tokens']==2048 and s['assignments']==16384 and s['sender_completions']==s['remote_WQEs'] and s['target_segments']==s['TA_count'];assert r['validation']['status']=='PASS'
  for stage in ['preparation','preflight','simulator','postflight']:assert r[stage+'_host']['status']=='PASS' and r[stage+'_host']['guard'] is None
  pc=rows(d/'packet-counts.csv');assert sum(int(x['wire_bytes']) for x in pc)==sum(s['byte_tx_per_node']);assert sum(int(x['packets']) for x in pc)==sum(s['packet_tx_per_node'])
  for q in rows(d/'queue-stats.csv'):assert int(q['peak_egress_bytes'])<=524288
  assert s['timeline']['dispatch_gate']==max(s['timeline']['reroute_end'],s['timeline']['weights_end'])
  checks.append(dict(layer=l,strategy=r['strategy'],status='PASS',token_assignment_conservation=True,online_validation=True,independent_postflight=True,measured_packet_totals_reconcile=True,queue_bound=True,receiver_gate=True))
 mc=a.private/f'L{l}'/'multicast/prepared/multicast-run';c=json.loads((mc/'config.json').read_text());members=rows(mc/'multicast-groups.csv');stats=rows(mc/'multicast-stats.csv');mapping={(g['group'],m['task']):m for g in c['multicast_groups'] for m in g['members']};assert len(members)==len(mapping)
 seen=set();times={}
 for m in members:
  key=int(m['group']),int(m['task']);assert key not in seen and key in mapping;seen.add(key);e=mapping[key];assert int(m['target'])==e['target'] and int(m['physical'])==e['physical'] and int(m['bytes'])==18874368
  ready,done,groupdone=map(int,[m['receiver_ready_ps'],m['sender_complete_ps'],m['group_complete_ps']]);assert 0<ready<=done<=groupdone;times.setdefault(key[0],[]).append((done,groupdone,ready))
 for group,ts in times.items():assert len({t[1] for t in ts})==1 and max(t[0] for t in ts)==ts[0][1]
 s=json.loads((mc/'online-summary.json').read_text());assert max(t[2] for ts in times.values() for t in ts)==s['timeline']['weights_end']
 ports={(int(x['node']),int(x['port'])):x for x in rows(mc/'multicast-ports.csv')};assert len(ports)==128
 for (node,port),x in ports.items():
  peer=ports[(port,0) if node==64 else (64,node)];cons,rest,free=map(int,[x['consumed_cells'],x['restored_cells'],x['free_cells']]);assert 6553-cons+rest==free;assert cons==int(peer['returned_cells'])==rest+int(peer['pending_cells'])
 assert len(stats)==len(c['multicast_groups']) and sum(int(x['payload_bytes']) for x in stats)==len(stats)*18874368
 checks.append(dict(layer=l,strategy='multicast-independent',status='PASS',children=len(members),groups=len(stats),unique_child_identity=True,all_targets_before_native_sender_complete=True,group_complete_exact_child_max=True,weight_gate_exact_receiver_max=True,cross_link_credit_conservation=True))
a.out.write_text(json.dumps(dict(status='PASS',cases=checks,scope='aggregate and per-child checks supplement accepted online per-TA/payload verification; no validation disabled'),indent=2)+'\n');print('12-case final verification PASS')
