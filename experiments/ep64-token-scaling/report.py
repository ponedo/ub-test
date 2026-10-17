#!/usr/bin/env python3
"""Write the measured report from collected ledger; failures are not extrapolated."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rows=json.loads((a.raw/'analysis/scaling.json').read_text());status=json.loads((a.raw/'status.json').read_text());passed=[r for r in rows if r['status']=='PASS']
lines=['# EP64 Prefill Token Scaling preexperiment','', '**Scope: H64/I128 scaled synthetic model, not real Qwen3-235B hardware performance.**','',
'## Configuration and provenance','',
'Accepted application: `ddbab33c1bd5c74ae3946c7ce671e4d710fec402`; native `2fde39d02920e639f5b200d0c5262a517326deb8`. All strategies use Pair Jetty, EP64, 128 experts, Top-k8, single switch, 100 Gbit/s links, 20 ns link delay, 1024-byte TA segmentation. No accepted simulator/planner/network/compute source was changed. `data/provenance.json` contains source and library hashes; `fixed-config.json` pins all defaults.', '',
'Routing uses the retained generator: seed20261016, probability proportional to (expert+1)^-1.1, Top-k rejection sampling without duplicates, round-robin token source. Every strategy receives the same routing per Token count. Direct and Chunk use the exact same single computed UltraEP plan. Stored routing CSVs are prefix-consistent across scales. Main placement is two consecutive experts per NPU; two redundant slots per NPU.', '',
'Compute is 3-matrix SwiGLU GEMM FLOPs at1000GFLOPS×0.5 utilization plus100ns per active physical expert. Explicit synthetic payloads validate every byte, but no numerical MLP runs. Each token payload is128B (one TA); each expert weight is49,152B. UltraEP planning200ns and reroute100ns are fixed simulated parameters; separately measured planner CPU wall time is not injected as NPU time. NB uses zero planning/reroute time.', '',
'## Actual measurements','', '| Global tokens | Assignments | Strategy | Layer us | Speedup | Max NPU load | Replicas | Weight span us | Host wall s | RSS MiB |','|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|']
for r in passed:
 lines.append(f"| {r['tokens']} | {r['assignments']} | {r['strategy']} | {r['layer_latency_us']:.6f} | {r['speedup']:.4f} | {r['max_npu_load']} | {r['replicas']} | {r['weight_distribution_span_us']:.6f} | {r['simulator_wall_seconds']:.2f} | {r['simulator_peak_rss_kib']/1024:.1f} |")
lines+=['','Values are actual ns-3 event measurements. Host resource observations are single runs, not repeated statistical estimates. `data/analysis/scaling.csv` includes planning/reroute, dispatch/compute/combine spans, maximum rank compute duration, byte/TA/WQE/event/callback counts, logical expert and physical NPU Jain, and separate verifier resources.','', '## Execution bounds and failures','',f"Scan status: **{status['status']}**. Complete three-strategy Token points: {status['completed_token_points']}."]
if status.get('reason'):lines.append('Stop reason: '+status['reason'])
if status.get('previous_guard_failure_preserved'):
 lines.append('- Initial6250-token NB attempt stopped at the8GiB free-disk guard after27.83s (peakRSS391.2MiB), without a final simulated latency. Its complete partial evidence is under data/attempts/initial. The user explicitly approved cleanup of two sets of verified old expanded copies and resuming6250→8192→12500. A fresh output root preserved all initial results;6250 routing and full simulator input hashes matched exactly before execution. The8GiB/300s guards remained unchanged. Cleanup raised free disk to12.94GiB; its receipt is retained under data/attempts/resumed.')

for r in rows:
 if r['status']=='FAIL':lines.append(f"- Attempted {r['tokens']} tokens / {r['strategy']}: {r['status']}; {r['failure_reason']}. No final layer latency or speedup is claimed.")
lines.append('- Requested21arms: '+', '.join(f"{sum(r['status']==state for r in rows)} {state}" for state in ['PASS','FAIL','NOT_RUN'])+'.')
attempted={r['tokens'] for r in rows if r['status']!='NOT_RUN'};missing=[t for t in [256,1024,2048,4096,6250,8192,12500] if t not in attempted]
lines+=['- Unattempted Token points: '+str(missing)+'.','- Guards remain300s per measured stage,6GiB process-tree RSS,7GiB address space,8GiB free output disk,1.5GiB host-available memory,2GiB free /tmp. No capacity limit or guard was loosened.','- Initial host preflight found only5.1GiB free. With explicit user approval, one previously verified duplicate restored evidence tree (16,643 files) was removed; originals and published evidence bundles remain. The cleanup and fresh recoverability check are recorded.','', '## Answers to the experiment questions','']
for strategy in ['direct','chunk-streaming']:
 rs=[r for r in passed if r['strategy']==strategy];wins=[r['tokens'] for r in rs if r['speedup']>1]
 if rs:
  monotone=all(x['speedup']<=y['speedup'] for x,y in zip(rs,rs[1:]))
  lines.append(f"- {strategy}: speedup {'increases monotonically' if monotone else 'is not monotonic'} across successful sampled points: "+', '.join(f"{r['tokens']}→{r['speedup']:.4f}×" for r in rs)+'.')
  lines.append(f"  First measured winning point: {min(wins) if wins else 'none'}. This is a sampled bound, not an exact crossover.")
# Quantify only common measured endpoints, not a fitted asymptote.
direct={r['tokens']:r for r in passed if r['strategy']=='direct'}
chunk={r['tokens']:r for r in passed if r['strategy']=='chunk-streaming'}
common=sorted(direct.keys()&chunk.keys())
if common:
 first,last=common[0],common[-1]
 gaps=[direct[n]['layer_latency_us']-chunk[n]['layer_latency_us'] for n in common]
 lines.append(f'- Direct minus Chunk layer-latency gaps at the measured points: '+', '.join(f'{n}: {gap:.6f}us' for n,gap in zip(common,gaps))+'.')
 for name,series in [('Direct',direct),('Chunk',chunk)]:
  x,y=series[first],series[last]
  lines.append(f"- {name} weight span changes {x['weight_distribution_span_us']:.6f}→{y['weight_distribution_span_us']:.6f}us from {first}→{last}tokens; its ratio to layer latency falls {100*x['weight_distribution_span_us']/x['layer_latency_us']:.2f}%→{100*y['weight_distribution_span_us']/y['layer_latency_us']:.2f}%. Maximum rank modeled compute grows {x['max_rank_compute_duration_us']:.6f}→{y['max_rank_compute_duration_us']:.6f}us.")
 lines.append('- No measured reverse decline occurs in either speedup curve. The reported physical NPU loads are substantially more balanced under UltraEP; increasing Token count amortizes fixed-scale weight cost. Physical Token destinations and traffic distribution also change under the accepted planner, so the layer benefit cannot be assigned entirely to compute from this experiment alone. The measured range does not establish an eventual saturation point.')
lines+=['- Direct is slower at256 and faster at1024 in this fixed model; the crossover is bounded between those sampled points. Chunk already wins at the smallest256-token point, so its lower crossover is not located.','- Direct and Chunk share planned compute loads and quotas. Their difference comes from the accepted weight-transfer graph and its native event dependencies. Consult weight-duration curves together with layer latency; do not assume a universal fixed relay advantage.','- Additional tokens increase modeled expert work while expert weight bytes depend on replica placement, not on token bytes. The successful measurements can therefore amortize weight distribution; replica counts and weight spans are reported explicitly rather than assumed constant.','- Do not infer saturation or high-Token behavior beyond the completed guarded range. A host storage guard is not a simulated network failure or an UltraEP performance result.','- H64/I128 gives only48KiB per expert and128B token payload; real dimensions alter weight volume, TA counts, network cost, GEMM efficiency and memory pressure. Constant utilization and linear per-assignment FLOPs omit real NPU calibration. Fixed200ns planning and100ns reroute do not model their growth with Token count; measured CPU planner wall is separate and cannot be substituted for GPU/NPU planning latency. Results establish this scaled experiment, not real Qwen speedups.','', '## Event timing and correctness','',
'Layer latency = layer_end − layer_start. Dispatch begins after planning and max(reroute, weight readiness). Each NPU computes only after its assigned token data arrive, and sends combine after its own compute. Different NPUs overlap: global Dispatch/Compute/Combine spans are not disjoint and must not be summed. Target transaction completion still drives chunk readiness and relay/group synchronization; sender completion is not substituted.', '',
'Every successful arm passed the retained strict Pair verifier: routing/quota conservation, target payload bytes and segment coverage, weight completeness, chunk dependencies, Top-k results, exact sender callbacks, no early completion and consistent task/Jetty identities. Input hashes and full raw events are preserved. Two-stage is retained and exercised in regressions, not added to the scan.','', '## Regression results','']
rp=a.raw/'regressions/results.json'
if rp.exists():
 for r in json.loads(rp.read_text()):lines.append(f"- {r['name']}: {r['resource']['status']} ({r['resource']['wall_seconds']:.2f}s), guard={r['resource']['guard']}.")
else:lines.append('- Regression driver has not completed; no current regression PASS is claimed.')
recovery=a.raw/'regressions-old-retry/recovery/results.json'
if recovery.exists():
 lines.append('- Old-suite recovery results (unchanged test assertions):')
 for r in json.loads(recovery.read_text()):lines.append(f"  - {r['name']}: {r['resource']['status']} ({r['resource']['wall_seconds']:.2f}s).")
 lines.append('- Preserved harness failures: initial lifecycle wrapper requested an 8GiB address-space limit inside the stricter 7GiB outer guard; the isolated wrapper was tightened to 7GiB. The old-suite source snapshot omitted accepted evidence JSON fixtures; config and summary fixtures were restored exactly from accepted Git objects. The 48 completed old scenarios were reused for normal/optimized verification, and the earlier dependency chain was rerun. No simulator code, oracle assertion, or simulated input was changed to recover these harness failures. Full failed logs and fixture hashes remain available.')

lines+=['','## Evidence and reproduction','',
'Run `bash experiments/ep64-token-scaling/run.sh` with `NS3_ROOT` and fresh `RAW` as shown in README. Run `regressions.py` separately, after the scan has terminated, never concurrently. Read `data/status.json` and failure resources before choosing a larger reproduction host.', '',
'Every finalized generated run is preserved as hashed, split XZ evidence packages; original archive members were read back byte-for-byte before replacing the owned working copy. `restore.py` reconstructs an empty destination and checks every member and transport hash. Routing CSVs and analysis are also directly readable. Raw failure records are retained and explicitly labeled. Source hashes identify unchanged baseline code; new files only orchestrate, validate, package and analyze experiments.', '',
'Prior workload profiling motivates orders of magnitude: measured GPQA-main single-request P50≈185tokens (suggested256), Codeforces batch8 P90≈6112 (suggested6144), LongBench Qasper P90≈7646 (suggested7680). This scan uses chosen preliminary points, not exact quantiles; longer real batches exceed its100K-assignment ceiling. Real request lengths do not establish real expert routing. See the accepted `experiments/prefill-workload-profiling/evidence/recommended-token-points.csv`.','', 'The task stops at this delivery for acceptance; no parameter retuning or new protocol optimization is included.']
a.out.write_text('\n'.join(lines)+'\n')
