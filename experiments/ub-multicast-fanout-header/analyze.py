#!/usr/bin/env python3
import argparse,csv,os,tempfile
from pathlib import Path
cache=tempfile.TemporaryDirectory(prefix="ub-fanout-plots-")
os.environ.setdefault("MPLCONFIGDIR",cache.name)
os.environ.setdefault("XDG_CACHE_HOME",cache.name)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args()
with (a.results/'performance.csv').open() as f:rows=[r for r in csv.DictReader(f) if r['block']!='small']
modes=['direct','chunk','full','compact-oracle','ideal-oracle'];labels=['Direct','Chunk (original policy)','Multicast full','Multicast compact Oracle','Multicast ideal Oracle'];colors=['#666666','#377eb8','#e41a1c','#4daf4a','#984ea3']
plots=[('weight-duration','weight_duration_ms','All-target Weight Ready duration (ms)',1),('speedup-vs-chunk','speedup_vs_chunk','Weight-distribution speedup vs Chunk',1),('source-wire-bytes','source_data_wire_bytes','Main-source weight wire bytes (MiB)',1/2**20),('header-overhead','source_header_bytes','Main-source charged weight header bytes (MiB)',1/2**20)]
for name,metric,ylabel,scale in plots:
 fig,ax=plt.subplots(figsize=(8,4.7))
 for mode,label,color in zip(modes,labels,colors):
  part=sorted((r for r in rows if r['mode']==mode and r[metric]!=''),key=lambda r:int(r['fanout']))
  if part:ax.plot([int(r['fanout']) for r in part],[float(r[metric])*scale for r in part],marker='o',label=label,color=color)
 ax.set_xticks([1,2,3,4,8]);ax.set_xlabel('Replica fanout (excluding main)');ax.set_ylabel(ylabel);ax.grid(alpha=.25)
 if 'speedup' in name:ax.axhline(1,color='black',linestyle=':',linewidth=1)
 ax.legend(fontsize=8);ax.set_title('18 MiB, EP64, single expert / switch, 100 Gbit/s')
 fig.text(.01,.01,'Measured ns-3 events; Oracle modes are header-cost hypotheses. Source: performance.csv',fontsize=8)
 fig.tight_layout(rect=(0,.035,1,1));fig.savefig(a.results/(name+'.png'),dpi=170);plt.close(fig)
