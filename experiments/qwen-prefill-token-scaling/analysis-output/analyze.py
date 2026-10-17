#!/usr/bin/env python3
"""Read-only aggregate analysis. Never invokes a simulator or modifies source evidence."""
import argparse, csv, hashlib, importlib.util, json, math
from pathlib import Path
from datetime import datetime, timezone
H=Path(__file__).resolve().parent
P=H.parent
STRATEGIES=['no-balancing','direct','chunk-streaming']
TOKENS=[256,512,1024,2048,4096]
READ_BYTES={}
def read(p):
 p=Path(p); data=p.read_bytes(); READ_BYTES[str(p)]=data; return json.loads(data)
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): Path(p).write_text(json.dumps(x,indent=2)+'\n')
def slim(x):
 if isinstance(x,dict): return {k:slim(v) for k,v in x.items() if k not in ('host_before','host_after','command','cpuinfo')}
 if isinstance(x,list): return [slim(v) for v in x]
 return x

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=P.parents[2]);ap.add_argument('--raw',type=Path);ap.add_argument('--final',action='store_true');a=ap.parse_args()
 b=a.workspace; raw=a.raw or b/'qwen-token-scaling-raw/attempt-1'
 status=read(raw/'status.json'); assert not a.final or status['status']!='RUNNING', 'Cannot finalize a live run'
 ledger=read(raw/'runs.json'); baseline_path=b/'qwen-model-size-raw/scan/runs.json'; baseline=read(baseline_path)
 sources=[baseline_path,raw/'runs.json',raw/'status.json',raw/'execution-provenance.json',P/'fixed-config.json']
 disk_forecast=raw.parent/'disk-forecast-before-2048-4096.json'
 if disk_forecast.exists():
  sources.append(disk_forecast);write(H/'disk-forecast.json',read(disk_forecast))
 reserved_forecast=raw.parent/'disk-forecast-with-retention-reserve.json'
 if reserved_forecast.exists():
  sources.append(reserved_forecast);write(H/'disk-forecast-with-retention-reserve.json',read(reserved_forecast))
 refreshed_forecast=raw.parent/'disk-forecast-refresh-before-4096.json'
 if refreshed_forecast.exists():
  sources.append(refreshed_forecast);write(H/'disk-forecast-refresh-before-4096.json',read(refreshed_forecast))
 sources += [P/'test-harness.py'] if (P/'test-harness.py').exists() else []
 for test_attempt in ['harness-tests','harness-tests-fixture-corrected']:
  for filename in ['console.txt','resource.json']:
   test_file=raw.parent/test_attempt/filename
   if test_file.exists():sources.append(test_file)
 sources += [P/name for name in ['harness-provenance.json','capacity-at-launch.py.txt','regression-reuse-proof.json'] if (P/name).exists()]
 records=[dict(r,origin='historical reused',source=str(baseline_path)) for r in baseline if r.get('status')=='PASS']
 old=next(r for r in baseline if r['strategy']=='chunk-streaming')
 inp=b/'qwen-model-size-raw/scan/tokens-256/chunk-streaming/run'; exe=b/'relay-dependency-index-raw/runtime/index-index-control'; post=b/'relay-dependency-index-raw/postflight/index-index-control'
 spec=importlib.util.spec_from_file_location('projection',P.parent/'tiered-logging/project-summary.py');proj=importlib.util.module_from_spec(spec);spec.loader.exec_module(proj)
 summary,spans=proj.project(inp,exe/'run')
 assert read(exe/'status.json')['status']=='PASS' and read(post/'result.json')['status']=='PASS' and summary['layer_latency_ps']==5844141552
 chunk=dict(old,execution_provenance=str(exe/'provenance.json'),status='PASS',summary=summary,event_spans=spans,simulator_host=read(exe/'host/resource.json'),verifier_host=read(post/'host/resource.json'),online_validation=read(exe/'run/validation.json'),postflight_validation=read(post/'result.json'),origin='historical reused; accepted indexed production',source=str(exe))
 for k in ['failure_resource','failure_reason']:chunk.pop(k,None)
 records.append(chunk)
 sources += [exe/f for f in ['status.json','provenance.json','host/resource.json','run/online-summary.json','run/validation.json']] + [post/'result.json',post/'host/resource.json',inp/'config.json',inp/'plan.json']
 records += [dict(r,origin='new token-scaling run',source=str(raw/f"tokens-{r['tokens']}"/f"{r['strategy']}-result.json")) for r in ledger]
 index={(r['tokens'],r['strategy']):r for r in records}; rows=[]; resources=[]; proofs=[]
 for n in TOKENS:
  for strategy in STRATEGIES:
   r=index.get((n,strategy),{}); passed=r.get('status')=='PASS'; state=r.get('status',('INCOMPLETE_AFTER_STOP' if status['status']=='STOPPED' else 'RUNNING') if r else ('NOT_RUN_AFTER_STOP' if status['status']=='STOPPED' else 'NOT_STARTED'))
   row=dict(tokens=n,strategy=strategy,status=state,origin=r.get('origin','new token-scaling run'),source=r.get('source',''),failure_reason=r.get('failure_reason',status.get('reason','') if r and state=='INCOMPLETE_AFTER_STOP' else ''))
   if r.get('failure_resource') and Path(r['failure_resource']).exists():
    failure=read(r['failure_resource']);sources.append(Path(r['failure_resource']))
    resources.append(dict(tokens=n,strategy=strategy,stage='failed:'+Path(r['failure_resource']).parent.name,origin=row['origin'],**{k:failure.get(k,'') for k in ['status','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','guard']}))
   for stage in ['preparation','preflight','simulator','verifier']:
    host=r.get(stage+'_host',{})
    if host:resources.append(dict(tokens=n,strategy=strategy,stage=stage,origin=row['origin'],**{k:host.get(k,'') for k in ['status','wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','guard']}))
   if passed:
    assert r.get('online_validation',r.get('validation',{})).get('status')=='PASS', 'Completed row lacks passing online validation'
    s=r['summary'];t=s['timeline'];e=r['event_spans'];host=r['simulator_host'];nb=index[(n,'no-balancing')]['summary']['layer_latency_ps'];intervals=s.get('compute_intervals',[])
    row.update(layer_latency_ms=s['layer_latency_ps']/1e9,speedup_vs_no_balancing=nb/s['layer_latency_ps'],planning_ms=(t['planning_end']-t['layer_start'])/1e9,reroute_ms=(t['reroute_end']-t['planning_end'])/1e9,weight_duration_ms=s['weight_target_duration_ps']/1e9,max_npu_load=s['max_npu_load'],max_npu_compute_interval_ms=max((x['end_ps']-x['start_ps'] for x in intervals),default=0)/1e9,replicas=s['replicas'],weight_bytes=s['weight_bytes'],remote_wqes=s['remote_WQEs'],remote_tas=s['TA_count'],weight_wqes=s['weight_WQEs'],weight_tas=s['weight_TAs'],host_wall_seconds=host['wall_seconds'],host_cpu_seconds=host['user_cpu_seconds']+host['system_cpu_seconds'],host_peak_rss_kib=host['peak_rss_kib'],planner_host_wall_seconds=r.get('planner_cpu_wall_seconds',''),verification='PASS',online_verification_wall_seconds=s['verification_wall_ns']/1e9)
    for stage in ['dispatch','compute','combine']:row[stage+'_span_ms']=e[stage+'_span_ps']/1e9
    envelopes={'weight':(t['planning_end'],t['weights_end']),**{name:(e[name+'_start_ps'],e[name+'_end_ps']) for name in ['dispatch','compute','combine']}}
    names=list(envelopes)
    for i,left in enumerate(names):
     for right in names[i+1:]:
      aa,bb=envelopes[left],envelopes[right]
      row[left+'_'+right+'_envelope_overlap_ms']=max(0,min(aa[1],bb[1])-max(aa[0],bb[0]))/1e9
    for i,stage in enumerate(['dispatch','combine','weight']):row[stage+'_verified_bytes']=s['verified_bytes'][i]
    proofs.append(slim(r))
   rows.append(row)
 def csvout(path,data):
  fields=list(dict.fromkeys(k for r in data for k in r))
  with path.open('w',newline='') as f:w=csv.DictWriter(f,fields,lineterminator="\n");w.writeheader();w.writerows(data)
 csvout(H/'results.csv',rows);csvout(H/'host-resources-by-stage.csv',resources)
 write(H/'completed-evidence.json',proofs)
 capacity=[]
 for n in TOKENS:
  c=index.get((n,'chunk-streaming'),{}); host=c.get('simulator_host',{})
  if not host and c.get('failure_resource') and 'simulator' in c['failure_resource']:host=read(c['failure_resource'])
  estimated=1545056*max(1,n/256); measured=host.get('peak_rss_kib')
  capacity.append(dict(tokens=n,strategy='chunk-streaming',forecast_peak_rss_kib=estimated,forecast_method='linear token extrapolation of historical Chunk256 peak RSS; uncertainty unknown',measured_peak_rss_kib=measured if measured is not None else '',measured_over_forecast=measured/estimated if measured is not None else '',measurement_status=c.get('status','not completed'),forecast_is_measured=False))
 csvout(H/'capacity-forecast-vs-measured.csv',capacity)
 write(H/'source-hashes.json',[dict(path=str(p),bytes=len(READ_BYTES.get(str(p),p.read_bytes())),sha256=hashlib.sha256(READ_BYTES.get(str(p),p.read_bytes())).hexdigest()) for p in sources])
 for metric,label in [('layer_latency_ms','Layer latency (ms)'),('speedup_vs_no_balancing','Speedup vs no balancing'),('weight_duration_ms','Weight target duration (ms)'),('max_npu_compute_interval_ms','Maximum NPU compute interval (ms)')]: plot(rows,metric,label)
 report(rows,status,a.final)
 write(H/'artifact-manifest.json',dict(generated_utc=datetime.now(timezone.utc).isoformat(),final=a.final,run_status=status,files=[dict(name=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(H.iterdir()) if p.is_file() and p.name!='artifact-manifest.json']))
 print(json.dumps({'status':status,'completed_rows':sum(r['status']=='PASS' for r in rows),'output':str(H)}))

def plot(rows,key,label):
 colors=['#2563eb','#dc2626','#059669']; vals=[r[key] for r in rows if key in r]; ymax=max(vals+[1])*1.12
 x=lambda n:85+(math.log2(n)-8)*135;y=lambda v:370-v/ymax*285
 s=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="470" viewBox="0 0 760 470">','<rect width="760" height="470" fill="white"/>','<g font-family="sans-serif" font-size="13" fill="#172033">',f'<text x="85" y="30" font-size="20">{label} vs tokens</text>','<text x="85" y="52">N=256 reused historical; gaps are incomplete / not run</text>']
 for i in range(6):
  v=ymax*i/5;yy=y(v);s += [f'<path d="M85 {yy} H625" stroke="#e5e7eb"/>',f'<text x="75" y="{yy+4}" text-anchor="end">{v:.3g}</text>']
 for n in TOKENS:s += [f'<text x="{x(n)}" y="392" text-anchor="middle">{n}</text>']
 for j,st in enumerate(STRATEGIES):
  prev=None
  for n in TOKENS:
   r=next(r for r in rows if r['tokens']==n and r['strategy']==st)
   if key not in r:prev=None;continue
   xx,yy=x(n),y(r[key])
   if prev:s += [f'<path d="M{prev[0]} {prev[1]} L{xx} {yy}" stroke="{colors[j]}" fill="none" stroke-width="2"/>']
   s += [f'<circle cx="{xx}" cy="{yy}" r="4" fill="{colors[j]}"/>'];prev=(xx,yy)
  s += [f'<text x="{85+j*200}" y="436" fill="{colors[j]}">{st}</text>']
 s += ['<text x="355" y="414">Tokens (log₂ spacing)</text>','</g></svg>'];(H/(key+'.svg')).write_text('\n'.join(s))

def report(rows,status,final):
 good=[r for r in rows if r['status']=='PASS'];by={(r['tokens'],r['strategy']):r for r in good}
 lines=['# Qwen-sized MoE prefill token scaling', '',f"{'Final' if final else 'Interim'} snapshot; run status: {status['status']}. Completed token levels: {status.get('completed_token_points',[])}.",'','## Scope and provenance','Synthetic Zipf(1.1) routing, seed 20261016; EP64, H2048, I768, E128, top-k 8, BF16. Pair jetty; TA 1024 B; chunks 4096 B; links 100 Gbps / 20 ns. Effective compute 500 GFLOPS is a simulator assumption. These are not real Qwen model-router traces or hardware benchmarks. Accepted source e5494d274b4b80f643809f86e7a3b52bc632657f; local baseline 9059c77d.','', 'N=256 is explicitly reused historical evidence, not rerun. No-balancing and Direct come from qwen-model-size-raw/scan/runs.json. Chunk uses the accepted completed relay-dependency-index-raw/runtime/index-index-control execution and its separate passing postflight, replacing the failed old Chunk attempt. Exact input config and plan remain the historical N=256 Chunk inputs.','', 'N=512, 1024, 2048, 4096 are requested sequentially, no-balancing → Direct → Chunk, with all three passing before advancing. Every new guarded stage has a 3600-second timeout; unchanged memory/disk guards remain authoritative. No model or strategy change is made by this analysis. Harness provenance discloses a helper-only capacity wording/explicit-assertion edit after the N=512 preparation; capacity-at-launch.py.txt preserves the original. Regression-reuse-proof.json records 64 accepted regression commands with matching source/binary evidence, reused rather than rerun.','', '## Completed measurements','| Tokens | Strategy | Layer ms | Speedup | Weight ms | Replicas | Max NPU load |','|---:|---|---:|---:|---:|---:|---:|']
 for r in good:lines.append(f"| {r['tokens']} | {r['strategy']} | {r['layer_latency_ms']:.9f} | {r['speedup_vs_no_balancing']:.4f} | {r['weight_duration_ms']:.9f} | {r['replicas']} | {r['max_npu_load']} |")
 lines += ['','## Timeline-envelope intersections','Intersections below are max(0, min(endA,endB) − max(startA,startB)) on aggregate stage envelopes. They show concurrent elapsed intervals, not independently measured simultaneous useful work; compute uses earliest NPU start to latest NPU end. All six pairwise weight/dispatch/compute/combine intersections are in results.csv. No sum of inclusive spans or intersections is used as LayerLatency.','| Tokens | Strategy | Weight ∩ compute ms | Dispatch ∩ compute ms | Compute ∩ combine ms |','|---:|---|---:|---:|---:|']
 for r in good:lines.append(f"| {r['tokens']} | {r['strategy']} | {r['weight_compute_envelope_overlap_ms']:.9f} | {r['dispatch_compute_envelope_overlap_ms']:.9f} | {r['compute_combine_envelope_overlap_ms']:.9f} |")
 lines += ['','## Incomplete points']+[f"- N={r['tokens']} {r['strategy']}: {r['status']} {r.get('failure_reason','')}" for r in rows if r['status']!='PASS']
 if len(good)==len(rows):lines.append('None. All requested new points completed and passed; the N=256 baseline is reused.')
 if status.get('reason'):lines.append('Run stop reason: '+status['reason'])
 lines += ['','## Interpretation']
 direct=[r for r in good if r['strategy']=='direct'];cross=[(a,b) for a,b in zip(direct,direct[1:]) if a['speedup_vs_no_balancing']<=1<b['speedup_vs_no_balancing']]
 if cross:
  for a,b in cross:lines.append(f"- Direct is slower than no-balancing at N={a['tokens']} and faster at N={b['tokens']}. The observed reversal is bounded by those sampled points; an exact crossing is not measured or interpolated.")
 else:lines.append('- No sampled slower-to-faster Direct crossing has yet been established. No exact threshold is inferred.')
 for n in TOKENS:
  d=by.get((n,'direct'));c=by.get((n,'chunk-streaming'))
  if d and c:lines.append(f"- N={n}: Chunk is {d['layer_latency_ms']/c['layer_latency_ms']:.3f}× faster than Direct; weight target duration {d['weight_duration_ms']:.6f} → {c['weight_duration_ms']:.6f} ms, with {d['replicas']} replicas in each plan. This supports a weight-delivery benefit at this sampled point.")
 chunks=[r for r in good if r['strategy']=='chunk-streaming']
 if len(chunks)>1:
  lines.append('- Completed Chunk replica counts by token count: '+', '.join(str(r['tokens'])+': '+str(r['replicas']) for r in chunks)+'. Replica growth need not be monotonic.')
  first,last=chunks[0],chunks[-1];lines.append(f"- Across completed Chunk endpoints N={first['tokens']}→{last['tokens']}, replicas change {first['replicas']}→{last['replicas']}, weight bytes {first['weight_bytes']}→{last['weight_bytes']}, and weight-duration per token {first['weight_duration_ms']/first['tokens']:.9f}→{last['weight_duration_ms']/last['tokens']:.9f} ms/token. This is the observed amortization trend, not a constant-replica or monotonically growing-replica assumption.")
 lines += ['- No network-bottleneck claim follows from aggregate stage times alone. Link utilization and critical-path attribution were not independently measured here.','','## Metric definitions and limits','LayerLatency is simulated layer end minus start. Planning, reroute, weight, dispatch, compute, and combine are overlapping timeline intervals, not additive components; do not sum them. Weight duration is target weights-end minus planning-end. Maximum NPU compute interval is max(end-start) across executed per-NPU compute intervals; it may include readiness gaps and is not pure arithmetic service time. Max NPU load counts token-expert assignments.','', 'Host wall time, CPU time (user+system), and peak RSS describe actual simulator processes, not LayerLatency or simulated accelerator performance. host-resources-by-stage.csv separately records preparation, preflight, simulator, and verifier resources; shared preparation is repeated per strategy for provenance and must not be summed three times. Planner host wall time is separate from modeled planning time. N=256 planner metadata is historical.','', 'Summary logging retains full online per-byte payload, terminal payload, routing/quota, dependency, weight coverage, compute order/duration, conservation, WQE completion and pair-idle checks, with independent input/plan/graph preflight and postflight evidence. It does not claim an offline raw-payload trace replay. Failed or incomplete rows have blank performance measurements and are never plotted as completed results.','', 'Capacity prechecks and RSS forecasts are planned/extrapolated quantities, not completed measurements. capacity-forecast-vs-measured.csv explicitly compares the recorded forecast formula (historical Chunk256 peak RSS × max(1, N/256)) against observed Chunk process peak RSS, with blanks where no measured process result exists. The forecast is not a gate or a measurement, and has unknown uncertainty. Capacity forecasts remain in preparation evidence; completed execution counts and measured process resources appear in the CSV. A failed stage cannot establish performance at that token count.','','## Fresh harness checks','Four lightweight mocked harness unittest methods passed after the native sweep, including ten stage-failure subtests, 3600-second timeout propagation, level order, second-preparation failure retention, and 64-bit/capacity bounds. These test orchestration and stop behavior, not a fresh native regression run. The first fixture attempt under /tmp encountered the real 8 GiB workspace-disk check with only about 4.3 GiB free there; moving only fixtures to the workspace allowed the tests to pass. Both attempts are retained and hashed; no product or guard relaxation was made.','','## Disk forecast timing and limits','A separate disk-growth forecast was recorded at 2026-10-17 14:20:28 UTC before N=2048/4096 directories existed. Estimated incremental peaks were 258,479,047 / 516,958,094 bytes against then-observed 587,464,704 bytes of headroom above the unchanged 8 GiB free-disk guard. These empirical forecasts are not proven upper bounds or measurements. N=512/1024 had exact input/free-disk checks and live guards, but no separately recorded output-growth forecast before execution; no forecast is backfilled. disk-forecast.json preserves the source record. A separate 14:23 UTC update, disk-forecast-with-retention-reserve.json, reserves intervening N=1024/2048 retained output; N=4096 estimated peak 516,958,094 bytes versus reserved headroom 565,207,972 bytes leaves about 48 MB. This narrow estimated margin has unknown uncertainty; the actual guard remains authoritative. Both forecasts are retained without overwriting their timing. A further 14:31:21 UTC refresh before N=4096 uses the completed N=1024 footprint rather than N=512: estimated peak increment 368.4 MB versus 561.3 MB reserved headroom after allowing N=2048 retention. disk-forecast-refresh-before-4096.json preserves exact numbers. This changes only the empirical reference point, never the hard guard; earlier forecasts remain visible.','','## Reproduction and evidence','Run analysis-output/analyze.py with --workspace pointing to the parent of the worktree and raw directories; add --final only after the run stops. This collector reads source files without changing them, rerunning benchmarks, or changing the model. results.csv, host-resources-by-stage.csv, four SVG plots, completed-evidence.json and source-hashes.json retain small aggregate evidence. artifact-manifest.json hashes these deliverables. The source ledger hashes reflect the exact bytes read for this snapshot, even while the run is active. Large raw payloads, configurations and archives are excluded from this output; source-hashes.json links them by exact path/hash.']
 (H/'report.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
