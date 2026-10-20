#!/usr/bin/env python3
"""Allowlist compact aggregate evidence; never copies input, routing, per-token rows or payload."""
import argparse,csv,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=a.private;o=a.out;o.mkdir(parents=True,exist_ok=False)
def read(p):return json.loads(p.read_text())
def csvrows(p):return list(csv.DictReader(p.open()))
def write(name,rows):
 with (o/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['status']);w.writeheader();w.writerows(rows)
def host(x):return {k:x[k] for k in ['status','guard','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','limits']}
def cp(src,dest):dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
sa=root/'stage-a';sb=root/'stage-b';reg=root/'regression'
assert read(sa/'stage-a-status.json')['full_matrix'];assert read(sb/'ledger.json')['status']=='PASS';assert read(reg/'status.json')['status']=='PASS'
assert [x['strategy'] for x in read(sb/'ledger.json')['runs']]==['no-balancing','direct','chunk-streaming','multicast-v2']
assert all(x['status']=='PASS' for x in read(sb/'ledger.json')['runs'])
diagnostic=root.parent/'stage-b/ledger.json'
if diagnostic.exists() and read(diagnostic).get('status')=='PAUSED_OPERATOR_RESOURCE_ADMISSION':
 first=read(diagnostic)['runs'][0]
 before=read(root.parent/'stage-a/shared-receivers/no-balancing/simulator-host/resource.json');after=read(sa/'shared-receivers/no-balancing/simulator-host/resource.json')
 (o/'resource-readmission.json').write_text(json.dumps(dict(first_nobal_simulated_layer_ps=first['summary']['layer_latency_ps'],first_nobal_host=host(first['simulator_host']),historical_native_asserts=False,all_current_runs_native_asserts=True,interrupted_case='direct; no result; operator exit130',matched_synthetic_before_cache=host(before),matched_synthetic_after_cache=host(after),optimization='Only TypeId attribute-presence cache; positive getter and all eligibility/credit checks unchanged.'),indent=2)+'\n')
cp(root/'two-stage-regression/status.json',o/'regression/two-stage.json')
(o/'native-build.json').write_text(json.dumps(host(read(root/'full-native-build/resource.json')),indent=2)+'\n')
small=[]
for x in read(sa/'results.json'):
 small.append(dict(case=x['case'],strategy=x['mode'],status=x['status'],layer_latency_ps=x['summary']['layer_latency_ps'],remote_wqes=x['summary']['remote_WQEs'],sender_completions=x['summary']['sender_completions'],pair_jetties=x['summary']['jettys'],output_hash=x['summary']['combine_fnv1a64']))
write('stage-a.csv',small)
for rel in ['stage-a-status.json','pair-stress/paired-small/summary.json','pair-stress/paired-small/events.csv','pair-stress/paired-small/groups.csv','pair-stress/paired-small/ports.csv','pair-stress/paired-window/summary.json','pair-stress/paired-window/events.csv','pair-stress/paired-window/groups.csv','pair-stress/paired-window/ports.csv']:
 cp(sa/rel,o/'stage-a'/rel)
for case in ['multi-target/multicast-v2','network/data-once','network/ack-once','network/invalidate-grant']:
 for file in ['weight-packets.csv','multicast-groups.csv','multicast-stats.csv','multicast-lifecycle.json','pair-state.csv','network-resources.csv','validation.json']:
  cp(sa/case/file,o/'stage-a'/case/file)
for name in ['application-parity.json','status.json'] :cp(reg/name,o/'regression'/name)
cp(reg/'v2/results.json',o/'regression/v1-v2.json')
for case in ['normal','data-once','ack-once','response-once']:cp(reg/('retx-'+case)/'results.json',o/'regression'/('retx-'+case+'.json'))
rows=[];communication=[];experts=[];nodes=[];ledger=read(sb/'ledger.json')
(o/'planner-host.json').write_text(json.dumps({mode:read(sb/('prepare-'+mode)/'preparation-summary.json') for mode in ['no-balancing','direct']},indent=2)+'\n')
for record in ledger['runs']:
 mode=record['strategy'];d=sb/mode;s=record['summary'];t=s['timeline'];interval=s['stage_intervals'];compute=s['compute_intervals'];hc=record['simulator_host']
 row=dict(strategy=mode,execution_mode=record.get('execution_mode','serial'),planner_ns=(t['planning_end']-t['layer_start'])/1000,reroute_ns=(t['reroute_end']-t['planning_end'])/1000,weight_ns=(t['weights_end']-t['planning_end'])/1000,dispatch_span_ns=(interval[0][1]-interval[0][0])/1000,compute_span_ns=(max(x['end_ps'] for x in compute)-min(x['start_ps'] for x in compute))/1000,compute_max_node_ns=max(x['end_ps']-x['start_ps'] for x in compute)/1000,combine_span_ns=(interval[1][1]-interval[1][0])/1000,layer_ns=s['layer_latency_ps']/1000,host_wall_seconds=hc['wall_seconds'],host_cpu_seconds=hc['user_cpu_seconds']+hc['system_cpu_seconds'],peak_rss_kib=hc['peak_rss_kib'],remote_wqes=s['remote_WQEs'],ta_count=s['TA_count'],sender_completions=s['sender_completions'],pair_jetties=s['jettys'],output_hash=s['combine_fnv1a64']);rows.append(row)
 for x in compute:nodes.append(dict(strategy=mode,**x))
 for file in ['online-summary.json','simulator-metrics.json','validation.json','packet-counts.csv','expert-ready.csv','network-resources.csv','pair-state.csv']:
  cp(d/file,o/'real'/mode/file)
 (o/'real'/mode/'host.json').write_text(json.dumps(host(hc),indent=2)+'\n')
 for x in csvrows(d/'expert-ready.csv'):experts.append(dict(strategy=mode,expert=int(x['expert']),fanout=int(x['fanout']),ready_ps=int(x['ready_ps']),distribution_duration_ns=(int(x['ready_ps'])-t['planning_end'])/1000))
 packets=csvrows(d/'packet-counts.csv');source=[x for x in packets if int(x['node'])<64 and x['kind'] in ['weight_write','multicast_v2']];down=[x for x in packets if int(x['node'])==64 and x['kind']=='weight_write'];sourcewire=sum(int(x['wire_bytes']) for x in source);downwire=sum(int(x['wire_bytes']) for x in down)
 if mode=='multicast-v2':
  stats=csvrows(d/'multicast-stats.csv');sourcepayload=sum(int(x['payload_bytes']) for x in stats);headers=sum(int(x['header_bytes']) for x in stats);multiexperts=sum(int(x['fanout'])>1 for x in stats);envelopes=sum(int(x['envelopes']) for x in stats);branches=sum(int(x['fanout'])*int(x['envelopes']) for x in stats)
  for file in ['multicast-groups.csv','multicast-stats.csv','multicast-lifecycle.json','weight-ready.csv']:cp(d/file,o/'real'/mode/file)
 else:sourcepayload=0 if mode=='no-balancing' else s['remote_bytes'][2];headers=sourcewire-sourcepayload;multiexperts=envelopes=branches=0
 weight_wqes=sum(x['stage']==2 and x['source']!=x['target'] for x in read(d/'config.json')['transfers'])
 communication.append(dict(strategy=mode,graph_weight_wqes=weight_wqes,native_weight_write_packets=sum(int(x['packets']) for x in down),multicast_experts=multiexperts,envelopes=envelopes,multicast_native_branches=branches,source_weight_payload_bytes=sourcepayload,source_weight_wire_bytes=sourcewire,source_weight_header_bytes=headers,switch_weight_wire_bytes=downwire,all_network_wire_bytes=sum(s['byte_tx_per_node'])))
base=rows[0]['layer_ns'];direct=rows[1];chunk=rows[2];mc=rows[3]
for row in rows:row['speedup_vs_nobal']=base/row['layer_ns']
write('performance.csv',rows);write('communication.csv',communication);write('expert-ready.csv',experts);write('compute-nodes.csv',nodes)
fanout={}
for x in csvrows(sb/'multicast-v2/multicast-stats.csv'):fanout[int(x['fanout'])]=fanout.get(int(x['fanout']),0)+1
write('fanout.csv',[dict(fanout=k,experts=v) for k,v in sorted(fanout.items())])
summary=dict(status='PASS',multicast_vs_direct_layer_speedup=direct['layer_ns']/mc['layer_ns'],multicast_vs_chunk_layer_speedup=chunk['layer_ns']/mc['layer_ns'],multicast_vs_direct_weight_speedup=direct['weight_ns']/mc['weight_ns'],multicast_vs_chunk_weight_speedup=chunk['weight_ns']/mc['weight_ns'],fanout=fanout,last_weight_ready_experts={mode:max((x for x in experts if x['strategy']==mode),key=lambda x:x['ready_ps']) for mode in ['direct','chunk-streaming','multicast-v2']},binary_identity=ledger['binary_identity'],input_identity=ledger['input_identity'],planning_identity=[{k:x[k] for k in ['strategy','plan_semantic_sha256','assignments_sha256','input_sha256','config_sha256']} for x in ledger['runs']])
children=csvrows(sb/'multicast-v2/multicast-groups.csv');fanin={}
for x in children:fanin[int(x['target'])]=fanin.get(int(x['target']),0)+1
write('receiver-fanin.csv',[dict(target=k,weight_copies=v,payload_bytes=v*18874368) for k,v in sorted(fanin.items())])
last=max(children,key=lambda x:int(x['receiver_ready_ps']));summary['last_multicast_weight_child']={k:int(last[k]) for k in ['group','expert','source','target','physical','receiver_ready_ps','sender_complete_ps']};summary['last_multicast_weight_child']['receiver_weight_fanin']=fanin[int(last['target'])]
byfan=[]
for mode in ['direct','chunk-streaming','multicast-v2']:
 for fan in sorted(fanout):
  selected=[x for x in experts if x['strategy']==mode and x['fanout']==fan]
  byfan.append(dict(strategy=mode,fanout=fan,experts=len(selected),mean_ready_duration_ns=sum(x['distribution_duration_ns'] for x in selected)/len(selected),max_ready_duration_ns=max(x['distribution_duration_ns'] for x in selected)))
write('fanout-readiness.csv',byfan)
summary['execution_resume']=ledger.get('explicit_resume')
summary['parallel_execution']=ledger.get('parallel_execution')
summary['metric_notes']={'source_weight_bytes':'Sum across all transmitting hosts, including Chunk relays; not main-source-only.', 'last_weight_ready_experts':'Latest receiver-ready expert, determining global Dispatch gate only when weights_end >= reroute_end; not attribution of downstream compute/Combine critical path.', 'phase_spans':'Dispatch, compute and Combine may overlap; their spans are not additive.'}
(o/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
