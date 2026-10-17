# Qwen-sized MoE prefill token scaling

Final snapshot; run status: PASS. Completed token levels: [512, 1024, 2048, 4096].

## Scope and provenance
Synthetic Zipf(1.1) routing, seed 20261016; EP64, H2048, I768, E128, top-k 8, BF16. Pair jetty; TA 1024 B; chunks 4096 B; links 100 Gbps / 20 ns. Effective compute 500 GFLOPS is a simulator assumption. These are not real Qwen model-router traces or hardware benchmarks. Accepted source e5494d274b4b80f643809f86e7a3b52bc632657f; local baseline 9059c77d.

N=256 is explicitly reused historical evidence, not rerun. No-balancing and Direct come from qwen-model-size-raw/scan/runs.json. Chunk uses the accepted completed relay-dependency-index-raw/runtime/index-index-control execution and its separate passing postflight, replacing the failed old Chunk attempt. Exact input config and plan remain the historical N=256 Chunk inputs.

N=512, 1024, 2048, 4096 are requested sequentially, no-balancing → Direct → Chunk, with all three passing before advancing. Every new guarded stage has a 3600-second timeout; unchanged memory/disk guards remain authoritative. No model or strategy change is made by this analysis. Harness provenance discloses a helper-only capacity wording/explicit-assertion edit after the N=512 preparation; capacity-at-launch.py.txt preserves the original. Regression-reuse-proof.json records 64 accepted regression commands with matching source/binary evidence, reused rather than rerun.

## Completed measurements
| Tokens | Strategy | Layer ms | Speedup | Weight ms | Replicas | Max NPU load |
|---:|---|---:|---:|---:|---:|---:|
| 256 | no-balancing | 7.957270688 | 1.0000 | 0.000000000 | 0 | 406 |
| 256 | direct | 12.690087432 | 0.6270 | 12.019932360 | 51 | 34 |
| 256 | chunk-streaming | 5.844141552 | 1.3616 | 5.173961840 | 51 | 34 |
| 512 | no-balancing | 15.876530080 | 1.0000 | 0.000000000 | 0 | 810 |
| 512 | direct | 14.179354408 | 1.1197 | 12.878491560 | 53 | 66 |
| 512 | chunk-streaming | 6.266903968 | 2.5334 | 4.966015960 | 53 | 66 |
| 1024 | no-balancing | 31.498520216 | 1.0000 | 0.000000000 | 0 | 1607 |
| 1024 | direct | 15.477521536 | 2.0351 | 12.878491560 | 56 | 132 |
| 1024 | chunk-streaming | 7.565492816 | 4.1634 | 4.965976200 | 56 | 132 |
| 2048 | no-balancing | 63.218620888 | 1.0000 | 0.000000000 | 0 | 3226 |
| 2048 | direct | 18.034661656 | 3.5054 | 12.878491560 | 59 | 262 |
| 2048 | chunk-streaming | 10.116454016 | 6.2491 | 4.960329600 | 59 | 262 |
| 4096 | no-balancing | 126.937704776 | 1.0000 | 0.000000000 | 0 | 6477 |
| 4096 | direct | 23.188766072 | 5.4741 | 12.878491560 | 57 | 524 |
| 4096 | chunk-streaming | 15.271444312 | 8.3121 | 4.960289000 | 57 | 524 |

## Timeline-envelope intersections
Intersections below are max(0, min(endA,endB) − max(startA,startB)) on aggregate stage envelopes. They show concurrent elapsed intervals, not independently measured simultaneous useful work; compute uses earliest NPU start to latest NPU end. All six pairwise weight/dispatch/compute/combine intersections are in results.csv. No sum of inclusive spans or intersections is used as LayerLatency.
| Tokens | Strategy | Weight ∩ compute ms | Dispatch ∩ compute ms | Compute ∩ combine ms |
|---:|---|---:|---:|---:|
| 256 | no-balancing | 0.000000000 | 0.139239080 | 7.745018264 |
| 256 | direct | 0.000000000 | 0.003255400 | 0.191999080 |
| 256 | chunk-streaming | 0.000000000 | 0.003166920 | 0.191910600 |
| 512 | no-balancing | 0.000000000 | 0.279650880 | 15.433774064 |
| 512 | direct | 0.000000000 | 0.004848880 | 0.286024320 |
| 512 | chunk-streaming | 0.000000000 | 0.004164080 | 0.285999520 |
| 1024 | no-balancing | 0.000000000 | 0.555975120 | 30.503753136 |
| 1024 | direct | 0.000000000 | 0.008260960 | 0.725148504 |
| 1024 | chunk-streaming | 0.000000000 | 0.008776680 | 0.722563504 |
| 2048 | no-balancing | 0.000000000 | 1.107207720 | 61.234624928 |
| 2048 | direct | 0.000000000 | 0.013154960 | 1.629790128 |
| 2048 | chunk-streaming | 0.000000000 | 0.013716440 | 1.628420328 |
| 4096 | no-balancing | 0.000000000 | 2.243126680 | 122.889943344 |
| 4096 | direct | 0.000000000 | 0.032937000 | 2.520773544 |
| 4096 | chunk-streaming | 0.000000000 | 0.028709120 | 2.521739624 |

## Incomplete points
None. All requested new points completed and passed; the N=256 baseline is reused.

## Interpretation
- Direct is slower than no-balancing at N=256 and faster at N=512. The observed reversal is bounded by those sampled points; an exact crossing is not measured or interpolated.
- N=256: Chunk is 2.171× faster than Direct; weight target duration 12.019932 → 5.173962 ms, with 51 replicas in each plan. This supports a weight-delivery benefit at this sampled point.
- N=512: Chunk is 2.263× faster than Direct; weight target duration 12.878492 → 4.966016 ms, with 53 replicas in each plan. This supports a weight-delivery benefit at this sampled point.
- N=1024: Chunk is 2.046× faster than Direct; weight target duration 12.878492 → 4.965976 ms, with 56 replicas in each plan. This supports a weight-delivery benefit at this sampled point.
- N=2048: Chunk is 1.783× faster than Direct; weight target duration 12.878492 → 4.960330 ms, with 59 replicas in each plan. This supports a weight-delivery benefit at this sampled point.
- N=4096: Chunk is 1.518× faster than Direct; weight target duration 12.878492 → 4.960289 ms, with 57 replicas in each plan. This supports a weight-delivery benefit at this sampled point.
- Completed Chunk replica counts by token count: 256: 51, 512: 53, 1024: 56, 2048: 59, 4096: 57. Replica growth need not be monotonic.
- Across completed Chunk endpoints N=256→4096, replicas change 51→57, weight bytes 481296384→537919488, and weight-duration per token 0.020210788→0.001211008 ms/token. This is the observed amortization trend, not a constant-replica or monotonically growing-replica assumption.
- No network-bottleneck claim follows from aggregate stage times alone. Link utilization and critical-path attribution were not independently measured here.

## Metric definitions and limits
LayerLatency is simulated layer end minus start. Planning, reroute, weight, dispatch, compute, and combine are overlapping timeline intervals, not additive components; do not sum them. Weight duration is target weights-end minus planning-end. Maximum NPU compute interval is max(end-start) across executed per-NPU compute intervals; it may include readiness gaps and is not pure arithmetic service time. Max NPU load counts token-expert assignments.

Host wall time, CPU time (user+system), and peak RSS describe actual simulator processes, not LayerLatency or simulated accelerator performance. host-resources-by-stage.csv separately records preparation, preflight, simulator, and verifier resources; shared preparation is repeated per strategy for provenance and must not be summed three times. Planner host wall time is separate from modeled planning time. N=256 planner metadata is historical.

Summary logging retains full online per-byte payload, terminal payload, routing/quota, dependency, weight coverage, compute order/duration, conservation, WQE completion and pair-idle checks, with independent input/plan/graph preflight and postflight evidence. It does not claim an offline raw-payload trace replay. Failed or incomplete rows have blank performance measurements and are never plotted as completed results.

Capacity prechecks and RSS forecasts are planned/extrapolated quantities, not completed measurements. capacity-forecast-vs-measured.csv explicitly compares the recorded forecast formula (historical Chunk256 peak RSS × max(1, N/256)) against observed Chunk process peak RSS, with blanks where no measured process result exists. The forecast is not a gate or a measurement, and has unknown uncertainty. Capacity forecasts remain in preparation evidence; completed execution counts and measured process resources appear in the CSV. A failed stage cannot establish performance at that token count.

## Fresh harness checks
Four lightweight mocked harness unittest methods passed after the native sweep, including ten stage-failure subtests, 3600-second timeout propagation, level order, second-preparation failure retention, and 64-bit/capacity bounds. These test orchestration and stop behavior, not a fresh native regression run. The first fixture attempt under /tmp encountered the real 8 GiB workspace-disk check with only about 4.3 GiB free there; moving only fixtures to the workspace allowed the tests to pass. Both attempts are retained and hashed; no product or guard relaxation was made.

## Disk forecast timing and limits
A separate disk-growth forecast was recorded at 2026-10-17 14:20:28 UTC before N=2048/4096 directories existed. Estimated incremental peaks were 258,479,047 / 516,958,094 bytes against then-observed 587,464,704 bytes of headroom above the unchanged 8 GiB free-disk guard. These empirical forecasts are not proven upper bounds or measurements. N=512/1024 had exact input/free-disk checks and live guards, but no separately recorded output-growth forecast before execution; no forecast is backfilled. disk-forecast.json preserves the source record. A separate 14:23 UTC update, disk-forecast-with-retention-reserve.json, reserves intervening N=1024/2048 retained output; N=4096 estimated peak 516,958,094 bytes versus reserved headroom 565,207,972 bytes leaves about 48 MB. This narrow estimated margin has unknown uncertainty; the actual guard remains authoritative. Both forecasts are retained without overwriting their timing. A further 14:31:21 UTC refresh before N=4096 uses the completed N=1024 footprint rather than N=512: estimated peak increment 368.4 MB versus 561.3 MB reserved headroom after allowing N=2048 retention. disk-forecast-refresh-before-4096.json preserves exact numbers. This changes only the empirical reference point, never the hard guard; earlier forecasts remain visible.

## Reproduction and evidence
Run analysis-output/analyze.py with --workspace pointing to the parent of the worktree and raw directories; add --final only after the run stops. This collector reads source files without changing them, rerunning benchmarks, or changing the model. results.csv, host-resources-by-stage.csv, four SVG plots, completed-evidence.json and source-hashes.json retain small aggregate evidence. artifact-manifest.json hashes these deliverables. The source ledger hashes reflect the exact bytes read for this snapshot, even while the run is active. Large raw payloads, configurations and archives are excluded from this output; source-hashes.json links them by exact path/hash.
