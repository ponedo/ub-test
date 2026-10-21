#!/usr/bin/env python3
"""Read-only bounded return-path supplement. No imports from mutable runtime."""
import argparse,csv,json,hashlib
from pathlib import Path

def read(p):
 with p.open(newline='') as f:return [{k:int(v) if v and v.lstrip('-').isdigit() else v for k,v in r.items()} for r in csv.DictReader(f)]
def dump(p,rs):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rs for k in r)) or ['no_selected_observations']);w.writeheader();w.writerows(rs)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(case, selected_limit=8):
 summary=json.loads((case/'online-summary.json').read_text());status=json.loads((case/'diagnostic-status.json').read_text())
 assert not status['incomplete'] and status['enabled']
 for k in ['queue_unmatched','queue_order_errors','queue_depth_errors','queue_observations_open','grant_outcomes_unmatched','grant_start_overwrites','grant_starts_open']:assert status[k]==0
 for name in ['validation.json','compute-validation.json']:assert json.loads((case/name).read_text())['status']=='PASS'
 begin,end=summary['event_spans']['weights_start'][0],summary['timeline']['weights_end']
 co=read(case/'diagnostic-weight-phase-cohorts.csv');allco=read(case/'diagnostic-native-aggregates.csv')
 def metric(metric,node,port,cl):return next((r for r in co if (r['metric'],r['node'],r['port'],r['class'])==(metric,node,port,cl)),dict(count=0,sum=0,max=0))
 partitions={r['port']:r for r in read(case/'diagnostic-port-partition.csv') if r['node']==64}
 partition=partitions[3]
 assert sum(partition[k] for k in ['tx_busy_union_ps','allocator_pending_excluding_tx_ps','uncovered_idle_ps'])==partition['total_ps']==end-begin
 q=metric(0,64,3,1);tx=metric(5,64,3,1);rx=metric(6,3,0,1)
 aggregate=dict(phase_start_ps=begin,phase_end_ps=end,weight_phase_ps=end-begin,
  return_ack_response_tx_packets=tx['count'],source_ack_response_rx_packets=rx['count'],
  tx_minus_received_at_phase_end_packets=tx['count']-rx['count'],
  return_ack_response_voq_count=q['count'],return_ack_response_voq_sum_ps=q['sum'],
  return_ack_response_voq_mean_ps=q['sum']/q['count'] if q['count'] else None,
  return_ack_response_voq_max_ps=q['max'],
  return_tx_busy_ps=partition['tx_busy_union_ps'],return_allocator_excluding_tx_ps=partition['allocator_pending_excluding_tx_ps'],
  return_uncovered_idle_ps=partition['uncovered_idle_ps'],
  return_tx_or_allocation_fraction=1-partition['uncovered_idle_ps']/partition['total_ps'],
  allocation_starts=metric(2,64,3,2)['count'],allocation_requested_service_ps=metric(2,64,3,2)['sum'],
  allocation_successful_callbacks=sum(metric(10,64,3,c)['count'] for c in [0,1,2]),
  allocation_no_ingress_callbacks=metric(9,64,3,2)['count'],allocation_rejected_callbacks=metric(8,64,3,2)['count'],
  source_weight_tx_packets=metric(5,3,0,0)['count'],source_ack_response_tx_packets=metric(5,3,0,1)['count'],
  semantics='Exact phase partition; native cohort counts are full start/end-event cohorts. VOQ sums overlap, not causal wall time.')
 selected=[r for r in co if r['node']==64 and r['port']==3]
 selectedall=[r for r in allco if r['node']==64 and r['port']==3]
 for r in selectedall:r['cohort']='whole_run'
 packets=read(case/'packet-counts.csv');selectedpackets=[r for r in packets if (r['node'],r['port']) in [(64,3),(3,0)]]
 ts=read(case/'transfers.csv')
 def ta(direction,weight):
  chosen=[r for r in ts if (r['stage']==2)==weight and r['source']!=r['target'] and r['source' if direction=='out' else 'target']==3]
  return sum((r['bytes']+1023)//1024 for r in chosen)
 tokenout,tokenin,weightout,weightin=ta('out',False),ta('in',False),ta('out',True),ta('in',True)
 pc={(r['node'],r['port'],r['kind']):r['packets'] for r in packets}
 # Native opcode-split whole-run physical TX counts, not broad class1 inference.
 derived=dict(outgoing_token_tas=tokenout,incoming_token_tas=tokenin,outgoing_weight_tas=weightout,incoming_weight_tas=weightin,
  whole_return_transport_ack=pc.get((64,3,'transport_ack'),0),whole_return_transaction_response=pc.get((64,3,'transaction_response'),0),
  weight_return_transport_ack_after_subtracting_token_ack=pc.get((64,3,'transport_ack'),0)-tokenout-tokenin,
  weight_return_taack_after_subtracting_token_response=pc.get((64,3,'transaction_response'),0)-tokenout,
  assumptions='No loss/retransmission; 1024B one-packet TA; WRITE→one TAACK; every received request/response gets transport ACK; source3 has no incoming weight WRITE. This is whole lifecycle, not weight-phase count.')
 assert weightin==0
 assert derived['weight_return_transport_ack_after_subtracting_token_ack']==weightout
 assert derived['weight_return_taack_after_subtracting_token_response']==weightout
 tail=read(case/'diagnostic-weight-tail.csv')
 # Match local wire occurrence by source receipt, preceding exact return-port TX,
 # same task and UID, plus observed propagation+serialization. Never UID alone.
 selected_entries=[(i,r) for i,r in enumerate(tail) if r['node']==3 and r['kind'] in [15,17] and r['tp'] in [198,206,245,252]][-selected_limit:]
 events=[];summary_events=[]
 for i,r in selected_entries:
  found=[(j,x) for j,x in enumerate(tail[:i]) if x['node']==64 and x['port']==3 and x['kind']==9 and x['uid']==r['uid'] and x['task']==r['task']]
  if not found:continue
  j,txevent=found[-1]
  receive=[(k,x) for k,x in enumerate(tail[j+1:i],j+1) if x['node']==3 and x['kind']==10 and x['uid']==r['uid'] and x['task']==r['task'] and x['time_ps']==r['time_ps']]
  if not receive:continue
  k,rxevent=receive[-1]
  assert r['time_ps']-txevent['time_ps']==txevent['aux0']+20000
  kind='transport_ack' if r['kind']==15 else 'TAACK_response_in_source3_weight_only_pair'
  summary_events.append(dict(kind=kind,task=r['task'],tp=r['tp'],uid=r['uid'],switch3_tx_ps=txevent['time_ps'],source3_receive_ps=rxevent['time_ps'],source_handler_ps=r['time_ps'],serialization_ps=txevent['aux0'],propagation_ps=20000))
  for n,event in [(j,txevent),(k,rxevent),(i,r)]:events.append(dict(ring_index=n,feedback_kind=kind,**event))
 last={}
 for i,r in enumerate(tail):
  if r['node']==3 and r['kind'] in [16,18] and r['tp'] in [198,206,245,252]:last[(r['tp'],r['kind'])]=(i,r)
 frontiers=[dict(tp=tp,kind='request_TPACK_sender_una' if kind==16 else 'reverse_TAACK_receive_nxt',time_ps=r['time_ps'],frontier=r['aux1'] if kind==16 else r['aux2'],ring_index=i) for (tp,kind),(i,r) in sorted(last.items())]
 critical=[dict(source=r['source'],target=r['target'],task=r['task']) for r in read(case/'diagnostic-transfers.csv') if r['receiver_ready_ps']==end]
 aggregate['source3_is_terminal']=any(r['source']==3 for r in critical)
 aggregate['coverage']='Fixed original source3 return path, not automatically the new terminal path; source3 class split can be reconstructed only under documented transfer/ACK invariants.'
 selected_ports=[]
 for port in sorted({3,36,50}|{r['source'] for r in critical}):
  part=partitions[port];q=metric(0,64,port,1)
  assert sum(part[k] for k in ['tx_busy_union_ps','allocator_pending_excluding_tx_ps','uncovered_idle_ps'])==part['total_ps']==end-begin
  selected_ports.append(dict(node=64,port=port,selection='fixed source control; actual terminal source' if port in {r['source'] for r in critical} and port in {3,36,50} else 'actual terminal source' if port in {r['source'] for r in critical} else 'fixed source control',
   source_is_terminal=any(r['source']==port for r in critical),weight_phase_ps=end-begin,
   tx_busy_ps=part['tx_busy_union_ps'],allocator_excluding_tx_ps=part['allocator_pending_excluding_tx_ps'],uncovered_idle_ps=part['uncovered_idle_ps'],
   tx_or_allocation_fraction=1-part['uncovered_idle_ps']/part['total_ps'],
   return_ack_response_tx_packets=metric(5,64,port,1)['count'],return_ack_response_voq_count=q['count'],
   return_ack_response_voq_mean_ps=q['sum']/q['count'] if q['count'] else None,return_ack_response_voq_max_ps=q['max'],
   scope='Selected fixed controls and true-terminal source return ports only; class1 includes native TPACK and weight TAACK, not their opcode split.'))
 capacity=[]
 for tp,target in [(198,5),(206,13),(245,52),(252,59)]:
  obs=[r for r in tail if r['node']==3 and r['tp']==tp and r['kind']==22]
  if not obs:continue
  reserved=[r['aux3']-r['aux2'] for r in obs];assert min(reserved)>=0 and max(reserved)<=1000
  empty=[r for r in obs if r['aux0']==1]
  capacity.append(dict(source=3,target=target,tp=tp,tail_first_ps=tail[0]['time_ps'],tail_last_ps=tail[-1]['time_ps'],
   retained_tail_empty_query_count=len(obs),retained_tail_empty_true_count=len(empty),
   min_reserved_unacknowledged_psn_slots=min(reserved),max_reserved_unacknowledged_psn_slots=max(reserved),
   queries_reserved_slots_at_1000=sum(x==1000 for x in reserved),empty_true_and_reserved_slots_at_1000=sum(r['aux3']-r['aux2']==1000 for r in empty),
   max_sent_unacknowledged_psn_slots=max(r['aux1']-r['aux2'] for r in obs),
   last_query_ps=obs[-1]['time_ps'],last_snd_nxt=obs[-1]['aux1'],last_snd_una=obs[-1]['aux2'],last_reserved_psn_count=obs[-1]['aux3'],
   scope='Retained weight-tail queries only, not full-run counts. cnt-UNA is reserved unacknowledged PSN slots; under audited one-packet/no-cancellation request path it lower-bounds retained segments. At1000 it proves capacity state, not gate evaluation, blocked duration or plateau causation.'))
 latest_start=max(x['start_ps'] for x in summary['compute_intervals']);latest_end=max(x['end_ps'] for x in summary['compute_intervals']);layer_end=summary['timeline']['layer_end']
 landmarks=dict(weights_end_ps=end,latest_node_batch_start_ps=latest_start,latest_node_batch_end_ps=latest_end,layer_end_ps=layer_end,
  preweight_ps=begin-summary['timeline']['layer_start'],weight_ps=end-begin,postweight_ps=layer_end-end,
  weight_end_to_latest_node_batch_start_ps=latest_start-end,latest_node_batch_start_to_latest_node_batch_end_ps=latest_end-latest_start,latest_node_batch_end_to_layer_end_ps=layer_end-latest_end,
  dispatch_envelope_ps=summary['stage_intervals'][0][1]-summary['stage_intervals'][0][0],combine_envelope_ps=summary['stage_intervals'][1][1]-summary['stage_intervals'][1][0],
  latest_node_batch_start_nodes=';'.join(str(x['node']) for x in summary['compute_intervals'] if x['start_ps']==latest_start),latest_node_batch_end_nodes=';'.join(str(x['node']) for x in summary['compute_intervals'] if x['end_ps']==latest_end),
  whole_lifecycle_weight_return_frames=2*weightout,weight_return_frames_not_transmitted_at_weightready=2*weightout-tx['count'],weight_return_frames_not_received_at_weightready=2*weightout-rx['count'],
  scope='Node compute batches use one compute_start before serial expert scheduling and compute_end after all assigned experts (layer.cc:399-405); these are not latest individual expert starts. Disjoint event cuts are arithmetic wall-time partitions, not additive overlapping stage latencies or isolated mediators. Remaining feedback counts use audited source3 whole-lifecycle one-request-TPACK/one-TAACK accounting.')
 assert landmarks['postweight_ps']==sum(landmarks[k] for k in ['weight_end_to_latest_node_batch_start_ps','latest_node_batch_start_to_latest_node_batch_end_ps','latest_node_batch_end_to_layer_end_ps'])
 return aggregate,derived,selected+selectedall,selectedpackets,summary_events,events,frontiers,critical,selected_ports,capacity,landmarks

def main():
 ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--formal',action='store_true');a=ap.parse_args()
 assert not a.out.exists();a.out.mkdir(parents=True)
 if a.formal:
  ledger=json.loads((a.root/'ledger.json').read_text());assert ledger['status']=='PASS'
  ids=[r['case_id'] for r in ledger['runs']];assert len(ids)==6
 else:ids=['chunk-streaming','multicast-v2']
 results={};collected={k:[] for k in ['port3-summary','weight-feedback-counts','port3-cohorts','physical-packet-kinds','selected-feedback-paths','selected-feedback-events','weight-end-frontiers','terminal-coverage','selected-return-ports','tp-empty-capacity-observations','postweight-landmarks']}
 for ident in ids:
  case=a.root/ident
  assert json.loads((case/'run-result.json').read_text())['status']=='PASS'
  limit=8 if ident in ['multicast-v2','baseline-512-multicast-v2'] else 2
  values=collect(case,limit);results[ident]=dict(zip(collected,values))
  for name,value in zip(collected,values):
   values_list=[value] if isinstance(value,dict) else value
   collected[name].extend(dict(case_id=ident,**r) for r in values_list)
 for name,rs in collected.items():dump(a.out/(name+'.csv'),rs)
 inputs={ident:{name:sha(a.root/ident/name) for name in ['online-summary.json','diagnostic-status.json','diagnostic-weight-phase-cohorts.csv','diagnostic-native-aggregates.csv','diagnostic-port-partition.csv','packet-counts.csv','transfers.csv','diagnostic-weight-tail.csv','diagnostic-transfers.csv','run-result.json','validation.json','compute-validation.json']} for ident in ids}
 (a.out/'input-manifest.json').write_text(json.dumps(inputs,indent=2)+'\n')
 (a.out/'summary.json').write_text(json.dumps(dict(status='PASS',scope='formal six-case supplement' if a.formal else 'accepted historical v3 evidence only; not new formal B results',results=results),indent=2)+'\n')
 (a.out/'manifest.json').write_text(json.dumps({p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()},indent=2)+'\n')
 print(json.dumps({'status':'PASS','rows':{k:len(v) for k,v in collected.items()}},indent=2))
if __name__=='__main__':main()
