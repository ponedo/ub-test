#!/usr/bin/env python3
"""Plot the single fixed experiment; not a token-scaling or fanout intervention curve."""
import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args();r=a.results
read=lambda name:list(csv.DictReader((r/name).open()))
rows=read('performance.csv');names=['No Balancing','Direct','Chunk Streaming','Multicast v2'];colors=['#929ba6','#4e79a7','#f28e2b','#238b67']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
for ax,field,title in zip(axes,['weight_ns','layer_ns'],['Weight distribution (receiver-ready)','MoE layer latency']):
 values=[float(x[field])/1e6 for x in rows];ax.bar(names,values,color=colors,width=.65);ax.set_ylabel('Simulated time (ms)');ax.set_title(title);ax.tick_params(axis='x',rotation=18);ax.margins(y=.15)
 for i,v in enumerate(values):ax.text(i,v,f'{v:.3f}',ha='center',va='bottom',fontsize=9)
fig.suptitle('Qwen3-235B · L37 · 2048 prefill tokens · EP64',fontsize=13)
fig.savefig(r/'latency.svg');fig.savefig(r/'latency.png',dpi=160);plt.close(fig)
experts=read('expert-ready.csv');fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
for mode,label,color in zip(['direct','chunk-streaming','multicast-v2'],names[1:],colors[1:]):
 data=sorted([x for x in experts if x['strategy']==mode],key=lambda x:int(x['expert']));ax.plot([int(x['expert']) for x in data],[float(x['distribution_duration_ns'])/1e6 for x in data],marker='o',markersize=4,label=label,color=color)
ax.set(xlabel='Expert ID (categorical ordered index)',ylabel='Weight-ready time since distribution start (ms)',title='Per-expert completion; connecting lines are visual guides');ax.legend();fig.savefig(r/'expert-ready.svg');plt.close(fig)
comm=read('communication.csv');fig,ax=plt.subplots(figsize=(8,4.5),layout='constrained');payload=[int(x['source_weight_payload_bytes'])/1e6 for x in comm];header=[int(x['source_weight_header_bytes'])/1e6 for x in comm]
ax.bar(names,payload,label='Payload',color='#4e79a7');ax.bar(names,header,bottom=payload,label='Headers',color='#e5a13a');ax.set(ylabel='All-host weight transmission (decimal MB)',title='Actual source-side weight data wire bytes');ax.legend();fig.savefig(r/'wire-bytes.svg');plt.close(fig)
