#!/usr/bin/env python3
"""Plot only actually completed cases; missing entries remain blank."""
import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args();rows=list(csv.DictReader((a.results/'performance.csv').open()));strategies=['no-balancing','direct','chunk-streaming','multicast'];colors=['#666666','#3377aa','#df9431','#2b996e']
for field,label,name in [('layer_latency_ms','Simulated MoE layer latency (ms)','layer-latency'),('weight_duration_ms','Weight distribution duration (ms)','weight-duration'),('speedup_vs_no_balancing','Speedup vs No Balancing','speedup'),('all_npu_weight_request_wire_bytes','All sending-NPU weight wire bytes (MiB)','source-weight-bytes'),('all_network_wire_bytes','All network transmitted bytes (MiB)','network-bytes')]:
 fig,ax=plt.subplots(figsize=(8,4.5));missing=[]
 for i,s in enumerate(strategies):
  xs=[];ys=[]
  for j,l in enumerate([0,37,52]):
   r=next((r for r in rows if int(r['layer'])==l and r['strategy']==s),None)
   if r is None:missing.append(f'L{l}/{s}');continue
   xs.append(j+(i-1.5)*.19);v=float(r[field]);ys.append(v/1024**2 if field.endswith('bytes') else v)
  if xs:ax.bar(xs,ys,width=.18,label=s,color=colors[i])
 ax.set_xticks([0,1,2],['L0','L37','L52']);ax.set_ylabel(label);ax.set_title('Real FP8 router trace, ideal FP8 weights, N2048 / EP64');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
 fig.text(.01,.01,'Parametric 500 GFLOP/s model; offline batch. '+(f'{len(missing)} cases not completed; omitted.' if missing else 'All displayed cases verified.'),fontsize=8);fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(a.results/(name+'.png'),dpi=160);plt.close(fig)
