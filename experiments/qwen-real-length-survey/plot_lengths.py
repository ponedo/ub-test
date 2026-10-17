"""Plot only public aggregate tables; never reads raw routing/token CSVs."""
import csv,statistics,gzip
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
with (P.parent.parent/'docs/qwen-real-length-survey/actual-sample-lengths.csv').open() as f: samples=list(csv.DictReader(f))
labels=['Chinese-SimpleQA 206','LiveCodeBench 104','AIME 28','MMLU medicine 1202','MMLU-ZH medicine 1202','MMLU history 5874','MMLU-ZH history 5877','MMLU law 10876']
fig,ax=plt.subplots(figsize=(10,5.6)); values=[int(r['tokens_per_layer']) for r in samples]
ax.barh(labels,values,color='#286eaa');ax.invert_yaxis();ax.bar_label(ax.containers[0],padding=4)
ax.set_xlim(0,max(values)*1.15);ax.set_xlabel('First-record rows per serialized layer (documented prefill convention)')
ax.set_title('Eight real request files: longest single request N=924',loc='left',fontweight='bold')
fig.text(.02,.015,'Total N=4,275 permits a same-layer offline N=4,096 prefix; this is not a single prompt or joint model execution.',fontsize=9)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'results/observed-request-lengths.png',dpi=170);plt.close(fig)
stats=P/'results/layer-statistics.csv.gz'
with (gzip.open(stats,'rt') if stats.exists() else stats.with_suffix('').open()) as f: rows=list(csv.DictReader(f))
ns=[256,512,1024,2048,4096];fig,axes=plt.subplots(1,2,figsize=(11,4.8))
for ax,metric,title in zip(axes,['gini','cv'],['Expert-load Gini','Expert-load coefficient of variation']):
    groups=[[float(r[metric]) for r in rows if r['selection']==f'batch_prefix_{n}' and r['dataset']=='real'] for n in ns]
    controls=[[float(r[metric]) for r in rows if r['selection']==f'batch_prefix_{n}' and r['dataset']=='zipf'] for n in ns]
    assert all(len(g)==94 for g in groups+controls)
    med=[statistics.median(g) for g in groups]
    ax.fill_between(ns,[min(g) for g in groups],[max(g) for g in groups],color='#286eaa',alpha=.16,label='Real: layer minimum–maximum')
    ax.plot(ns,med,'o-',color='#286eaa',label='Real: median over 94 layers')
    ax.plot(ns,[g[0] for g in controls],'s--',color='#b65c1c',label='Matched-N Zipf control')
    ax.set_xscale('log',base=2);ax.set_xticks(ns,ns);ax.set_xlabel('Same-layer offline batch prefix N');ax.set_title(title);ax.grid(axis='y',alpha=.2)
axes[0].legend(fontsize=8,loc='best');fig.suptitle('Aggregate routing loads across actual request prefixes',fontweight='bold')
fig.text(.02,.015,'Layer ranges are descriptive, not confidence intervals. One seeded control is reused across layers; no performance claim.',fontsize=9)
fig.tight_layout(rect=(0,.05,1,.94));fig.savefig(P/'results/offline-prefix-loads.png',dpi=170);plt.close(fig)
# Complete-request workload comparison across all serialized layers.
matrix=[]
for i in range(len(samples)):
    selected=sorted((r for r in rows if r['selection']==f'request_{i:04d}' and r['dataset']=='real'),key=lambda r:int(r['layer']))
    assert [int(r['layer']) for r in selected]==list(range(94))
    matrix.append([float(r['gini']) for r in selected])
fig,ax=plt.subplots(figsize=(12,5.5))
im=ax.imshow(matrix,aspect='auto',cmap='viridis',vmin=0,vmax=1,interpolation='nearest')
ax.set_yticks(range(8),[f'{label}  (N={n})' for label,n in zip(labels,values)])
ax.set_xticks([0,15,30,45,60,75,93]);ax.set_xlabel('Serialized layer key (original model-layer identity unverified)')
ax.set_title('Complete real requests: expert-load Gini across 94 layers',loc='left',fontweight='bold')
fig.colorbar(im,ax=ax,label='Gini (0 = equal loads; higher = more concentrated)')
fig.text(.02,.015,'Each row uses its actual N. Differences mix workload and sample length; these are selected examples, not population estimates.',fontsize=9)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'results/request-layer-gini.png',dpi=170);plt.close(fig)
