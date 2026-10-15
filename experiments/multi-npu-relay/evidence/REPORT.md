# Multi-NPU Relay: executed results

All 48 runs passed normal and optimized independent event/payload verification. Eight live fault injections, idempotent duplicate notifications, payload/event tampering tests, extracted-source graph checks and all prior milestone regressions passed. No fixed-matrix failure or skipped case.

| Case | NoBalance µs | Direct µs | TwoStage µs | Chunk µs | Direct/Chunk | Chunk weight µs | Replicas | Native admitted overlaps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single4 | 1.217152 | 5.757264 | 5.757264 | 5.757264 | 1.0000 | 4.594240 | 1 | 0 |
| multi4_force | 4.244688 | 15.095720 | 15.241120 | 14.321600 | 1.0541 | 12.740800 | 3 | 10 |
| multi8 | 8.600056 | 28.536080 | 19.735920 | 17.803720 | 1.6028 | 16.187520 | 6 | 24 |
| slow_relay8 | 8.600056 | 37.136920 | 37.275480 | 35.889760 | 1.0347 | 34.276000 | 6 | 10 |
| multi_expert8 | 10.917320 | 16.915608 | 17.082408 | 15.050008 | 1.1240 | 11.627880 | 6 | 20 |
| chunk_lt_ta | 4.244688 | 15.095720 | 15.241120 | 12.766360 | 1.1825 | 11.192040 | 3 | 100 |
| chunk_eq_ta | 4.244688 | 15.095720 | 15.241120 | 11.332040 | 1.3321 | 9.757720 | 3 | 52 |
| tail4 | 4.326800 | 18.822160 | 18.915600 | 19.222280 | 0.9792 | 17.623040 | 3 | 6 |
| out_of_order4 | 4.244688 | 34.419000 | 35.011720 | 25.998880 | 1.3239 | 24.418080 | 3 | 8 |
| public_chunk8 | 8.600056 | 28.536080 | 19.735920 | 16.909760 | 1.6876 | 15.296000 | 6 | 0 |
| slots_zero4 | 4.244688 | 4.544688 | 4.544688 | 4.544688 | 1.0000 | 0.000000 | 0 | 0 |
| fixed64 | 18.238360 | 139.969584 | 50.671824 | 45.750904 | 3.0594 | 44.379800 | 31 | 132 |

LayerLatency is layer_start through final source top-k Combine receipt. Weight duration is planning_end through all final target weights ready. A native admitted overlap is a positive intersection between a relay outgoing chunk interval (first native TA admission→target-ready) and a later incoming chunk interval for the same relay. Both edges have entered the native transport, not merely been submitted as WQEs. Counts are witness counts, not disjoint physical busy intervals or link utilization. Submission-based task-lifetime overlaps are separately retained in summaries.

## EP64 evidence

| Strategy | Weight WQEs | Weight TAs | Total weight bytes | Max NPU weight send bytes | Weight finish µs |
|---|---:|---:|---:|---:|---:|
| no-balancing | 0 | 0 | 0 | 0 | 0.000000 |
| direct | 31 | 1488 | 1523712 | 1523712 | 138.598480 |
| two-stage | 31 | 1488 | 1523712 | 294912 | 49.300720 |
| chunk-streaming | 372 | 1488 | 1523712 | 294912 | 44.379800 |

EP64 has 31 replicas and unchanged balanced max NPU load 6 (NoBalance 130). Direct/Chunk layer ratio is 3.0594×, while NoBalance/Chunk is 0.3986×. Relay improves this Direct comparison but still loses to NoBalance for this small synthetic workload. No parameters were adjusted after observing results.

## Correctness and public-source checks

The extracted selection oracle passed 120 fixed-seed multi-expert cases plus all matrix graphs. 79 cases distinguish original l2p order from rank-sorted order; 99 distinguish persistent cross-expert load from resetting it. Adaptive and public force modes, direct fallbacks and whole/chunk grouping equality are covered.

All three balanced modes copy the exact same Planner plan bytes and preserve assignments, compute loads and final Combine payload hashes. NoBalance also produces the same logical Combine payloads. Native Direct latency/load matches the accepted single-replica, multi-replica and EP64 evidence exactly. Duration/Compute code and the original PoC coverage tracker remain unchanged.

Live faults reject corrupted source bytes, corrupted forwarding bytes, corrupted stored relay buffer, early relay send, early final weight ready, premature edge ready, duplicate sending, and fast-relay sends before group completion. Duplicate target notifications are idempotent and reproduce identical latency/results. Tail/bounds/conflicting duplicate coverage tests pass; explicit delayed first-chunk execution proves out-of-order target completion without premature final ready.

The full accepted Direct 26-run matrix and ordinary/optimized checks were rerun, followed by its complete Planner, NoBalancing, Chunk Relay and legacy parity regressions. Earlier milestone evidence outside this relay package is unchanged. See prior-regression/ for commands, summaries and raw artifact hashes.

## Group-readiness acceptance correction

Correctness and dependency predictions matched for every row. The multi4_force and EP64 streaming cases exhibit positive in-flight overlap. Single-replica and zero-slot fallbacks correctly show none; the public chunk-size case does not exhibit the measured later-chunk overlap. Performance was explicitly unbounded: tail4 ChunkStreaming is slower than both Direct and TwoStage, and the two-stage 4-NPU case is slower than Direct. These results are retained.

ChunkStreaming now waits for all Stage-I selected relay targets in each expert/shard/chunk group. The slow_relay8 case holds rank 1 target completions for 20 µs: the fast rank 2 relay waits up to 17.784400 µs after its own chunk is ready. The early-group live fault attempts forwarding after local readiness but before group readiness and is rejected. Every group event is independently checked against the maximum target completion of all its Stage-I edges.

The previous per-relay implementation and raw results remain in commit 167ffee211bafa114ccb627d6b2230bd4a02acc9; attributing that simplification to the user was incorrect. This acceptance correction uses application-layer aggregation and requires no UB protocol changes. Per-relay streaming is no longer selectable. TwoStage retains its requested per-relay whole-expert ablation.

Pinned selection/grouping and group-ready dependency are preserved. GPU multi-destination tile copies, persistent GPU scheduling, flag visibility latency and memory effects remain abstractions; README details these limits. Synthetic model/network assumptions and unchanged compute limit performance conclusions.

## Evidence navigation

`comparison.json` and each summary include all NPU send-byte vectors, WQE/TA counts, target-weight time, layer time, replica count and overlap witness task IDs. `group-timeline.csv` records each actual group-ready event, Stage-I task set and slow/fast target gap. `relay-timeline.csv` joins every weight send/target-ready/sender completion with its global byte range, source/destination physical ID and dependency list. Each case retains executed-transfers.csv, events.csv, native traces, actual received-payloads.bin and payload-index.csv. SHA-256 inventory covers all delivered evidence.
