# Phase 1 Direct weights + Forward: executed results

All 26 matrix runs passed independent event verification in normal and optimized Python. The final `run.sh` was executed successfully, including all prior regressions. This is a single-layer functional/simulation milestone; it does not establish production NPU speedup.

| Case | NoBalancing µs | UltraEP Direct µs | Speedup NB/UltraEP | Replicas | Max load NB → UltraEP | Weight target-ready µs | Prediction status |
|---|---:|---:|---:|---:|---|---:|---|
| uniform4 | 1.363592 | 1.663592 | 0.8197 | 0 | 8 → 8 | 0.000000 | matched: overhead may dominate |
| single_replica4 | 1.217152 | 5.757264 | 0.2114 | 1 | 8 → 6 | 4.594240 | matched: overhead may dominate |
| multi_replica4 | 4.244688 | 15.095720 | 0.2812 | 3 | 32 → 10 | 13.521400 | matched: overhead may dominate |
| multi_expert8 | 5.651760 | 15.618568 | 0.3619 | 6 | 40 → 12 | 13.521400 | matched: overhead may dominate |
| slots_zero4 | 4.244688 | 4.544688 | 0.9340 | 0 | 32 → 32 | 0.000000 | matched: overhead may dominate |
| nondivisible4 | 2.343180 | 12.954760 | 0.1809 | 2 | 17 → 8 | 11.500040 | matched: overhead may dominate |
| target_delay4 | 1.217152 | 7.637624 | 0.1594 | 1 | 8 → 6 | 6.479560 | matched: overhead may dominate |
| reroute_slow4 | 1.217152 | 101.154624 | 0.0120 | 1 | 8 → 6 | 4.594240 | matched: overhead may dominate |
| two_matrix4 | 0.955008 | 4.060336 | 0.2352 | 1 | 8 → 6 | 3.093920 | matched: overhead may dominate |
| empty4 | 0.000000 | 0.300000 | n/a (empty) | 0 | 0 → 0 | 0.000000 | inconclusive performance (empty) |
| uneven_sources4 | 2.824096 | 10.680992 | 0.2644 | 2 | 24 → 8 | 9.056080 | matched: overhead may dominate |
| fixed64 | 18.238360 | 139.969584 | 0.1303 | 31 | 130 → 6 | 138.598480 | matched: overhead may dominate |
| single_replica4_repeat | 1.217152 | 5.757264 | 0.2114 | 1 | 8 → 6 | 4.594240 | matched: overhead may dominate |

LayerLatency is trace-derived from layer_start to receipt of every original token’s top-k Combine contributions. Weight duration is planning_end to the last target-side weight completion, not sender WQE completion. Both modes use identical trace, network, parameter values and per-assignment WQE rules; the intended policy overhead is charged only to UltraEP.

EP64 reduced the maximum assigned load from 130 to 6, but required 31 replicas × 49152 bytes = 1523712 weight bytes. Target-ready weight distribution took 138.598480 µs; the complete layer took 139.969584 µs versus 18.238360 µs for NoBalancing (0.1303×). This demonstrates correct load balancing plus an unfavorable Direct transfer cost for this small synthetic workload. It does not justify parameter tuning after observing the result or a real hardware acceleration claim.

## Basic timeline evidence

| Case/mode | Planning end µs | Reroute end µs | Weights ready µs | Dispatch gate µs | Layer end µs |
|---|---:|---:|---:|---:|---:|
| single_replica4/no_balancing | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.217152 |
| single_replica4/ultraep | 0.200000 | 0.300000 | 4.794240 | 4.794240 | 5.757264 |
| target_delay4/no_balancing | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.217152 |
| target_delay4/ultraep | 0.200000 | 0.300000 | 6.679560 | 6.679560 | 7.637624 |
| reroute_slow4/no_balancing | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.217152 |
| reroute_slow4/ultraep | 0.200000 | 100.200000 | 4.794240 | 100.200000 | 101.154624 |
| fixed64/no_balancing | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 18.238360 |
| fixed64/ultraep | 0.200000 | 0.300000 | 138.798480 | 138.798480 | 139.969584 |

Times above are relative to layer_start on one Simulator clock. Planning and reroute delays are configured, not derived from host CPU wall time. The dispatch gate equals max(reroute_end, weights_end). The two delayed cases exercise both sides of that maximum.

In the single-replica canary, target weights became ready at absolute 4795240 ps and dispatch began then; the weight sender completed later at 4903080 ps. The implementation and verifier therefore do not substitute sender WQE completion for target readiness.

## Correctness and regressions

- Every weight, dispatch and combine byte traversing a remote path is carried as explicit payload through the native WRITE/Transaction executor and checked at the target. Every TA offset/length, request identity and target completion is logged; full coverage is required before ready.
- Placement, per-physical quota, logical top-k, token source, assignment/WQE counts and weight provenance are validated by the adapter, C++ input/execution checks and independent event reconstruction. Main weights start ready; replicas are distributed exactly once.
- Compute waits for tokens and required weights. Expert intervals are serialized per NPU with exactly the configured FLOP-derived durations, while different NPU batches may overlap. Combine waits for batch completion, and source completion waits for every top-k contribution.
- Four live fault injections reject corrupted weight payloads, premature ready, duplicate weight forwarding and early compute. Two malformed execution inputs reject incorrect main provenance and quota. Three event-log corruptions and both unsupported relay policies are rejected. Ordinary and optimized checks pass.
- Repeated single-replica runs produce byte-identical events in both modes. The legacy two-matrix case also produces exactly 955008 ps and the same per-NPU loads in the old and new NoBalancing executors.
- The accepted Planner full suite ran in an isolated archive: strict/random/exhaustive, fixed-source replication, compatible-mode, numeric safety and normal/-O checks pass. NoBalancing passes 16 normal and 16 optimized tests; the full prior Chunk Relay regression is included and passes. Their tracked source/evidence are unchanged.

One initial cross-executor parity harness attempt omitted the old assignments.csv artifact. Its error is retained in `evidence/legacy-parity-initial-error.txt`; using the original case emitter fixed the harness, and the subsequent independent comparison passed. It was not a protocol/simulation failure. No fixed-matrix case failed or was skipped.

## Scope and parameter assumptions

All performance parameters are synthetic: scaled SwiGLU H=64/I=128/dtype=2, three-matrix GEMM FLOPs 6HI, effective throughput 1000 GFLOP/s × 0.5, setup 100 ns/expert, planning/reroute 200/100 ns, 100 Gb/s endpoint links, 20 ns propagation, 1024-byte TAs. Specific coverage overrides are frozen in cases.py and per-case specs. No number is presented as a public NPU capability. Queries of native attribute/global defaults plus explicit overrides and pinned commits make the simulator configuration reviewable.

The three-matrix model and exact scaled weights are consistent with each other; this is not numerical SwiGLU evaluation. Elementwise activation, gating/notify, memory-bandwidth effects, source memory copy cost, production-kernel efficiency and connection setup time are outside the model. The two-matrix case is legacy functional validation only. No packing, multi-layer, complete relay, training/backward, decode or Phase 2 work was performed.

Evidence: `evidence/comparison.json`, each case’s `summary.json` / `events.csv` / native logs, `evidence/tests.json`, `evidence/run-ledger.json`, `evidence/prior-regression/`, and the exact final-run console logs. See README for the public dependency evidence, adapter format and reproduction commands.
