#!/usr/bin/env python3
import argparse,csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(out):
 out=Path(out);ledger=json.loads((out/'profile-ledger.json').read_text());meta=json.loads((out/'statistics-manifest.json').read_text())
 lengths=list(csv.DictReader((out/'length-statistics.csv').open()));batches=list(csv.DictReader((out/'batch-statistics.csv').open()))
 lines=['# Measured prefill workload results','',f"Measured **{meta['series']} series / {meta['length_measurements']:,} input observations**, each raw and chat. Counts include overlapping GPQA subsets and separately selected populations; this is not a deduplicated union of all datasets.",'','No model inference or network simulation was run. See [methods](../METHODS.md), [capacity audit](../CAPACITY.md), [source ledger](profile-ledger.json) and [locked revisions](../sources.lock.json).','','## Coverage','', '| Series | N / status | Available population / scope |','|---|---:|---|']
 for x in ledger:
  lines.append(f"| {x['series']} | {x.get('N',x['status'])} | {str(x.get('available_rows',''))+'; ' if 'available_rows' in x else ''}{x.get('coverage',x.get('reason',x.get('error','')))} |")
 d=next((x for x in ledger if x['series']=='dapo_unique' and x['status']=='measured'),None)
 if d:lines+=['',f"DAPO: {d['raw_rows']:,} raw rows − {d['duplicate_rows']:,} exact repeats = **{d['N']:,} unique prompts**. Dataset naming is not an observed cardinality."]
 lines+=['','## Per-request tokens','', 'Both modes and all exceedance columns are in [length-statistics.csv](length-statistics.csv). The table below is chat mode; all counts are untruncated. Each plot includes raw/chat CDF and histogram.','','| Series | N | Mean | P50 | P90 | P95 | P99 | Min | Max | CDF / histogram |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
 for r in lengths:
  if r['mode']=='chat':lines.append('| '+r['series']+' | '+ ' | '.join(f"{float(r[k]):,.1f}" if k not in ['N','min','max'] else f"{int(r[k]):,}" for k in ['N','mean','P50','P90','P95','P99','min','max'])+f" | [plot](plots/{r['series']}-lengths.png) |")
 lines+=['','## IID synthetic batch sums','', 'All 1/2/4/8/16/32-request, raw/chat statistics are in [batch-statistics.csv](batch-statistics.csv). Each series/B uses 100,000 draws with replacement. No packing, truncation, arrivals or scheduler. Selected chat examples follow.','','| Series | Requests | Mean sum | P50 | P90 | P99 | Batch plot |','|---|---:|---:|---:|---:|---:|---|']
 selected=['gpqa_main','dapo_unique','codeforces_train','swe_bench_test_issue_only','openscience_OS-Q3-235B-4','longbench_qasper','longbench_narrativeqa','longbench_repobench-p']
 for r in batches:
  if r['mode']=='chat' and r['series'] in selected and int(r['request_count']) in [1,8,32]:lines.append(f"| {r['series']} | {r['request_count']} | "+' | '.join(f"{float(r[k]):,.1f}" for k in ['mean','P50','P90','P99'])+f" | [plot](plots/{r['series']}-batches.png) |")
 lines+=['',f"Half-sample stability: **{meta['stability_above_5_percent']} of {meta['stability_checks']}** series/mode/B cases exceed a 5% relative discrepancy in P50/P90/P99 between the two 50,000-draw halves. [Full diagnostic](batch-stability.csv). This tests Monte Carlo stability, not source representativeness.",'','## Suggested future global-token points','', 'Derived from measured chat lengths/batch sums, rounded upward to multiples of 256; **suggestions only, no execution**. Algebraic scaled checks assume H64/I128/bf16/3 matrices/R31 and k8. Planner check below is the A≤2M bound alone; placement/numeric constraints also apply. Real Qwen H4096/I1536 with R31 fails the weight-byte admission check for every point.','','| Source | B | Quantile | Measured tokens | Suggested global T | Scaled executor bounds | Planner assignment bound |','|---|---:|---|---:|---:|---|---|']
 stability=list(csv.DictReader((out/'batch-stability.csv').open()))
 flagged=sorted(set((r['series'],int(r['request_count'])) for r in stability if r['within_5_percent']=='False'))
 lines.insert(lines.index('## Suggested future global-token points')-1, 'Flagged cases (raw and chat): '+', '.join(name+' B='+str(b) for name,b in flagged)+'. For B=1, use the exact full empirical quantiles in length-statistics.csv as the source-distribution reference; sampled quantiles can jump across discrete CDF steps. The flags remain reported, not silently replaced or called converged.')
 specs=[('gpqa_main',1,'P50'),('dapo_unique',8,'P90'),('codeforces_train',4,'P50'),('codeforces_train',8,'P90'),('longbench_qasper',1,'P90'),('longbench_narrativeqa',1,'P90'),('longbench_narrativeqa',8,'P90'),('longbench_narrativeqa',32,'P99')];recommend=[]
 for name,b,q in specs:
  matches=[r for r in batches if r['series']==name and r['mode']=='chat' and int(r['request_count'])==b]
  if not matches:continue
  value=float(matches[0][q]);t=math.ceil(value/256)*256;checked=2*t*8*64*2+31*49152;fit=t*8<=100000 and checked<=256*1024**2 and t<=100000;plan=t*8<=2000000
  row=dict(series=name,request_count=b,mode='chat',quantile=q,measured_tokens=value,suggested_global_tokens=t,rounding_multiple=256,top_k=8,assignments=t*8,scaled_R31_checked_bytes=checked,scaled_executor_algebraic_fit=fit,planner_assignment_bound_fit=plan,real_qwen_R31_payload_fit=False,executed=False);recommend.append(row)
  lines.append(f"| {name} | {b} | {q} | {value:,.1f} | {t:,} | {'pass bounds only' if fit else 'requires changes'} | {'pass bound only' if plan else 'exceeds bound'} |")
 with (out/'recommended-token-points.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(recommend[0]),lineterminator='\n');w.writeheader();w.writerows(recommend)
 lines+=['','No gate routing can be inferred from these lengths. Use separately labelled synthetic skew until real layer-wise traces are obtained. Context exceedance and sum-budget exceedance remain separate diagnostics in the CSVs; neither was used to discard observations.','','## Remaining gaps','', '- Exact UltraEP serving preprocessing, mixture, scheduling configuration and real routing traces are unavailable in the inspected public revision.','- SWE-bench full agent/repository-context prompts remain unmeasured.','- Two OpenScience 10-choice populations cover only converted prefixes.','- Codeforces reconstruction and uniform chat wrapping are explicit choices, not verified author recipes.','- Current executor capacity bounds preclude several realistic global token sums and Qwen-size replicated weights; no runtime feasibility claim is made.']
 failed=[x for x in ledger if x['status']=='failed']
 (out/'run-status.json').write_text(json.dumps(dict(measured_series=meta['series'],measured_observations=meta['length_measurements'],expected_series=32,all_selected_series_measured=meta['series']==32 and not failed,source_failures=failed,unavailable=[x for x in ledger if x['status']=='not_available'],model_execution=False,simulator_execution=False,performance_sweep=False),indent=2)+'\n')
 lines+=['',f"Recorded source-processing failures in this completed ledger: **{len(failed)}**."]
 (out/'RESULTS.md').write_text('\n'.join(lines)+'\n');print('results and length-derived future points written')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default=str(ROOT/'evidence'));run(p.parse_args().out)
