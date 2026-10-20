import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args();r=a.results
rows=list(csv.DictReader((r/'performance.csv').open()));modes=['no-balancing','direct','chunk-streaming','multicast-v2'];labels=['No Balancing','Direct','Chunk','Multicast v2']
plt.rcParams.update({'font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
for ax,model in zip(axes,['legacy','roofline']):
 selected=[next(x for x in rows if x['model']==model and x['strategy']==mode) for mode in modes];values=[float(x['layer_ns'])/1e6 for x in selected];bars=ax.bar(labels,values,color=['#949ca5','#4e79a7','#f28e2b','#238b67']);ax.bar_label(bars,fmt='%.3f',padding=3);ax.set_ylim(0,max(values)*1.18);ax.set_ylabel('Simulated layer latency (ms)');ax.set_title('Legacy: 0.5 effective TFLOPS' if model=='legacy' else 'Roofline: 100 TFLOPS + 2692 GB/s');ax.tick_params(axis='x',labelrotation=16)
fig.suptitle('Qwen3-235B · L37 · 2048 prefill tokens · EP64');fig.savefig(r/'layer-comparison.png',dpi=160);fig.savefig(r/'layer-comparison.svg');plt.close(fig)
unit=list(csv.DictReader((r/'stage-a/unit/token-latency.csv').open()));fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
for field,label,style in [('compute_ps','Compute','--'),('memory_ps','HBM','--'),('roofline_ps','max(Compute, HBM)','-')]:ax.plot([int(x['tokens']) for x in unit],[int(x[field])/1e6 for x in unit],style,marker='o',label=label)
ax.set_xlabel('Tokens per physical Expert');ax.set_ylabel('Modeled Expert latency (µs)');ax.set_title('Explicit unfused-GEMM activation traffic assumption');ax.legend();fig.savefig(r/'token-latency.png',dpi=160);fig.savefig(r/'token-latency.svg');plt.close(fig)
