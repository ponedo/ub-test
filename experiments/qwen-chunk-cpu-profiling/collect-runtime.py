#!/usr/bin/env python3
"""Collect completed/partial runtime evidence without starting any simulation."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,default=H/'evidence');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
def writecsv(name,rows):
 if not rows:return
 with (a.out/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!='verification_wall_ns'}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
resources=[];phases=[];counters=[];progress=[];parity=[]
for d in sorted((a.raw/'runtime').iterdir()):
 if not (d/'host/resource.json').exists():continue
 r=json.loads((d/'host/resource.json').read_text());prov=json.loads((d/'provenance.json').read_text());row=dict(run=d.name,case=prov['case'],variant=prov['variant'],status=r['status'],guard=r['guard'],wall_seconds=r['wall_seconds'],user_cpu_seconds=r['user_cpu_seconds'],system_cpu_seconds=r['system_cpu_seconds'],peak_rss_kib=r['peak_rss_kib'],sampled_peak_tree_rss_bytes=r['sampled_peak_tree_rss_bytes'],simulator_complete=(d/'run/online-summary.json').exists(),simulator_events=None,simulator_events_per_process_cpu_second=None,layer_latency_ps=None,remote_WQEs=None,TA_count=None,port_packet_tx_total=None)
 dest=a.out/'runtime'/d.name;dest.mkdir(parents=True,exist_ok=True)
 for f in ['provenance.json','status.json','host/resource.json','host/resource-samples.csv','host/console.txt','timing.json','timing-history.jsonl','run/online-summary.json','run/validation.json','run/simulator-metrics.json']:
  if (d/f).exists():shutil.copyfile(d/f,dest/Path(f).name)
 if row['simulator_complete']:
  s=json.loads((d/'run/online-summary.json').read_text());row.update(simulator_events=s['simulator_events'],simulator_events_per_process_cpu_second=s['simulator_events']/(r['user_cpu_seconds']+r['system_cpu_seconds']),layer_latency_ps=s['layer_latency_ps'],remote_WQEs=s['remote_WQEs'],TA_count=s['TA_count'],port_packet_tx_total=sum(s['packet_tx_per_node']))
  baseline=a.raw.parent/'qwen-model-size-raw/scan/tokens-256'/prov['case']/'run/online-summary.json'
  if baseline.exists():
   same=stable(s)==stable(json.loads(baseline.read_text()));parity.append(dict(run=d.name,reference=str(baseline),same_stable_full_summary=same,excluded_fields=['verification_wall_ns']))
   if not same:raise RuntimeError('Large completed-case stable summary differs: '+d.name)
 if (d/'timing.json').exists():
  t=json.loads((d/'timing.json').read_text())
  for phase,v in t['phases'].items():phases.append(dict(run=d.name,phase=phase,complete=t['complete'],**v))
  for name,value in t['counters'].items():counters.append(dict(run=d.name,counter=name,count=value,complete=t['complete']))
  hist=d/'timing-history.jsonl'
  if hist.exists():
   prev=None
   for line in hist.read_text().splitlines():
    j=json.loads(line);e=j['simulator_events'];cpu=j['process_cpu_ns']/1e9;wall=j['wall_ns']/1e9
    progress.append(dict(run=d.name,wall_seconds=wall,process_cpu_seconds=cpu,reason=j['reason'],active_phase=j['active_phase'],simulator_events=e,simulated_time_ps=j['simulated_time_ps'],events_per_cpu_second_since_previous=(e-prev[0])/(cpu-prev[1]) if prev and cpu>prev[1] else None))
    prev=(e,cpu)
 resources.append(row)
writecsv('runtime-resources.csv',resources);writecsv('runtime-phases.csv',phases);writecsv('runtime-counters.csv',counters);writecsv('runtime-progress.csv',progress)
(a.out/'completed-large-parity.json').write_text(json.dumps(dict(status='PASS' if parity and all(x['same_stable_full_summary'] for x in parity) else 'NO_COMPLETED_CASES',checks=parity,partial_chunk='No completed Chunk summary; small event parity and static proof do not establish large-cutoff progress equality.'),indent=2)+'\n')
print(json.dumps(resources,indent=2))
