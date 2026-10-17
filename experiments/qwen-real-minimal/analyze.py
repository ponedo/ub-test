#!/usr/bin/env python3
"""Read aggregate-only exports; generate analysis without modifying experiment inputs."""
import argparse,csv,json,math,os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/qwen-analysis-mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/qwen-analysis-cache")
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',type=Path,default=Path(__file__).resolve().parent/'results',help='Aggregate collector result directory')
parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent,help='Report and figure output directory')
args=parser.parse_args()
SRC=args.input.resolve();BASE=args.out.resolve();BASE.mkdir(parents=True,exist_ok=True)
loads=json.loads((SRC/'aggregate-loads.json').read_text())
ranking={int(x['layer']):x for x in csv.DictReader((SRC/'layer-ranking.csv').open())}
def gini(xs):
 s=sorted(xs);n=len(s);return sum((2*i-n-1)*x for i,x in enumerate(s,1))/(n*sum(s))
def jain(xs):return sum(xs)**2/(len(xs)*sum(x*x for x in xs))
rows=[]
for x in loads:
 r=dict(layer=x['layer'],rank_1based=int(ranking[x['layer']]['rank_1based']))
 for kind in ['expert','npu']:
  v=x[kind+'_loads'];r.update({kind+'_mean':sum(v)/len(v),kind+'_max':max(v),kind+'_max_mean':max(v)/(sum(v)/len(v)),kind+'_gini':gini(v),kind+'_jain':jain(v),kind+'_active':sum(n>0 for n in v)})
 rows.append(r)
rows.sort(key=lambda x:x['rank_1based'])
with (BASE/'all-layer-skew-statistics.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
selected=[0,37,52];stats={x['layer']:x for x in rows};loadmap={x['layer']:x for x in loads}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
fig,axs=plt.subplots(3,2,figsize=(12,8.3),layout='constrained')
for i,layer in enumerate(selected):
 for j,kind in enumerate(['expert','npu']):
  ax=axs[i,j];v=loadmap[layer][kind+'_loads'];ax.bar(range(len(v)),v,color=['#326ab1','#d77d28'][j],width=.9);ax.axhline(sum(v)/len(v),color='#555',ls='--',lw=1)
  ax.set_title(f"Layer {layer} · rank {stats[layer]['rank_1based']}/94 · {kind} max/mean {stats[layer][kind+'_max_mean']:.4g}")
  ax.set_xlabel('Expert ID' if j==0 else 'NPU ID (expert // 2)');ax.set_ylabel('Assignments');ax.set_ylim(0,200 if j==0 else 355)
fig.suptitle('Real-routing offline batch: 256 tokens, 2,048 assignments per serialized layer\nAggregate load histograms before balancing; dashed lines show mean')
fig.savefig(BASE/'selected-layer-load-histograms.png');plt.close(fig)
perf=list(csv.DictReader((SRC/'performance.csv').open()))
passed={(int(r['layer']),r['strategy']):r for r in perf if r['status']=='PASS'}
strategies=['no-balancing','direct','chunk-streaming'];labels=['NoBalancing','Direct','Chunk-Streaming'];colors=['#677782','#326ab1','#d77d28']
fig,ax=plt.subplots(figsize=(9,4.8),layout='constrained')
for j,st in enumerate(strategies):
 for i,layer in enumerate(selected):
  r=passed.get((layer,st));x=i+(j-1)*.24
  if r:
   y=float(r['layer_latency_ms']);ax.bar(x,y,width=.22,color=colors[j],label=labels[j] if i==0 else None);ax.text(x,y+.15,f'{y:.3f}',ha='center',fontsize=8)
  else:ax.text(x,.15,'pending',rotation=90,ha='center',fontsize=8,color='#777')
ax.set_xticks(range(3),[f'Layer {l}\nNPU max/mean {stats[l]["npu_max_mean"]:g}' for l in selected]);ax.set_xlim(-.55,2.55);ax.set_ylabel('Simulated layer latency (ms)');ax.set_title(f'Real-routing mini-experiment · {len(passed)}/9 verified runs\nHypothetical 500 GFLOP/s compute, not hardware measurements');ax.legend(loc='upper left');ax.margins(y=.23);fig.savefig(BASE/'layer-latency-comparison.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
for j,st in enumerate(strategies[1:],1):
 for layer in selected:
  r=passed.get((layer,st))
  if r:
   x=stats[layer]['npu_max_mean'];y=float(r['speedup']);ax.scatter(x,y,facecolors='none' if j==1 else colors[j],edgecolors=colors[j],linewidths=1.7,marker=['o','s'][j-1],s=90 if j==1 else 42,label=labels[j] if layer==0 else None);ax.annotate(f'L{layer}',(x,y),xytext=(5,7 if j==1 else -16),textcoords='offset points',fontsize=9)
ax.axhline(1,color='#777',ls='--',lw=1);ax.set_xlim(2.5,11);ax.set_ylim(.80,max([float(r['speedup']) for r in passed.values()]+[1])*1.1);ax.set_xlabel('Baseline NPU load max/mean');ax.set_ylabel('NoBalancing latency / strategy latency');ax.set_title('Exploratory speedup versus baseline NPU skew\nThree selected layers; no fitted trend or causal claim');
if len(passed)>1:ax.legend()
fig.savefig(BASE/'speedup-versus-npu-skew.png');plt.close(fig)
lines=['# Real-routing Qwen3-235B-A22B mini-experiment','',f'Current aggregate export: {len(passed)}/9 runs verified PASS. Only completed runs have numeric results; pending or stopped runs are not imputed.','', '## Scope and fixed assumptions','', 'This is a discrete-event simulation driven by observed routing, not a numerical Qwen inference or hardware measurement. The fixed offline batch takes 22 + 224 + 10 tokens from three independent requests in existing manifest order. It is not an observed joint-forward batch. The same 256 tokens and 2,048 top-8 assignments are used in each selected serialized layer. Serialized layer IDs and source token ordinals have not independently been proven to be model-layer IDs or tokenizer IDs.','', 'All 94 layers are ranked ascending by baseline NPU max/mean, breaking ties by serialized layer ID. Ranks 1, 47 (lower median), and 94 select layers 0, 37, and 52. Main placement is expert // 2 on 64 NPUs with 128 experts; source NPU is offline-batch token ordinal % 64. Source placement is an experimental assumption.','', 'Official model dimensions are H=4096, routed-expert I=1536, top-k=8. Ideal FP8 expert weights are 3HI = 18,874,368 bytes (18 MiB). The model requires another 4,608 bytes of FP32 block scales per expert, omitted here along with runtime padding/repacking. This is not the exact checkpoint/runtime footprint. Dispatch and combine use BF16 vectors (8,192 bytes per assignment per direction); BF16 wire precision is an assumption separate from dynamic FP8 compute-input quantization.','', 'Compute counts three GEMMs at 6HI = 37,748,736 FLOPs per assignment with hypothetical effective 500 GFLOP/s, plus unchanged 100 ns per nonempty physical expert. Planning 200 ns and reroute 100 ns settings remain unchanged. Network configuration is 100 Gbps per UbPort, 20 ns per UbLink delay, TA 1,024 bytes, chunk 4,096 bytes and pair jetty mode.','', '## Baseline aggregate skew','', '| Serialized layer | Rank / 94 | Expert max/mean | Expert Gini | Expert Jain | NPU max/mean | NPU Gini | NPU Jain |','|---|---|---|---|---|---|---|---|']
for layer in selected:
 r=stats[layer];lines.append(f"| {layer} | {r['rank_1based']} | {r['expert_max_mean']:.4f} | {r['expert_gini']:.4f} | {r['expert_jain']:.4f} | {r['npu_max_mean']:.4f} | {r['npu_gini']:.4f} | {r['npu_jain']:.4f} |")
lines += ['', 'Gini includes inactive experts/NPUs (zero load). Jain = (sum loads)² / (entity count × sum squared loads), also including zero-load entities. Higher Gini and lower Jain indicate more imbalance. The all-layer CSV contains all 94 layers, not only the selected examples.','', '## Verified results','', '| Layer | Strategy | Layer latency ms | Speedup vs NoBalancing | Weight WQEs | Max NPU load | Simulator host wall s |','|---|---|---|---|---|---|---|']
for layer in selected:
 for st,label in zip(strategies,labels):
  r=passed.get((layer,st))
  lines.append(f"| {layer} | {label} | {float(r['layer_latency_ms']):.6f} | {float(r['speedup']):.4f}× | {r['weight_wqes']} | {r['max_npu_load']} | {float(r['host_wall_seconds']):.3f} |" if r else f'| {layer} | {label} | pending | — | — | — | — |')
lines += ['', 'Layer latency is simulated critical-path elapsed time. Host wall time is the time needed to execute the simulator on the host and is not model inference latency. Dispatch, compute and combine spans can overlap and must not be summed as disjoint stage times. The maximum per-NPU compute interval is distinct from the global compute span.','', 'The unchanged original Chunk-Streaming algorithm produces the same 39 weight WQEs as Direct on low-skew layer 0 because its relay threshold is not reached. This is a threshold-driven outcome, not a replacement of Chunk-Streaming with Direct.','', '## Interpretation limits','', 'The speedup-versus-skew figure is descriptive for three deliberately selected layers only. Layer-specific expert placement, traffic, replication, and critical paths also differ. These observations cannot establish a causal or universal relationship between a single skew statistic and speedup. There are no replicate-run confidence intervals. Neither the plotted latencies nor their speedups establish physical-NPU performance. Historical 30B Zipf results (including the previously reported 8.31×) are background only, not a controlled real-routing-versus-Zipf A/B: this run also changes model size, H/I, ideal FP8 weight payload (18 MiB versus historical BF16 9 MiB) and GEMM FLOPs (4×). A speedup difference across those experiments cannot be attributed solely to routing. The controlled comparison here is among the three strategies within each selected layer.','', 'The figures and CSV expose only aggregated expert/NPU counts and scalar run metrics, never per-token routing.','', '## Official precision references','', '- [Pinned official config](https://huggingface.co/Qwen/Qwen3-235B-A22B-FP8/resolve/39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35/config.json)','- [Qwen3-MoE implementation, Transformers v4.51.0](https://github.com/huggingface/transformers/blob/v4.51.0/src/transformers/models/qwen3_moe/modeling_qwen3_moe.py#L223-L252)','- [FP8 implementation and scale format](https://github.com/huggingface/transformers/blob/v4.51.0/src/transformers/integrations/finegrained_fp8.py#L294-L353)','', 'See model-precision.md for the full precision audit and fixed-cost source verification.']
observations=['', '## Observed comparisons (completed cases only)', '']
for layer in selected:
 nb=passed.get((layer,'no-balancing'))
 if not nb:continue
 for st,label in zip(strategies[1:],labels[1:]):
  r=passed.get((layer,st))
  if r:
   pct=(float(r['layer_latency_ms'])/float(nb['layer_latency_ms'])-1)*100
   observations.append(f"- Layer {layer}, {label}: latency {abs(pct):.2f}% {'higher' if pct>=0 else 'lower'} than NoBalancing; max NPU assignments {nb['max_npu_load']} → {r['max_npu_load']}; weight-target duration {float(r['weight_duration_ms']):.6f} ms. This duration is a separate measured interval, not an additive phase decomposition.")
if (0,'direct') in passed and (0,'chunk-streaming') in passed:
 d=passed[(0,'direct')];c=passed[(0,'chunk-streaming')]
 observations.append(f"- Layer 0, Chunk-Streaming minus Direct latency: {(float(c['layer_latency_ms'])-float(d['layer_latency_ms']))*1000:.5f} µs. The [aggregate graph audit](results/low-layer-strategy-order.json) finds identical full edge-field multisets (39 scope=0 edges) but all 39 sequence positions differ: Direct uses physical-list order while Chunk uses ordinal physical order. The small latency difference is consistent with these existing submission-order differences; no causal intervention scan was performed.")
resources=json.loads((SRC/'resources.json').read_text())
audit_path=SRC/'finalized-archive-audit.json'
if audit_path.exists():
 audit=json.loads(audit_path.read_text())
 audit_cases=audit.get('cases',[])
 observations += ['', '## Validation and resource protection', '', f"All {len(resources)} recorded preparation, preflight, simulator and postflight stages have status PASS with no triggered guard." if all(r['status']=='PASS' and r.get('guard') is None for r in resources) else 'Consult resources.json for individual stage statuses and guard events.', f"The [finalized archive audit](results/finalized-archive-audit.json) has {sum(x.get('status')=='PASS' for x in audit_cases)}/{len(audit_cases)} cases PASS; overall status {audit.get('status')}. It verifies archived source/top-k positions, assigned and completed token counts, sender/target completion counts, hashes, and Direct/Chunk planner equality excluding host cpu_wall_ns. These checks validate simulator execution against its inputs, not physical hardware fidelity.", '', 'Stage resource records: [resources.json](results/resources.json). Scalar simulator results: [performance.csv](results/performance.csv).']
peak=max(resources,key=lambda x:x['peak_rss_kib'])
observations += ['', f"Maximum recorded peak RSS across the 36 experiment stages: {peak['peak_rss_kib']:,} KiB ({peak['peak_rss_kib']/1024**2:.3f} GiB), layer {peak['layer']} {peak['strategy']} {peak['stage']}. This is measured host memory consumption, not simulated NPU memory.", '', '## Regression coverage', '', '- 3 precision unit tests and [56 independent reproducible integration checks](results/qwen-real-reproducible-review.json) passed.', '- [4 legacy input-byte regression cases](results/input-regression.json) passed.', '- [5 actual small/EP64 simulator regression cases](results/runtime-regression.json) passed with summary-output equality excluding verification_wall_ns.', '- [13 actual fault-injection cases and 1 actual Qwen30B Zipf NoBalancing 256-token regression](results/final-runtime-compatibility.json) passed: faults were rejected with nonzero exits and FAIL validation; the Zipf run outputs matched the baseline except verification_wall_ns.', '- [5 incomplete/duplicate final-inventory rejection checks](results/final-inventory-tests.txt) passed.', '', '## Figures', '', '![Selected-layer expert and NPU aggregate loads](selected-layer-load-histograms.png)', '', '![Nine-case simulated layer-latency comparison](layer-latency-comparison.png)', '', '![Exploratory speedup versus baseline NPU skew](speedup-versus-npu-skew.png)', '', '## Possible next step (not started)', '', 'A separately authorized next experiment could expand the selected-layer sample and hold model dimensions, precision and routing inputs fixed when testing other variables. No additional stage or scan is launched by this analysis.']
lines += observations
(BASE/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'verified':len(passed),'selected_statistics':[stats[x] for x in selected]}))
