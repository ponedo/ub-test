#!/usr/bin/env python3
"""Export aggregates only. Failed cases never receive simulated performance values."""
import argparse,csv,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True)
def csvwrite(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r)) or ['layer','tokens','strategy']
 with (a.out/name).open('w') as f:w=csv.DictWriter(f,keys,lineterminator="\n");w.writeheader();w.writerows(rows)
def readcsv(p,required=False):
 if not p.exists():
  if required:raise ValueError('missing required measured evidence: '+str(p))
  return []
 with p.open() as f:return list(csv.DictReader(f))
ledger=json.loads((a.private/'run-ledger.json').read_text());perf=[];hosts=[];packets=[];queues=[];groups=[];ports=[];prov=[];status=[];summaries=[]
for r in ledger:
 l,s=r['layer'],r['strategy'];base=dict(layer=l,tokens=2048,strategy=s);status.append(dict(base,status=r['status'],failure=r.get('failure','')))
 for stage in ['preparation','preflight','simulator','postflight']:
  h=r.get(stage+'_host');hp=a.private/f'L{l}'/s/(stage+'-host/resource.json')
  if h is None and hp.exists():h=json.loads(hp.read_text())
  if h:hosts.append(dict(base,stage=stage,status=h['status'],wall_seconds=h['wall_seconds'],cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'],sampled_peak_tree_rss_bytes=h['sampled_peak_tree_rss_bytes'],guard=h['guard']))
 if r['status']!='PASS':continue
 d=a.private/f'L{l}'/s/'prepared'/('multicast-run' if s=='multicast' else 'run');summary=r['summary'];config=json.loads((d/'config.json').read_text());plan=json.loads((d/'plan.json').read_text());pc=readcsv(d/'packet-counts.csv',True);gs=readcsv(d/'multicast-stats.csv',s=='multicast');
 for x in pc:assert {'node','kind','wire_bytes','packets'}<=x.keys()
 assert (d/'queue-stats.csv').exists()
 physical={x['id']:x for x in plan['physical']};weights=[x for x in config['transfers'] if x['stage']==2]
 main=sum(int(x['payload_bytes']) for x in gs) if s=='multicast' else sum(x['bytes'] for x in weights if physical[x['source_physical']]['kind']=='main')
 timeline=summary['timeline'];h=r['simulator_host']
 row=dict(base,status='PASS',layer_latency_ms=summary['layer_latency_ps']/1e9,weight_duration_ms=(timeline['weights_end']-timeline['planning_end'])/1e9,replicas=summary['replicas'],groups=len(gs),main_weight_payload_bytes=main,weight_destination_bytes=sum(x['bytes'] for x in weights),all_npu_weight_request_wire_bytes=sum(int(x['wire_bytes']) for x in pc if int(x['node'])<64 and x['kind'] in ('weight_write','multicast_data')),all_network_wire_bytes=sum(int(x['wire_bytes']) for x in pc),host_transport_ack_packets=sum(int(x['packets']) for x in pc if int(x['node'])<64 and x['kind']=='transport_ack'),host_transaction_response_packets=sum(int(x['packets']) for x in pc if int(x['node'])<64 and x['kind']=='transaction_response'),remote_WQEs=summary['remote_WQEs'],TAs=summary['TA_count'],jettys=summary['jettys'],events=summary['simulator_events'],max_npu_load=summary['max_npu_load'],wall_seconds=h['wall_seconds'],cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'],validation=r['validation']['status'])
 row['main_origin_weight_wire_bytes']=sum(int(x['wire_bytes']) for x in gs) if s=='multicast' else sum(x['bytes']+78*((x['bytes']+1023)//1024) for x in weights if physical[x['source_physical']]['kind']=='main')
 row['main_origin_wire_basis']='measured group source counters' if s=='multicast' else 'derived from verified executed main-origin tasks and native 78B per-TA header'
 row['all_npu_wire_basis']='measured packet transmission counters; includes relay senders'
 if s!='multicast':assert row['all_npu_weight_request_wire_bytes']==sum(x['bytes']+78*((x['bytes']+1023)//1024) for x in weights)
 perf.append(row)
 for name,output in [('packet-counts.csv',packets),('queue-stats.csv',queues),('multicast-stats.csv',groups),('multicast-ports.csv',ports)]:
  output.extend(dict(base,**x) for x in readcsv(d/name))
 prov.append(dict(base,**{k:v for k,v in r.items() if k.endswith('sha256')},runtime=config['runtime'],planner_parameters={k:v for k,v in config['planner_input'].items() if k!='mapping'}))
 summaries.append(dict(base,summary=summary,validation=r['validation']))
for r in perf:
 nb=next((x for x in perf if x['layer']==r['layer'] and x['strategy']=='no-balancing'),None);chunk=next((x for x in perf if x['layer']==r['layer'] and x['strategy']=='chunk-streaming'),None)
 r['speedup_vs_no_balancing']=nb['layer_latency_ms']/r['layer_latency_ms'] if nb else ''
 r['multicast_speedup_vs_chunk']=chunk['layer_latency_ms']/r['layer_latency_ms'] if chunk and r['strategy']=='multicast' else ''
for name,rows in [('performance.csv',perf),('status.csv',status),('host-resources.csv',hosts),('packet-counts.csv',packets),('queue-wait.csv',queues),('groups.csv',groups),('multicast-ports.csv',ports)]:csvwrite(name,rows)
for name,data in [('input-provenance.json',prov),('execution-summaries.json',summaries)]: (a.out/name).write_text(json.dumps(data,indent=2)+'\n')
expected={(l,s) for l in [37,0,52] for s in ['no-balancing','direct','chunk-streaming','multicast']}
missing=expected-{(r['layer'],r['strategy']) for r in ledger}
(a.out/'coverage.json').write_text(json.dumps({'completed':len(perf),'recorded':len(ledger),'not_run':[dict(layer=l,strategy=s,reason='awaiting prior gate or protected stop') for l,s in sorted(missing)]},indent=2)+'\n')
print('Exported',len(perf),'measured cases')
