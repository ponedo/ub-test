#!/usr/bin/env python3
"""Plot verified aggregate simulated time, not host execution time or causal shares."""
import argparse,json,os,tempfile
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',tempfile.mkdtemp(prefix='reversal-mpl-'))
os.environ.setdefault('XDG_CACHE_HOME',tempfile.mkdtemp(prefix='reversal-cache-'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('analysis');p.add_argument('out');a=p.parse_args()
j=json.loads(Path(a.analysis).read_text());assert j['status']=='PASS' and j['accounting_available']
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':170})
ss=['chunk-streaming','multicast-v2'];labels=['Chunk: terminal source 36 / 50','Multicast: terminal source 3']
fig,ax=plt.subplots(figsize=(10,4.8));colors=['#3178a8','#d89b37','#b95555','#777777'];keys=['tx_busy_union_ps','allocator_pending_excluding_tx_ps','uncovered_idle_ps'];names=['TX busy union','Allocation pending, excluding TX','Uncovered idle','Final dequeue → Weight Ready']
for i,s in enumerate(ss):
 c=j['cases'][s];t=c['critical_transfers'][0];r=t['prefix_accounting_candidates'][0];vs=[r[k]/1e6 for k in keys]+[t['post_dequeue_to_ready_ps']/1e6];assert abs(sum(vs)-c['weight_span_ps']/1e6)<1e-8
 left=0
 for k,v in enumerate(vs):
  ax.barh(i,v,left=left,color=colors[k],label=names[k] if i==0 else None,height=.5)
  if v>30:ax.text(left+v/2,i,f'{v:.3f}',va='center',ha='center',color='white',fontsize=10)
  left+=v
 ax.text(left+7,i,f'{left:.6f} µs',va='center')
ax.set_yticks(range(2),labels);ax.invert_yaxis();ax.set_xlim(0,865);ax.set_xlabel('Simulated elapsed time (µs)');ax.set_title('164.289264 µs gap: exact elapsed-resource accounting',loc='left',weight='bold');ax.legend(loc='upper center',bbox_to_anchor=(.45,-.2),ncol=2,frameon=False,fontsize=9)
fig.subplots_adjust(left=.28,right=.98,top=.83,bottom=.31);fig.text(.02,.04,'Accumulated durations, NOT chronological blocks or causal percentages.\nDifferent terminal sources; same-port controls are reported separately. Final suffix: 53.591 ns / 53.127 ns.',fontsize=9,color='#444444');fig.savefig(out/'critical-source-accounting.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(9,4.3)); ylabels=[]
for i,s in enumerate(ss):
 c=j['cases'][s];t=c['critical_transfers'][0];start=c['weights_start_ps'];last=(t['last_native_send_ps']-start)/1e6;ready=(t['receiver_ready_ps']-start)/1e6;sender=(t['sender_complete_ps']-start)/1e6
 ax.plot([0,ready],[i,i],lw=8,color=colors[i],solid_capstyle='butt');ax.scatter([last],[i],s=55,marker='|',color='black',zorder=5);ax.scatter([sender],[i],s=35,facecolor='white',edgecolor=colors[i],zorder=5);ax.plot([ready,sender],[i,i],ls=':',color=colors[i]);ax.text(ready,i-.18,f'Weight Ready {ready:.3f} µs',ha='right',fontsize=9);ax.text(sender,i+.24,f'Sender completion {sender:.3f} µs',ha='right',fontsize=9)
ax.set_yticks([0,1],['Chunk (task 69657)','Multicast (task 32814)']);ax.invert_yaxis();ax.set_ylim(1.6,-.5);ax.set_xlim(0,830);ax.set_xlabel('Simulated time from weight-phase start (µs)');ax.set_title('Receiver Weight Ready is not final sender cleanup',loc='left',weight='bold');ax.grid(axis='x',alpha=.2);fig.subplots_adjust(bottom=.24,left=.23,right=.98,top=.85);fig.text(.02,.04,'Final packet dequeue lies ~53 ns before Weight Ready. Earlier TAACKs can still gate admission during transmission.',fontsize=9);fig.savefig(out/'weight-timeline.png');plt.close(fig)
