#!/usr/bin/env python3
"""Produce aggregate CSV/figures only from measured completed executions."""
import argparse,csv,json,os,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
h=Path(__file__).resolve().parent
old=json.loads((h.parent/'ep64-token-scaling/data/runs.json').read_text());new=[]
for raw in a.raw:
 if (raw/'runs.json').exists():new+=json.loads((raw/'runs.json').read_text())
rows=[]
for model,records in [('H64/I128',old),('Qwen3-H2048/I768',new)]:
 bases={r['tokens']:r['summary']['layer_latency_ps'] for r in records if r.get('status')=='PASS' and r['strategy']=='no-balancing'}
 for r in records:
  row=dict(model=model,tokens=r['tokens'],assignments=r['assignments'],strategy=r['strategy'],status=r.get('status','INCOMPLETE'),routing_sha256=r['routing_sha256'],gemm_flops_per_assignment=9437184 if model.startswith('Qwen') else 49152,total_gemm_flops=r['assignments']*(9437184 if model.startswith('Qwen') else 49152),payload_bytes_per_assignment_per_direction=4096 if model.startswith('Qwen') else 128)
  if r.get('status')=='PASS':
   s=r['summary'];t=s['timeline'];sp=r['event_spans'];host=r['simulator_host'];intervals=s['compute_intervals']
   row.update(layer_latency_ms=s['layer_latency_ps']/1e9,speedup=bases[r['tokens']]/s['layer_latency_ps'],planning_ms=(t['planning_end']-t['layer_start'])/1e9,reroute_ms=(t['reroute_end']-t['planning_end'])/1e9,weight_distribution_ms=s['weight_target_duration_ps']/1e9,dispatch_span_ms=sp['dispatch_span_ps']/1e9,compute_span_ms=sp['compute_span_ps']/1e9,compute_max_npu_duration_ms=max((x['end_ps']-x['start_ps'] for x in intervals),default=0)/1e9,combine_span_ms=sp['combine_span_ps']/1e9,max_npu_load=s['max_npu_load'],replicas=s['replicas'],weight_bytes=s['weight_bytes'],logical_transfer_tasks=r['metrics']['tasks'],simulator_events=r['metrics']['simulator_events'],jettys=r['metrics']['jettys'],sender_completions=r['metrics']['sender_completions'],remote_wqes=s['remote_WQEs'],remote_tas=s['target_segments'],weight_wqes=s['weight_WQEs'],weight_tas=s['weight_TAs'],host_wall_s=host['wall_seconds'],host_cpu_s=host['user_cpu_seconds']+host['system_cpu_seconds'],planner_host_wall_s=r['planner_cpu_wall_seconds'],preparation_host_wall_s=r['preparation_host'].get('wall_seconds'),independent_preflight_wall_s=r.get('preflight_host',{}).get('wall_seconds'),independent_postflight_wall_s=r['verifier_host']['wall_seconds'],peak_rss_kib=host['peak_rss_kib'],validation='PASS')
  else:
   row['failure_reason']=r.get('failure_reason','not completed')
   resource=Path(r.get('failure_resource',''))
   candidates=[resource]+[root/f"tokens-{r['tokens']}"/r['strategy']/'simulator-host/resource.json' for root in a.raw]
   found=next((p for p in candidates if p.is_file()),None)
   if found:
    failed=json.loads(found.read_text());row.update(host_wall_s=failed['wall_seconds'],peak_rss_kib=failed['peak_rss_kib'],host_cpu_s=failed['user_cpu_seconds']+failed['system_cpu_seconds'],validation='INCOMPLETE')
  rows.append(row)
coverage=[]
for tokens in [256,1024,2048,4096,6250,8192,12500]:
 for strategy in ['no-balancing','direct','chunk-streaming']:
  r=next((x for x in new if x['tokens']==tokens and x['strategy']==strategy),None)
  coverage.append(dict(tokens=tokens,strategy=strategy,status=r.get('status','INCOMPLETE') if r else 'NOT_RUN',reason=(r.get('failure_reason','') if r else 'not reached under sequential resource gate')))
with (a.out/'qwen-scan-coverage.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['tokens','strategy','status','reason']);w.writeheader();w.writerows(coverage)
keys=list(dict.fromkeys(k for r in rows for k in r))
with (a.out/'model-size-comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
# Exact routing equality for all comparable measured points.
index={(r['tokens'],r['strategy']):r for r in old}
checks=[]
for r in new:
 ref=index[(r['tokens'],r['strategy'])];assert r['routing_sha256']==ref['routing_sha256']
 if r.get('status')=='PASS':assert r['plan_load']==ref['plan_load'];assert r['summary']['replicas']==ref['summary']['replicas']
 checks.append(dict(tokens=r['tokens'],strategy=r['strategy'],routing='PASS',aggregate_load_replica_count='PASS' if r.get('status')=='PASS' else 'not executed'))
(a.out/'cross-model-controls.json').write_text(json.dumps(checks,indent=2)+'\n')
os.environ.setdefault('MPLCONFIGDIR',tempfile.mkdtemp(prefix='qwen-matplotlib-'))
os.environ.setdefault('XDG_CACHE_HOME',tempfile.mkdtemp(prefix='qwen-font-cache-'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
colors={'no-balancing':'#333333','direct':'#0072B2','chunk-streaming':'#D55E00'}
for field,title,ylabel in [('speedup','Measured layer speedup','No Balancing / strategy'),('layer_latency_ms','Measured MoE layer latency','Milliseconds'),('weight_distribution_ms','Measured weight distribution duration','Milliseconds'),('compute_max_npu_duration_ms','Maximum per-NPU compute duration','Milliseconds')]:
 fig,ax=plt.subplots(figsize=(8,4.5))
 for model in ['H64/I128','Qwen3-H2048/I768']:
  for strategy,color in colors.items():
   selected=sorted([r for r in rows if r['model']==model and r['strategy']==strategy and r['status']=='PASS'],key=lambda r:r['tokens'])
   if selected:ax.plot([r['tokens'] for r in selected],[r[field] for r in selected],marker='o' if model.startswith('Qwen') else '.',linestyle='-' if model.startswith('Qwen') else '--',color=color,label=model+' '+strategy)
 ax.set_xscale('log',base=2);ax.set_xlabel('Total EP-group prefill tokens');ax.set_ylabel(ylabel);ax.set_title(title+'\nSynthetic Zipf routing; assumed 500 effective GFLOP/s');ax.grid(alpha=.25);ax.legend(fontsize=7);fig.tight_layout();fig.savefig(a.out/(field+'.png'),dpi=150);plt.close(fig)
print('Measured rows',sum(r['status']=='PASS' for r in rows),'incomplete rows',sum(r['status']!='PASS' for r in rows))
