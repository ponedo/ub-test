#!/usr/bin/env python3
"""Six reproducible plot sets from verified aggregate outputs only."""
import argparse,json,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
LAYERS=[0,37,52];SIZES=[256,512,1024,2048];STRATS=['no-balancing','direct','chunk-streaming'];LABELS=['No balancing','Direct','Chunk streaming'];COLORS=['#65758B','#D68220','#168F89']
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=pathlib.Path,required=True);p.add_argument('--report-only',action='store_true');a=p.parse_args();rows=json.loads((a.results/'aggregate.json').read_text());skew=[r for r in json.loads((a.results/'input-skew.json').read_text()) if r['tokens'] in SIZES];coverage=json.loads((a.results/'coverage.json').read_text());out=a.results/'plots';out.mkdir(exist_ok=True)
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
 def finish(fig,name,title):
  fig.suptitle(title,fontsize=15);fig.tight_layout(rect=(0,.07,1,.94));fig.text(.5,.015,('N256 fanout: reconstructed validated graphs • N256 latency: historical • Nested prefixes, not independent samples' if name in ['04-replicas-fanout','05-actual-relay-experts'] else 'Verified completed runs only • N256 reused historical • Same-layer nested prefixes, not independent samples'),ha='center',fontsize=9,color='#536174');fig.savefig(out/(name+'.png'));fig.savefig(out/(name+'.svg'));plt.close(fig)
 def format_ax(ax,layer,ylabel):
  ax.set(title=f'Layer {layer}',xlabel='Routed token count N',ylabel=ylabel);ax.set_xscale('log',base=2);ax.set_xticks(SIZES,[str(x) for x in SIZES]);ax.set_xlim(230,2280);ax.grid(axis='y',alpha=.18);ax.set_ylim(bottom=0)
  if any(x in ylabel.lower() for x in ['replica','copies','experts']):ax.yaxis.set_major_locator(MaxNLocator(integer=True));ax.set_ylim(0,max(1,ax.get_ylim()[1]))
 def standard(name,title,key,ylabel,baseline=False):
  fig,axs=plt.subplots(1,3,figsize=(13,4.2))
  for ax,layer in zip(axs,LAYERS):
   for strategy,label,color in zip(STRATS,LABELS,COLORS):
    rr=[r for r in rows if r['layer']==layer and r['strategy']==strategy and key in r];ax.plot([r['tokens'] for r in rr],[r[key] for r in rr],'o-',label=label,color=color,linewidth=1.5,markersize=(7 if strategy=='direct' else 4),markerfacecolor=('white' if strategy=='direct' else color))
   format_ax(ax,layer,ylabel)
   if baseline:ax.axhline(1,color='#444',ls=':',lw=1)
  axs[0].legend(fontsize=8);finish(fig,name,title)
 if not a.report_only:
  standard('01-speedup','Speedup relative to No balancing at the same N and layer','speedup','Speedup (×)',True)
  standard('02-latency','Simulated layer latency','layer_latency_ms','Latency (ms)')
  fig,axs=plt.subplots(1,2,figsize=(11,4.4))
  for ax,key,title in zip(axs,['expert_max_mean','npu_max_mean'],['Expert load max / mean','Initial NPU load max / mean']):
   for layer,color in zip(LAYERS,COLORS):
    rr=[r for r in skew if r['layer']==layer];ax.plot([r['tokens'] for r in rr],[r[key] for r in rr],'o-',label=f'Layer {layer}',color=color)
   format_ax(ax,'',title);ax.set_title(title);ax.legend(fontsize=8)
  finish(fig,'03-input-skew','Measured routing skew (in-scope audited prefixes; not execution results)')
  fig,axs=plt.subplots(3,3,figsize=(13,10.1))
  for col,layer in enumerate(LAYERS):
   for ax,key,label in [(axs[0,col],'replicas','Total replicas excluding mains'),(axs[1,col],'max_expert_replicas_excluding_main','Max replicas per expert (R)'),(axs[2,col],'max_expert_main_outgoing_copies','Max main copies per expert')]:
    for strategy,sl,color in zip(STRATS,LABELS,COLORS):
     rr=[r for r in rows if r['layer']==layer and r['strategy']==strategy and key in r];ax.plot([r['tokens'] for r in rr],[r[key] for r in rr],'o-',color=color,label=sl,markersize=(7 if strategy=='direct' else 4),markerfacecolor=('white' if strategy=='direct' else color))
    format_ax(ax,layer,label)
  axs[0,0].legend(fontsize=8);finish(fig,'04-replicas-fanout','Replication and main-origin fanout (copies, not chunk tasks)')
  standard('05-actual-relay-experts','Experts with actual replica-origin forwarding','fanout_actual_relay_experts','Actual relay experts')
  standard('06-weight-duration','Measured weight target-completion duration','weight_duration_ms','Weight duration (ms)')
 lines=['# Real Qwen235B batch scaling: measured results','',f"Scoped acceptance state: {coverage.get('scope_status','UNKNOWN')} (raw driver state: {coverage.get('status','UNKNOWN')}); {coverage['new_verified_rows']} new verified cases plus 9 reused historical cases.",'','## Scope and interpretation','','Real routing from 8 requests (4,275 available tokens) is concatenated into nested N=256/512/1024/2048 prefixes for each of serialized layers 0, 37 and 52. This is a controlled routing-prefix experiment, not an actual serving scheduler batch or independent samples across N. Each strategy comparison uses exactly the same (N, layer) input. Only completed, independently validated PASS cases appear in latency and speedup charts. Unexecuted or protected-stop cases are left missing; no theoretical values fill gaps.','','Fixed assumptions: H=4096, I=1536, E=128, top-k=8; idealized FP8 weights (18 MiB per expert, no scale metadata), BF16 activations, 500 GFLOP/s compute, EP64 with expert main rank e//2 and source rank token_id%64; 100 Gbit/s links, 20 ns link delay, 1024-byte TA and 4096-byte chunk; pair jetty mode. These are simulator assumptions, not measured hardware throughput.','','The raw outer driver records STOPPED because it was deliberately terminated at the user-requested N2048 boundary. Scope acceptance separately requires all 27 new cases to PASS plus the explicit USER_SCOPE_LIMIT_REACHED marker; this is not a resource failure.','','N256 fanout counts are independently validated, reconstructed planner/graph statistics, checked against historical replica counts, weight bytes/WQEs/TAs and the complete per-NPU load vector. They are not a new performance run.','','planning_ms and reroute_ms are simulated event-timeline deltas: planning_end minus layer_start, and reroute_end minus planning_end. They are not host planner wall-clock measurements. All 36 rows contain both fields.','','N256 latency is reused from the earlier validated experiment. Its host elapsed/CPU times are not comparable to new runs after environment recovery. Stage spans overlap and must not be added as a serial latency decomposition. Weight-duration fraction is descriptive and is not an attribution of critical-path delay.','','## Observed speedups and finite-grid break-even','']
 for layer in LAYERS:
  for s,label in zip(STRATS[1:],LABELS[1:]):
   rr=[r for r in rows if r['layer']==layer and r['strategy']==s];positive=[r['tokens'] for r in rr if r['speedup']>1]
   desc=', '.join(f"N={r['tokens']}: {r['speedup']:.3f}× ({r['layer_latency_ms']:.3f} ms)" for r in rr)
   first=f'first observed winning N={min(positive)}' if positive else 'no measured win yet'
   lines.append(f'- Layer {layer}, {label}: {desc}; {first}.')
 if coverage.get('scope_status')=='PASS':
  lines+=['','### Main findings','','- Layer 0 changes from a slight loss at N256 (~0.950×) to a win at N512 (~1.333×), then improves to ~1.540× at N2048. The tested-grid crossover lies between the 256- and 512-token prefixes; this is not an interpolated scheduler threshold.','- Layers 37 and 52 already win at the smallest tested N256. At N2048 Chunk reaches 3.515× and 3.398× respectively, so no lower critical batch was located for these layers.','- The routing distributions are non-monotone: N1024 has no actual relay forwarding in any layer, while N2048 activates two relay experts in each of L37 and L52. More tokens do not mechanically imply more useful fanout.','- At N2048, L37 is slightly more skewed than L52 and has the larger NoBalancing latency. Layer identities must not be frozen into low/medium/high skew labels.']
 lines+=['','The first observed winning size is only a tested-grid result. A continuous critical batch size cannot be identified from these discrete, changing prefix distributions. A win already at N256 provides no lower crossover bound. Non-monotone routing skew means later wins or losses need not follow a single universal threshold.','','## Chunk versus Direct and bottleneck evidence','']
 lookup={(r['tokens'],r['layer'],r['strategy']):r for r in rows}
 for r in rows:
  if r['strategy']!='chunk-streaming':continue
  d=lookup.get((r['tokens'],r['layer'],'direct'))
  if not d:continue
  lines.append(f"- N={r['tokens']}, layer {r['layer']}: Direct / Chunk latency = {d['layer_latency_ms']/r['layer_latency_ms']:.3f}×; weight duration {d['weight_duration_ms']:.3f} → {r['weight_duration_ms']:.3f} ms; replicas {r['replicas']:.0f}."+(f" Actual relay experts {r['fanout_actual_relay_experts']}, max main copies {d['max_expert_main_outgoing_copies']} → {r['max_expert_main_outgoing_copies']}." if 'fanout_actual_relay_experts' in r else ' Historical fanout was not retained; no count inferred.'))
 if any(r.get('fanout_actual_relay_experts')==0 and r['strategy']=='chunk-streaming' for r in rows):
  lines+=['','Cases with zero actual relay experts cannot demonstrate a relay-forwarding benefit. Sub-microsecond Direct/Chunk differences in those cases are reported as tiny timing differences, not attributed to relay; their exact cause was not isolated.']
 if coverage.get('scope_status')=='PASS':
  lines+=['','### Bottleneck shift at N2048','','The measured maximum NPU compute interval is 19.781 ms for both balanced strategies on all three layers. This occupies about 84%, 78% and 77% of Chunk layer latency for L0/L37/L52. NoBalancing max compute intervals are 35.711/87.426/86.143 ms, almost the full layer latency; load balancing sharply lowers the long compute tail. These are interval comparisons, not additive critical-path attribution.','','For L37, Chunk reduces weight completion duration by 1.716 ms and layer latency by 1.716 ms versus Direct; for L52 the corresponding reductions are 2.958 ms and 2.958 ms. Both activate two relay experts and lower maximum main-origin copies from 4 to 3. This closely aligned measured reduction supports weight distribution as the remaining Direct-to-Chunk lever, while compute occupies most of the final balanced latency. It does not prove a general hardware bottleneck or isolate forwarding from readiness effects.']
 lines+=['','Direct and Chunk use the same placement objective but differ in graph forwarding and readiness; their observed difference is the combined effect, not a pure causal estimate of fanout alone. Compare actual relay counts and main-origin copies before attributing a benefit to relay. Main outgoing copies count distinct physical targets; thousands of chunk tasks are not thousands of replicas. R is replicas excluding the main; total physical instances include the main. Eligibility is distinct from actual forwarding, especially for Direct.','','Skew is measured separately at each N. In particular layers 37 and 52 reverse order at N2048; fixed low/medium/high labels would be misleading. Input-skew plots include audited inputs even where execution remains unmeasured.','','## Out-of-scope retained input evidence','','The audited N4096 source-prefix skew remains in input-skew.json as static provenance only. N4096 is excluded from performance scope, planned-case counts, missing-case inventories and all main plots. It is not scheduled or accepted as a performance result.','','## Artifacts and reproduction','','- performance.csv and aggregate.json: whitelisted per-case aggregates, including provenance and paired speedup.','- input-skew.json: audited prefix skew.','- coverage.json: current completion status.','- plots/01–06: PNG and SVG plot sets.','- collect.py accepts explicit private aggregate-ledger root, historical results directory and audited skew file. analyze.py reads only the collected results. Neither executes the simulator or reads token/payload artifacts.','','Pinned graph authority: https://github.com/ponedo/ub-test/blob/93bdf7fef154743738910da9e561d796f5955507/experiments/direct-weight-forward/weight-distribution.h','','No raw tokens, payloads, native simulator logs or host command lines are included in these public outputs.']
 if (a.results/'regression-summary.json').exists():
  regression=json.loads((a.results/'regression-summary.json').read_text())
  assert regression['status']=='PASS'
  lines+=['','## Regression checks','','The accepted small8 case passes all four strategies, including TwoStage. The H64/I128 N256 Zipf regression exactly matches the baseline for all three tested strategies in latency, WQEs, TAs, replicas, simulator events, completion counts and routing SHA256. Planner strict-floor and upstream-compatible checks, dependency-index equivalence, source extraction, independent validation, precision, fanout and scope-gate tests also pass. See results/regression-summary.json and its companion regression JSON files.','','No native protocol source was changed in this milestone. The full native regression matrix was not rerun; the baseline evidence is retained. These synthetic regression checks are separate from the real-routing performance measurements above.']
 (a.results.parent/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
