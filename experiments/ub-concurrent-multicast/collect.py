#!/usr/bin/env python3
"""Publish small aggregate evidence only; never copies Payload or native packet traces."""
import argparse,csv,json,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=a.private;o=a.out;o.mkdir(parents=True,exist_ok=True)
def write_csv(name,rows):
 if not rows:return
 with (o/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
results=json.loads((r/'layer-queue-stats/results.json').read_text());perf=[];hosts=[];groups=[];ports=[];counts=[];queues=[];summaries=[];inputs=[]
for row in results:
 case,mode=row['case'],row['strategy'];d=r/'layer-queue-stats'/case/mode;s=row['summary'];c=json.loads((d/'config.json').read_text());n=c['planner_input']['npus'];packets=list(csv.DictReader((d/'packet-counts.csv').open()));weight=[x for x in c['transfers'] if x['stage']==2];byid={x['id']:x for x in json.loads((d/'plan.json').read_text())['physical']}
 stats=list(csv.DictReader((d/'multicast-stats.csv').open())) if mode=='multicast' else []
 main_payload=sum(int(x['payload_bytes']) for x in stats) if mode=='multicast' else sum(x['bytes'] for x in weight if byid[x['source_physical']]['kind']=='main')
 all_payload=sum(int(x['payload_bytes']) for x in stats) if mode=='multicast' else sum(x['bytes'] for x in weight)
 cpu=row['host']['simulator']['user_cpu_seconds']+row['host']['simulator']['system_cpu_seconds'];phase=s['timeline']
 perf.append(dict(case=case,strategy=mode,tokens=c['planner_input']['tokens'] if 'tokens' in c['planner_input'] else len(c['planner_input']['mapping']),top_k=c['planner_input']['top_k'],npus=n,replicas=s['replicas'],groups=len(stats),layer_latency_us=s['layer_latency_ps']/1e6,weight_duration_us=(phase['weights_end']-phase['planning_end'])/1e6,remote_WQEs=s['remote_WQEs'],logical_TAs=s['TA_count'],jettys=s['jettys'],main_weight_payload_bytes=main_payload,all_npu_weight_payload_bytes=all_payload,host_origin_weight_wire_bytes=sum(int(x['wire_bytes']) for x in packets if int(x['node'])<n and x['kind'] in ('weight_write','multicast_data')),total_network_wire_bytes=sum(int(x['wire_bytes']) for x in packets),host_origin_transport_ack_packets=sum(int(x['packets']) for x in packets if int(x['node'])<n and x['kind']=='transport_ack'),host_origin_transaction_response_packets=sum(int(x['packets']) for x in packets if int(x['node'])<n and x['kind']=='transaction_response'),wall_seconds=row['host']['simulator']['wall_seconds'],cpu_seconds=cpu,peak_rss_kib=row['host']['simulator']['peak_rss_kib'],validation='PASS'))
 for stage,h in row['host'].items():hosts.append(dict(case=case,strategy=mode,stage=stage,status=h['status'],wall_seconds=h['wall_seconds'],cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'],guard=h['guard']))
 summaries.append({k:row[k] for k in ['case','strategy','status','plan_hash','assignments_hash','summary','validation']})
 inputs.append(dict(case=case,strategy=mode,input_sha256=hashlib.sha256((d/'input.txt').read_bytes()).hexdigest(),config_sha256=hashlib.sha256((d/'config.json').read_bytes()).hexdigest(),plan_sha256=row['plan_hash'],assignments_sha256=row['assignments_hash'],runtime=c['runtime'],planner_parameters={k:v for k,v in c['planner_input'].items() if k!='mapping'}))
 if mode=='multicast':
  for x in stats:groups.append(dict(case=case,**x))
  for x in csv.DictReader((d/'multicast-ports.csv').open()):ports.append(dict(case=case,**x))
 for x in csv.DictReader((d/'queue-stats.csv').open()):queues.append(dict(case=case,strategy=mode,**x))
 for x in packets:counts.append(dict(case=case,strategy=mode,**x))
for x in perf:
 direct=next(y for y in perf if y['case']==x['case'] and y['strategy']=='direct');x['speedup_vs_direct']=direct['layer_latency_us']/x['layer_latency_us']
write_csv('queue-wait.csv',queues);write_csv('performance.csv',perf);write_csv('host-resources.csv',hosts);write_csv('groups.csv',groups);write_csv('multicast-ports.csv',ports);write_csv('packet-counts.csv',counts)
(o/'execution-summaries.json').write_text(json.dumps(summaries,indent=2)+'\n');(o/'input-provenance.json').write_text(json.dumps(inputs,indent=2)+'\n')
for src,name in [('concurrent-release-results/results.json','concurrent-tests.json'),('regressions1/singleton-results/results.json','singleton-gate.json'),('regressions1/old-multi-results/results.json','old-multicast-tests.json'),('regressions1/old-verifier-mutations/results.json','old-verifier-mutations.json'),('regressions1/application-parity.json','application-parity.json'),('regressions1/network-parity.json','network-byte-parity.json'),('regressions1/native-final.json','native-tests.json'),('debug-parity-final.json','debug-parity.json'),('telemetry-parity.json','telemetry-parity.json'),('faults-queue-stats/results.json','layer-faults.json')]:
 shutil.copy2(r/src,o/name)
for file in ['groups.csv']:
 shutil.copy2(r/'concurrent-release-results/dynamic'/file,o/('dynamic-'+file))
shutil.copy2(r/'layer-queue-stats/slow_relay8/multicast/multicast-groups.csv',o/'slow-target-ready.csv')
shutil.copy2(r/'regressions1/native-retry/unified-bus-examples/console.txt',o/'known-native-parser-failure.txt')
# Hash large/private evidence rather than publishing it.
manifest=[]
for sub in ['concurrent-release-results','debug-queue-stats','layer-queue-stats','faults-queue-stats']:
 for f in sorted((r/sub).rglob('*')):
  if f.is_file() and f.suffix in ('.csv','.json','.bin'):
   manifest.append(dict(path=str(f.relative_to(r)),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
(o/'private-evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Collected',len(perf),'measured application cases')
