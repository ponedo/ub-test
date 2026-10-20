"""Publish only bounded summary and per-expert evidence, never raw token routing/payload."""
import argparse,csv,json,shutil,datetime,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;OLD=H.parent/'ultraep-multicast-integration'
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();private=a.private.resolve();r=private/'real';o=a.out.resolve()
def j(p):return json.loads(Path(p).read_text())
def read(p):return list(csv.DictReader(Path(p).open()))
def write(name,rows):
 with (o/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def cp(src,name):dest=o/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
def host(x):return {k:x[k] for k in ['status','guard','start','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','limits']}
l=j(r/'ledger.json');sa=j(private/'stage-a/status.json');assert l['status']==sa['status']=='PASS'
assert [x['strategy'] for x in l['runs']]==['no-balancing','direct','chunk-streaming','multicast-v2']
assert sa['legacy_exact_cases']==sa['roofline_cases']==16
assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in l['binary_identity'].items())
native=next(Path(k).parents[2] for k in l['binary_identity'] if k.endswith('/libns3.44-unified-bus.so'))
assert all(hashlib.sha256((native/k).read_bytes()).hexdigest()==v for k,v in j(OLD/'candidate-native-source-sha256.json').items())
for x in l['runs']:
 assert x['status']=='PASS'
 for key in ['simulator_host','postflight_host','independent_host','compute_host']:
  assert x[key]['status']=='PASS' and x[key]['guard'] is None
  assert j(r/x['strategy']/key.replace('_','-')/'resource.json')==x[key]
 for key,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert hashlib.sha256((r/x['strategy']/name).read_bytes()).hexdigest()==x[key]
 assert j(r/x['strategy']/'compute-validation.json')['status']=='PASS'
o.mkdir(parents=True,exist_ok=False)
legacy=[]
for x in read(OLD/'results/performance.csv'):
 legacy.append(dict(model='legacy',strategy=x['strategy'],planner_ns=float(x['planner_ns']),reroute_ns=float(x['reroute_ns']),weight_ns=float(x['weight_ns']),dispatch_span_ns=float(x['dispatch_span_ns']),compute_span_ns=float(x['compute_span_ns']),compute_max_node_ns=float(x['compute_max_node_ns']),combine_span_ns=float(x['combine_span_ns']),layer_ns=float(x['layer_ns']),host_wall_seconds=float(x['host_wall_seconds']),host_cpu_seconds=float(x['host_cpu_seconds']),peak_rss_kib=int(x['peak_rss_kib']),source_commit='ef1ec5c801ab854363b6382a2af9aa5237ade4c8'))
rows=legacy[:];resources=[];comm=[];compute=[]
for x in l['runs']:
 mode=x['strategy'];d=r/mode;s=x['summary'];t=s['timeline'];st=s['stage_intervals'];ci=s['compute_intervals'];hc=x['simulator_host']
 row=dict(model='roofline',strategy=mode,planner_ns=(t['planning_end']-t['layer_start'])/1000,reroute_ns=(t['reroute_end']-t['planning_end'])/1000,weight_ns=(t['weights_end']-t['planning_end'])/1000,dispatch_span_ns=(st[0][1]-st[0][0])/1000,compute_span_ns=(max(z['end_ps'] for z in ci)-min(z['start_ps'] for z in ci))/1000,compute_max_node_ns=max(z['end_ps']-z['start_ps'] for z in ci)/1000,combine_span_ns=(st[1][1]-st[1][0])/1000,layer_ns=s['layer_latency_ps']/1000,host_wall_seconds=hc['wall_seconds'],host_cpu_seconds=hc['user_cpu_seconds']+hc['system_cpu_seconds'],peak_rss_kib=hc['peak_rss_kib'],source_commit='this-delivery')
 assert row['weight_ns']==next(z['weight_ns'] for z in legacy if z['strategy']==mode),'weight behavior changed'
 rows.append(row);ex=read(d/'expert-compute.csv');active=[z for z in ex if int(z['tokens'])]
 compute.append(dict(strategy=mode,active_experts=len(active),memory_bound_experts=sum(z['bottleneck']=='memory' for z in active),compute_bound_experts=sum(z['bottleneck']=='compute' for z in active),flops=sum(int(z['flops']) for z in active),weight_hbm_bytes=sum(int(z['weight_hbm_bytes']) for z in active),activation_hbm_bytes=sum(int(z['activation_hbm_bytes']) for z in active),serial_expert_time_sum_ps=sum(int(z['duration_ps']) for z in active),latest_compute_node=max(ci,key=lambda z:z['end_ps'])['node'],latest_compute_end_ps=max(z['end_ps'] for z in ci),layer_end_ps=t['layer_end']))
 packets=read(d/'packet-counts.csv');sources=[z for z in packets if int(z['node'])<64 and z['kind'] in ['weight_write','multicast_v2']];down=[z for z in packets if int(z['node'])==64 and z['kind']=='weight_write']
 payload=sum(int(z['payload_bytes']) for z in read(d/'multicast-stats.csv')) if mode=='multicast-v2' else s['remote_bytes'][2]
 wire=sum(int(z['wire_bytes']) for z in sources);comm.append(dict(strategy=mode,all_host_weight_payload_bytes=payload,all_host_weight_wire_bytes=wire,weight_header_bytes=wire-payload,switch_down_weight_wire_bytes=sum(int(z['wire_bytes']) for z in down),all_network_wire_bytes=sum(s['byte_tx_per_node'])))
 start=datetime.datetime.fromisoformat(hc['start']);end=start+datetime.timedelta(seconds=hc['wall_seconds']);others=[]
 for y in l['runs']:
  if y is x:continue
  ys=datetime.datetime.fromisoformat(y['simulator_host']['start']);ye=ys+datetime.timedelta(seconds=y['simulator_host']['wall_seconds'])
  overlap=(min(end,ye)-max(start,ys)).total_seconds()
  if overlap>0:others.append(y['strategy']+':'+str(round(overlap,3))+'s')
 resources.append(dict(strategy=mode,start_utc=start.isoformat(),end_utc=end.isoformat(),concurrent_overlap=';'.join(others),wall_seconds=hc['wall_seconds'],cpu_seconds=hc['user_cpu_seconds']+hc['system_cpu_seconds'],peak_rss_kib=hc['peak_rss_kib'],sampled_peak_tree_rss_bytes=hc['sampled_peak_tree_rss_bytes'],guard=str(hc['guard'])))
 for f in ['online-summary.json','validation.json','compute-validation.json','compute-model.json','expert-compute.csv','expert-ready.csv','packet-counts.csv','network-resources.csv']:cp(d/f,'real/'+mode+'/'+f)
 states=read(d/'pair-state.csv')
 transport=dict(status='PASS',transport_directions=len(states),all_psn_windows_drained=all(z['send_una']==z['send_nxt'] for z in states),all_ta_windows_drained=all(z['ta_una']==z['ta_nxt'] for z in states),unacked=sum(int(z['unacked']) for z in states),descriptors=sum(int(z['descriptors']) for z in states),timers=sum(int(z['timer']) for z in states),active_wqes=sum(int(z['active_wqes']) for z in states),note='Endpoint/pair identifiers and individual sequence values intentionally omitted from public evidence; detailed source remains private.')
 assert transport['all_psn_windows_drained'] and transport['all_ta_windows_drained'] and not any(transport[k] for k in ['unacked','descriptors','timers','active_wqes'])
 (o/'real'/mode/'transport-state-summary.json').write_text(json.dumps(transport,indent=2)+'\n')
 (o/'real'/mode/'host.json').write_text(json.dumps(host(hc),indent=2)+'\n')
 if mode=='multicast-v2':
  for f in ['multicast-lifecycle.json','multicast-stats.csv','multicast-groups.csv']:cp(d/f,'real/'+mode+'/'+f)
for row in rows:
 base=next(z for z in rows if z['model']==row['model'] and z['strategy']=='no-balancing')
 row['speedup_vs_nobal']=base['layer_ns']/row['layer_ns'];row['weight_layer_fraction']=row['weight_ns']/row['layer_ns'];row['post_dispatch_gate_ns']=row['layer_ns']-row['planner_ns']-max(row['weight_ns'],row['reroute_ns'])
assert len({x['flops'] for x in compute})==len({x['activation_hbm_bytes'] for x in compute})==1
assert compute[0]['flops']==6*2048*8*4096*1536
write('performance.csv',rows);write('communication.csv',comm);write('resources.csv',resources);write('compute-aggregate.csv',compute)
comparisons=[]
for model in ['legacy','roofline']:
 chunk=next(x for x in rows if x['model']==model and x['strategy']=='chunk-streaming');mc=next(x for x in rows if x['model']==model and x['strategy']=='multicast-v2')
 comparisons.append(dict(model=model,multicast_vs_chunk_weight_speedup=chunk['weight_ns']/mc['weight_ns'],multicast_vs_chunk_layer_speedup=chunk['layer_ns']/mc['layer_ns'],weight_saved_ns=chunk['weight_ns']-mc['weight_ns'],layer_saved_ns=chunk['layer_ns']-mc['layer_ns'],post_gate_difference_ns=chunk['post_dispatch_gate_ns']-mc['post_dispatch_gate_ns']))
write('comparison.csv',comparisons)
for name in ['status.json','unit/status.json','unit/token-latency.csv']:cp(private/'stage-a'/name,'stage-a/'+name)
small=[]
for x in j(private/'stage-a/results.json'):small.append(dict(case=x['case'],strategy=x['strategy'],model=x['model'],status=x['status'],layer_latency_ps=x['summary']['layer_latency_ps'],output_hash=x['summary']['combine_fnv1a64']))
write('stage-a.csv',small)
for model in ['legacy','roofline']:
 for case in ['data-once','ack-once','invalidate-grant']:
  for name in ['weight-packets.csv','compute-validation.json','validation.json','multicast-lifecycle.json']:cp(private/'stage-a/network'/model/case/name,'stage-a/network/'+model+'/'+case+'/'+name)
cp(r/'parallel-resource-record.json','parallel-resource-record.json')
samples=j(r/'parallel-resource-samples.json');(o/'host-pressure-summary.json').write_text(json.dumps(dict(samples=len(samples),min_host_available_bytes=min(x[1] for x in samples),max_cpu_percent=max(x[2] for x in samples),max_load1=max(x[3] for x in samples),note='System-wide availability and CPU can include unrelated activity; PID visibility is sandbox-limited. Concurrent host times are not strict performance comparisons.'),indent=2)+'\n')
build_history=[]
for name in ['native-configure','native-configure-restored-tools','native-full-build','native-full-build-resume-j2']:
 if (private/name/'resource.json').exists():
  item=host(j(private/name/'resource.json'));build_history.append(dict(stage=name,**item));(o/(name+'.json')).write_text(json.dumps(item,indent=2)+'\n')
summary=dict(status='PASS',build_history=build_history,historical_legacy_commit='ef1ec5c801ab854363b6382a2af9aa5237ade4c8',legacy_small_exact_cases=16,roofline_small_cases=16,binary_identity=l['binary_identity'],input_identity=l['input_identity'],comparisons=comparisons,preparation_host={k:host(v) for k,v in l['preparation'].items()},planning_identity=[{k:x[k] for k in ['strategy','plan_semantic_sha256','assignments_sha256','input_sha256','config_sha256']} for x in l['runs']],native_source_unchanged=True)
(o/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(comparisons,indent=2))
