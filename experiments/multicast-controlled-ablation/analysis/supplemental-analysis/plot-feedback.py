#!/usr/bin/env python3
"""Plot completed read-only feedback aggregates. No simulator imports or launches."""
import argparse,csv,hashlib,json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/ablation-feedback-matplotlib')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/ablation-feedback-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def main():
 p=argparse.ArgumentParser();p.add_argument('analysis',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 d=json.loads((a.analysis/'summary.json').read_text());assert d['status']=='PASS';assert not a.out.exists();a.out.mkdir(parents=True)
 with (a.analysis/'port3-summary.csv').open() as f:rows=list(csv.DictReader(f))
 def casekey(r):
  c=r['case_id'];return (512 if c.startswith('baseline-') or c in ['chunk-streaming','multicast-v2'] else int(c.split('-')[1]),'multicast-v2' in c)
 rows.sort(key=casekey);ys=np.arange(len(rows));labels=[]
 for r in rows:
  w,mc=casekey(r);labels.append(f"{w} · {'MC' if mc else 'Chunk'}"+(' *' if r['source3_is_terminal']=='True' else ''))
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 fig,(ax,aq)=plt.subplots(1,2,figsize=(12,4.4 if len(rows)==2 else 5.6),gridspec_kw={'width_ratios':[1.25,1]},sharey=True)
 bottom=np.zeros(len(rows))
 for key,label,color in [('return_tx_busy_ps','TX busy','#4877b4'),('return_allocator_excluding_tx_ps','Allocation, excluding TX','#8053a0'),('return_uncovered_idle_ps','Uncovered idle','#d2d6db')]:
  values=np.array([float(r[key])/1e6 for r in rows]);ax.barh(ys,values,left=bottom,color=color,label=label,height=.59);bottom+=values
 for y,t,r in zip(ys,bottom,rows):ax.text(t+max(bottom)*.012,y,f'{t:.3f}',va='center',fontsize=9)
 ax.set_yticks(ys,labels);ax.invert_yaxis();ax.set_xlim(0,max(bottom)*1.18);ax.set_xlabel('Weight-phase elapsed partition (µs)');ax.set_title('Exact resource accounting at return port 3',loc='left',fontsize=11,pad=13);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
 mean=[float(r['return_ack_response_voq_mean_ps'])/1e6 for r in rows];maximum=[float(r['return_ack_response_voq_max_ps'])/1e6 for r in rows]
 aq.hlines(ys,mean,maximum,color='#aeb7bf',lw=2,zorder=1);aq.scatter(mean,ys,marker='o',color='#bb5e2c',label='Mean',s=42,zorder=2);aq.scatter(maximum,ys,marker='s',facecolors='white',edgecolors='#34576b',label='Maximum',s=42,zorder=2)
 for y,m,x in zip(ys,mean,maximum):
  aq.text(x if x>max(maximum)*.5 else max(maximum)*.012,y+.19,f'{m:.3f} mean / {x:.3f} max',ha='right' if x>max(maximum)*.5 else 'left',va='center',fontsize=8,color='#555')
 aq.set_xlim(0,max(maximum)*1.14);aq.set_xlabel('ACK-response VOQ residence (µs)');aq.set_title('Queueing cohort: not additive elapsed time',loc='left',fontsize=11,pad=13);aq.grid(axis='x',alpha=.2);aq.set_axisbelow(True)
 formal='formal six-case' in d['scope'];fig.suptitle('Shared feedback return path: fixed switch 64 / egress 3',x=.07,y=.98,ha='left',fontsize=15,fontweight='bold')
 fig.text(.07,.912,'Six fresh controlled cells; changed windows are ablation-only.' if formal else 'Accepted historical 512 baselines only. This is not a new B result.',fontsize=10,color='#555')
 ax.legend(loc='upper left',bbox_to_anchor=(0,-.19),ncol=2,frameon=False,fontsize=9);aq.legend(loc='upper left',bbox_to_anchor=(0,-.19),ncol=2,frameon=False,fontsize=9)
 fig.text(.07,.027,'* Source 3 is an actual terminal source in that cell. All rows still use the same fixed physical port.\nPartition components are disjoint; VOQ residence sums overlap. Model: one logical port, unchanged 5 ns allocator.',fontsize=9,color='#555',va='bottom')
 fig.subplots_adjust(left=.14,right=.98,bottom=.32,top=.80,wspace=.24)
 for ext in ['png','svg']:fig.savefig(a.out/f'feedback-return-port.{ext}',dpi=180,facecolor='white')
 plt.close(fig)
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.out.iterdir() if p.is_file()}
 (a.out/'manifest.json').write_text(json.dumps({'scope':d['scope'],'input_sha256':{p:hashlib.sha256((a.analysis/p).read_bytes()).hexdigest() for p in ['summary.json','port3-summary.csv']},'files':files},indent=2)+'\n')
 print(json.dumps({'status':'PASS','rows':len(rows),'out':str(a.out)}))
if __name__=='__main__':main()
