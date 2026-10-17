#!/usr/bin/env python3
"""Collect real event measurements. Phase spans overlap; never add them as latency."""
import argparse,csv,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
runs=json.loads((a.raw/'runs.json').read_text());rows=[];status=json.loads((a.raw/'status.json').read_text())
def jain(v):return sum(v)**2/(len(v)*sum(x*x for x in v)) if any(v) else 1.0
for r in runs:
 h=r.get('simulator_host',{})
 if not h and r.get('failure_resource') and 'simulator-host' in r['failure_resource']:
  assert r['failure_resource']==status['failure_resource']
  h=status['failure_measurement']
 v=r.get('verifier_host',{});s=r.get('summary',{});m=r.get('metrics',{});t=s.get('timeline',{});e=r.get('event_spans',{})
 row=dict(tokens=r['tokens'],assignments=r['assignments'],strategy=r['strategy'],status=r.get('status','INCOMPLETE'),failure_reason=r.get('failure_reason',''),routing_sha256=r['routing_sha256'],layer_latency_us=s.get('layer_latency_ps',0)/1e6 if s else None,speedup=r.get('speedup'),planning_us=(t['planning_end']-t['layer_start'])/1e6 if t else None,reroute_compute_us=(t['reroute_end']-t['planning_end'])/1e6 if t else None,weights_end_from_layer_us=(t['weights_end']-t['layer_start'])/1e6 if t else None,weight_distribution_span_us=(t['weights_end']-t['planning_end'])/1e6 if t else None,dispatch_gate_from_layer_us=(t['dispatch_gate']-t['layer_start'])/1e6 if t else None,dispatch_span_us=e.get('dispatch_span_ps',0)/1e6 if e else None,compute_span_us=e.get('compute_span_ps',0)/1e6 if e else None,combine_span_us=e.get('combine_span_ps',0)/1e6 if e else None,max_rank_compute_duration_us=max((x['end_ps']-x['start_ps'] for x in s.get('compute_intervals',[])),default=0)/1e6 if s else None,max_npu_load=s.get('max_npu_load'),npu_load_jain=jain(r['plan_load']) if 'plan_load' in r else None,expert_load_max=r['expert_load']['max'],expert_load_jain=r['expert_load']['jain'],replicas=s.get('replicas'),weight_bytes=s.get('weight_bytes'),weight_WQEs=s.get('weight_WQEs'),weight_TAs=s.get('weight_TAs'),jettys=m.get('jettys'),remote_WQEs=m.get('remote_WQEs'),TAs=m.get('TA_count'),events=m.get('simulator_events'),sender_completions=m.get('sender_completions'),planner_cpu_wall_seconds=r['planner_cpu_wall_seconds'],simulator_wall_seconds=h.get('wall_seconds'),simulator_cpu_seconds=h.get('user_cpu_seconds',0)+h.get('system_cpu_seconds',0) if h else None,simulator_peak_rss_kib=h.get('peak_rss_kib'),verifier_wall_seconds=v.get('wall_seconds'),verifier_peak_rss_kib=v.get('peak_rss_kib'))
 rows.append(row)
baseline={r['tokens']:r for r in rows if r['strategy']=='no-balancing' and r['status']=='PASS'}
for r in rows:
 if r['status']=='PASS' and r['tokens'] in baseline:r['speedup']=baseline[r['tokens']]['layer_latency_us']/r['layer_latency_us']
# Explicit requested matrix: missing arms are NOT_RUN, never zero latency.
existing={(r['tokens'],r['strategy']) for r in rows}
for tokens in [256,1024,2048,4096,6250,8192,12500]:
 for strategy in ['no-balancing','direct','chunk-streaming']:
  if (tokens,strategy) not in existing:
   row={k:None for k in rows[0]};row.update(tokens=tokens,assignments=tokens*8,strategy=strategy,status='NOT_RUN',failure_reason='scan stopped; no enlargement after resource guard')
   rows.append(row)
order={'no-balancing':0,'direct':1,'chunk-streaming':2};rows.sort(key=lambda r:(r['tokens'],order[r['strategy']]))
with (a.out/'scaling.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['status']);w.writeheader();w.writerows(rows)
(a.out/'failure-status.json').write_text(json.dumps(status,indent=2)+'\n')
(a.out/'scaling.json').write_text(json.dumps(rows,indent=2)+'\n')
# Independently verify prefix-consistent public routing CSVs.
previous=[];prefix=[]
for point in sorted(a.raw.glob('tokens-*'),key=lambda x:int(x.name.split('-')[1])):
 if not (point/'routing.csv').exists():continue
 with (point/'routing.csv').open() as f:current=list(csv.reader(f))
 assert current[:len(previous)]==previous
 prefix.append({'tokens':int(point.name.split('-')[1]),'rows':len(current)-1,'previous_prefix_equal':True});previous=current
(a.out/'routing-prefix-verification.json').write_text(json.dumps(prefix,indent=2)+'\n')
os.environ.setdefault('MPLCONFIGDIR','/tmp/ep64-scaling-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
valid=[r for r in rows if r['status']=='PASS']
for metric,label,name in [('layer_latency_us','Layer latency (us)','latency'),('speedup','No Balancing / strategy','speedup'),('simulator_wall_seconds','Host simulator wall time (s)','host-wall'),('simulator_peak_rss_kib','Peak simulator RSS (KiB)','rss'),('max_npu_load','Maximum NPU assignments','load'),('weight_distribution_span_us','Weight distribution span (us)','weight-cost'),('replicas','Replica count','replicas')]:
 fig,ax=plt.subplots(figsize=(7,4))
 for strategy in ['no-balancing','direct','chunk-streaming']:
  rs=[r for r in valid if r['strategy']==strategy and r[metric] is not None]
  ax.plot([r['tokens'] for r in rs],[r[metric] for r in rs],marker='o',label=strategy)
 if metric=='speedup':ax.axhline(1,color='gray',linestyle='--',linewidth=.8)
 ax.set(xlabel='Global EP-group Prefill tokens',ylabel=label,title='EP64, H64/I128 synthetic model, Pair Jetty');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(a.out/(name+'.png'),dpi=160);fig.savefig(a.out/(name+'.svg'));plt.close(fig)
print(json.dumps({'rows':len(rows),'passed':len(valid),'prefix_points':len(prefix)}))
