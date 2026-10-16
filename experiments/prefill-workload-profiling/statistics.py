#!/usr/bin/env python3
"""Empirical lengths + reproducible IID batch sums, not a serving scheduler."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent

def stats(x):
 q=np.quantile(x,[.5,.9,.95,.99],method='linear')
 return dict(N=len(x),mean=float(np.mean(x)),P50=float(q[0]),P90=float(q[1]),P95=float(q[2]),P99=float(q[3]),min=int(np.min(x)),max=int(np.max(x)))
def write_csv(path,rows):
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def run(args):
 out=Path(args.out);plots=out/'plots';plots.mkdir(exist_ok=True)
 lock=json.loads((ROOT/'sources.lock.json').read_text())['measurement'];reps=lock['batch_repetitions'];sizes=lock['batch_sizes'];summary=[];batches=[];stability=[]
 ledger=json.loads((out/'profile-ledger.json').read_text());measured=[r for r in ledger if r['status']=='measured']
 plt.rcParams.update({'font.size':9,'figure.dpi':120,'savefig.dpi':160})
 for item in measured:
  name=item['series'];rows=list(csv.DictReader((out/'lengths'/f'{name}.csv').open()));lengths={m:np.array([int(row[m+'_tokens']) for row in rows],dtype=np.int64) for m in ['raw','chat']}
  fig,axes=plt.subplots(1,2,figsize=(10,3.6),constrained_layout=True)
  lo=min(int(x.min()) for x in lengths.values());hi=max(int(x.max()) for x in lengths.values())
  bins=np.geomspace(max(1,lo),hi+1,40) if hi>lo else [max(0,lo-.5),hi+.5]
  for mode,x in lengths.items():
   record=dict(series=name,mode=mode,**stats(x))
   for limit in [12500,32768,40960,131072]:record[f'fraction_above_{limit}']=float(np.mean(x>limit))
   summary.append(record)
   axes[0].step(np.sort(x),np.arange(1,len(x)+1)/len(x),where='post',label=mode)
   axes[1].hist(x,bins=bins,histtype='step',label=mode)
  axes[0].set(xscale='log',xlabel='Input tokens (untruncated)',ylabel='Empirical CDF',ylim=(0,1));axes[1].set(xscale='log',xlabel='Input tokens (untruncated)',ylabel='Requests')
  for ax in axes:ax.legend();ax.grid(alpha=.2)
  fig.suptitle(name);fig.savefig(plots/(name+'-lengths.png'));plt.close(fig)
  group=[]
  for b in sizes:
   seed=(lock['batch_seed']+int(hashlib.sha256(f'{name}/{b}'.encode()).hexdigest()[:16],16))%(2**63)
   rng=np.random.default_rng(seed);sums={m:[] for m in lengths};maxs={m:[] for m in lengths}
   for start in range(0,reps,10000):
    ids=rng.integers(0,len(rows),size=(min(10000,reps-start),b))
    for mode,x in lengths.items():samples=x[ids];sums[mode].append(samples.sum(axis=1));maxs[mode].append(samples.max(axis=1))
   for mode in lengths:
    x=np.concatenate(sums[mode]);mx=np.concatenate(maxs[mode]);q=stats(x)
    record=dict(series=name,mode=mode,request_count=b,repetitions=reps,seed=seed,replacement=True,**q)
    record['expected_mean_from_lengths']=float(b*np.mean(lengths[mode]))
    record['mean_mc_standard_error']=float(np.std(x,ddof=1)/np.sqrt(reps))
    for limit in [12500,32768,65536,131072]:record[f'fraction_sum_above_diagnostic_budget_{limit}']=float(np.mean(x>limit))
    for limit in [32768,40960,131072]:record[f'fraction_any_request_above_context_{limit}']=float(np.mean(mx>limit))
    first=np.quantile(x[:reps//2],[.5,.9,.99],method='linear');second=np.quantile(x[reps//2:],[.5,.9,.99],method='linear')
    delta=np.abs(first-second)/np.maximum(1,np.maximum(first,second))
    stability.append(dict(series=name,mode=mode,request_count=b,repetitions=reps,P50_half_relative_difference=float(delta[0]),P90_half_relative_difference=float(delta[1]),P99_half_relative_difference=float(delta[2]),max_relative_difference=float(max(delta)),within_5_percent=bool(max(delta)<=.05)))
    batches.append(record);group.append(record)
  fig,axes=plt.subplots(1,2,figsize=(10,3.6),constrained_layout=True)
  for ax,mode in zip(axes,['raw','chat']):
   data=[r for r in group if r['mode']==mode]
   for metric in ['mean','P50','P90','P99']:ax.plot(sizes,[r[metric] for r in data],marker='o',markersize=3,label=metric)
   ax.set(xscale='log',yscale='log',xlabel='IID requests per synthetic batch',ylabel='Sum of input tokens',title=mode);ax.set_xticks(sizes,labels=list(map(str,sizes)));ax.legend();ax.grid(alpha=.2)
  fig.suptitle(name+' — with replacement; no scheduler');fig.savefig(plots/(name+'-batches.png'));plt.close(fig)
  print(name,'stats/batches/plots OK',flush=True)
 write_csv(out/'length-statistics.csv',summary);write_csv(out/'batch-statistics.csv',batches);write_csv(out/'batch-stability.csv',stability)
 (out/'statistics-manifest.json').write_text(json.dumps(dict(series=len(measured),length_measurements=sum(r['N'] for r in measured),batch_repetitions=reps,seed=lock['batch_seed'],bit_generator='numpy PCG64',quantile='linear',replacement=True,paired_raw_chat_sample_indices=True,diagnostic_limits_are_not_scheduler_configs=True,stability_checks=len(stability),stability_above_5_percent=sum(not r['within_5_percent'] for r in stability)),indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default=str(ROOT/'evidence'));run(p.parse_args())
