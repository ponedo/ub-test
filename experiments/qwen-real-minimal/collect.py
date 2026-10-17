#!/usr/bin/env python3
"""Aggregate-only public export; never copies private routing/plan/task files."""
import argparse,csv,hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
ledger=json.loads((a.private/'runs.json').read_text());rank={int(r['layer']):r for r in csv.DictReader((H/'results/layer-ranking.csv').open())}
terminal=json.loads((a.private/'status.json').read_text())
rows=[];resources=[];proofs=[]
for rec in ledger:
 if rec['status']=='RUNNING' and terminal['status']=='STOPPED':rec['status']='STOPPED'
 layer=rec['layer'];strategy=rec['strategy'];s=rec.get('summary',{});t=rec.get('times',{});host=rec.get('simulator_host',{})
 refs=[r for r in ledger if r['layer']==layer and r['strategy']=='no-balancing' and r['status']=='PASS']
 row=dict(layer=layer,strategy=strategy,status=rec['status'],tokens=256,assignments=2048,routing_sha256=rec['routing_sha256'],layer_latency_ms=s.get('layer_latency_ps',0)/1e9 if s else '',speedup=refs[0]['summary']['layer_latency_ps']/s['layer_latency_ps'] if refs and s else '',replicas=s.get('replicas',''),max_npu_load=s.get('max_npu_load',''),weight_bytes=s.get('weight_bytes',''),weight_duration_ms=s.get('weight_target_duration_ps',0)/1e9 if s else '',remote_wqes=s.get('remote_WQEs',''),ta_count=s.get('TA_count',''),weight_wqes=s.get('weight_WQEs',''),weight_tas=s.get('weight_TAs',''),simulator_events=s.get('simulator_events',''),host_wall_seconds=host.get('wall_seconds',''),host_cpu_seconds=host.get('user_cpu_seconds',0)+host.get('system_cpu_seconds',0) if host else '',peak_rss_kib=host.get('peak_rss_kib',''),validation=rec.get('validation',{}).get('status','NOT_COMPLETED'))
 for stage in ['dispatch','compute','combine']:row[stage+'_span_ms']=t.get(stage+'_span_ps',0)/1e9 if t else ''
 row['max_npu_compute_ms']=max((x['end_ps']-x['start_ps'] for x in s.get('compute_intervals',[])),default=0)/1e9 if s else ''
 tl=s.get('timeline',{});row['planning_ms']=(tl.get('planning_end',0)-tl.get('layer_start',0))/1e9 if tl else '';row['reroute_ms']=(tl.get('reroute_end',0)-tl.get('planning_end',0))/1e9 if tl else ''
 row['planner_host_wall_seconds']=rec.get('preparation_summary',{}).get('planner_time',{}).get('wall_seconds','')
 row['planner_host_cpu_seconds']=rec.get('preparation_summary',{}).get('planner_time',{}).get('cpu_seconds','')
 rows.append(row)
 for stage,key in [('Preparation','preparation_host'),('Preflight','preflight_host'),('Simulator','simulator_host'),('Postflight','postflight_host')]:
  x=rec.get(key)
  if x:resources.append(dict(layer=layer,strategy=strategy,stage=stage,status=x['status'],guard=x['guard'],wall_seconds=x['wall_seconds'],cpu_seconds=x['user_cpu_seconds']+x['system_cpu_seconds'],peak_rss_kib=x['peak_rss_kib'],sampled_peak_tree_rss_bytes=x['sampled_peak_tree_rss_bytes'],limits=x['limits']))
 if s:proofs.append(dict(layer=layer,strategy=strategy,routing_sha256=rec['routing_sha256'],validation=rec['validation'],metrics=rec['metrics'],timeline=tl,stage_spans=t,compute_intervals=s['compute_intervals'],per_npu_load=rec['npu_load'],verified_bytes=s['verified_bytes'],remote_bytes=s['remote_bytes'],local_bytes=s['local_bytes'],combine_fnv1a64=s['combine_fnv1a64'],executed_graph_fnv1a64=s['executed_graph_fnv1a64'],sender_completions=s['sender_completions'],capacity=rec['capacity']))
with (a.out/'performance.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(a.out/'resources.json').write_text(json.dumps(resources,indent=2)+'\n');(a.out/'verification-proofs.json').write_text(json.dumps(proofs,indent=2)+'\n');(a.out/'status.json').write_text((a.private/'status.json').read_text())
print('Exported aggregate rows',len(rows),'completed',len(proofs))
