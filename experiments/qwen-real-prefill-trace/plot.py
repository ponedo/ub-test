#!/usr/bin/env python3
"""Draw aggregate load distributions only, never per-token routes."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent/'results'
rows=list(csv.DictReader((root/'layer-statistics.csv').open()))
real=[r for r in rows if r['dataset']=='real'];control=next(r for r in rows if r['dataset']=='zipf')
fig,axes=plt.subplots(2,2,figsize=(11,7))
for ax,key,label in zip(axes.flat,['max_mean','jain','gini','hot8_share'],['Max / mean load','Jain fairness','Gini coefficient','Top-8 expert assignment share']):
    ax.plot([int(r['layer']) for r in real],[float(r[key]) for r in real],label='Trace record 0 (N=22)',linewidth=1.2)
    ax.axhline(float(control[key]),color='tab:orange',linestyle='--',label='Same Zipf(1.1) control, N=22')
    ax.set_xlabel('Serialized layer key');ax.set_ylabel(label);ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8)
fig.suptitle('Single Qwen3-235B-FP8 request: aggregate expert-load comparison\nRecord 0 is prefill by dataset convention; no routing-equivalence or performance claim',fontsize=11)
fig.tight_layout();fig.savefig(root/'layer-load-comparison.png',dpi=140);plt.close(fig)
counts=list(csv.DictReader((root/'expert-counts.csv').open()))
fig,ax=plt.subplots(figsize=(10,4))
for label in ['real','zipf']:
    values=[int(r['count']) for r in counts if r['dataset']==label and r['layer']=='0']
    ax.plot(range(128),values,label=label)
ax.set(xlabel='Expert ID',ylabel='Assignments',title='Serialized layer 0: 176 assignments over 128 experts (N=22, k=8)')
ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(root/'layer-0-expert-counts.png',dpi=140);plt.close(fig)
