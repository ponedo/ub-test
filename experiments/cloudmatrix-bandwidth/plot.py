#!/usr/bin/env python3
"""Render only collected, validated evidence; stages overlap and are never stacked."""
import argparse
import csv
import json
import os
if not __debug__ or os.environ.get("PYTHONOPTIMIZE"):
    raise RuntimeError("Assertions must remain enabled")
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args();r=a.results
assert json.loads((r/'summary.json').read_text())['status']=='PASS'
with (r/'performance.csv').open() as f: data=list(csv.DictReader(f))
names=['no-balancing','direct','chunk-streaming','multicast-v2']; labels=['No Balancing','Direct','Chunk Streaming','Multicast v2']
colors=['#708090','#4477AA','#EEAA33','#228866']
plt.rcParams.update({'font.size':10,'figure.dpi':150,'axes.spines.top':False,'axes.spines.right':False})
def save(fig,name):
    fig.savefig(r/(name+'.png'),bbox_inches='tight');fig.savefig(r/(name+'.svg'),bbox_inches='tight');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
for ax,rate in zip(axes,[100,3136]):
    rr=[next(x for x in data if int(x['link_gbps'])==rate and x['strategy']==mode) for mode in names]
    vals=[float(x['layer_ns'])/1e6 for x in rr]
    ax.bar(range(4),vals,color=colors);ax.set_xticks(range(4),labels,rotation=18,ha='right')
    ax.set_ylabel('Simulated layer latency (ms)');ax.set_title(f'{rate} Gbps logical aggregate\n'+('accepted baseline (reused)' if rate==100 else 'new measured simulation'))
    ax.set_ylim(0,max(vals)*1.2)
    for i,v in enumerate(vals):ax.text(i,v,f'{v:.4f}',ha='center',va='bottom')
fig.suptitle('L37 / 2048 tokens / EP64: separate panel scales, not hardware measurements')
save(fig,'layer-comparison')
fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
fields=['weight_ns','dispatch_span_ns','compute_span_ns','combine_span_ns']
for ax,rate in zip(axes,[100,3136]):
    rr=[next(x for x in data if int(x['link_gbps'])==rate and x['strategy']==mode) for mode in names]
    for k,key in enumerate(fields):
        ax.bar([i+(k-1.5)*.19 for i in range(4)],[float(x[key])/1e6 for x in rr],width=.18,label=key.replace('_ns','').replace('_',' '))
    ax.set_xticks(range(4),labels,rotation=18,ha='right');ax.set_ylabel('Simulated elapsed span (ms)');ax.set_title(f'{rate} Gbps');ax.legend(fontsize=8)
fig.suptitle('Overlapping stage spans: bars must NOT be summed')
save(fig,'stage-spans')
fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
for k,rate in enumerate([100,3136]):
    rr=[next(x for x in data if int(x['link_gbps'])==rate and x['strategy']==mode) for mode in names]
    ax.bar([i+(k-.5)*.35 for i in range(4)],[float(x['speedup_vs_nobal']) for x in rr],width=.33,label=f'{rate} Gbps')
ax.axhline(1,color='black',linewidth=.8);ax.set_xticks(range(4),labels);ax.set_ylabel('No Balancing layer time / strategy layer time');ax.set_title('Layer speedup: below 1 means slower than No Balancing');ax.legend()
save(fig,'speedup')

# Pairwise Multicast comparisons must visibly retain ratios below one.
with (r/'comparison.csv').open() as handle: comparison=list(csv.DictReader(handle))
fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
for ax,field,title in zip(axes,['multicast_weight_speedup','multicast_layer_speedup'],['Weight interval','Whole layer']):
    for k,rate in enumerate([100,3136]):
        values=[float(next(x for x in comparison if int(x['link_gbps'])==rate and x['reference_strategy']==mode)[field]) for mode in ['direct','chunk-streaming']]
        positions=[i+(k-.5)*.35 for i in range(2)]
        ax.bar(positions,values,width=.33,label=f'{rate} Gbps')
        for pos,value in zip(positions,values):
            ax.text(pos,value,f'{value:.4f}x',ha='center',va='bottom',color='#AA2222' if value<1 else 'black',fontweight='bold' if value<1 else 'normal')
    ax.axhline(1,color='black',linestyle='--',linewidth=1)
    ax.set_xticks(range(2),['vs Direct','vs Chunk Streaming']);ax.set_ylim(0,max(float(x[field]) for x in comparison)*1.2)
    ax.set_ylabel('Reference time / Multicast time');ax.set_title(title);ax.legend()
fig.suptitle('Multicast speedup: below 1 means SLOWER (no clipped axis)')
save(fig,'multicast-speedup')
