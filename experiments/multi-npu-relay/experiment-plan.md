# Multi-NPU relay: fixed experiment plan

Base ea78e1ba7ce7fce7caa747b96d02c3d324765383. User authorized development, execution and independent branch publication on 2026-10-15. No Phase 2 parameter scan.

Claim: native UB WRITE can execute the pinned upstream replica relay selection/grouping with upstream-group target-completion-gated chunks, actual received-buffer forwarding, and unchanged end-to-end Forward invariants. Chunk streaming permits two-stage in-flight task intervals to overlap; no physical link busy claim or guaranteed latency benefit is predicted.

Four-way blocks: NoBalancing, UltraEP Direct, TwoStageRelay, ChunkStreamingRelay. Exactly one accepted Planner plan per block is reused byte-for-byte for the three balanced strategies; logical input/network/model/token WQE rules are fixed for all four. The only policy differences are replication/planning overhead vs NoBalancing and the declared weight graph/readiness strategy. NoBalancing always has resident mains and zero planning/reroute latency. Direct remains the accepted whole-expert-per-replica WQE behavior.

Frozen workload matrix is cases.py/materialized matrix.yaml. Single replica and 4-NPU force-relay canary precede 8-NPU multi-relay/multi-expert, chunk<,=,>TA, partial tails, out-of-order target completion, a fixed slow-relay group-gate canary, public chunk-size control, zero slots, then unchanged fixed EP64 trace/model/network. Public adaptive mode min4/max8/gain2 by default; force mode only specified functional coverage cases (the upstream force-relay option). Chunk 4096 bytes is an explicit scaled-model test parameter; public 262144-byte chunk tested separately. No result-dependent tuning.

Network: identical N endpoint / one N-port switch, endpoint 100Gbps, 20ns link propagation, native WRITE Transaction and required-pair RTP channels, same native defaults and CC=false as accepted Direct. All weight and activation bytes use explicit Packet payloads. No static traffic.csv can express conditional received-buffer forwarding; a stateful C++ harness emits actual native traces, exact execution graph and event stream. Query native parameter catalogs in build.sh. No ns3 core changes.

Planning/reroute are configured simulated delays. Weights and reroute begin together after planning. Dispatch waits for all final replicas and reroute. Unchanged per-NPU batched serial expert compute and Combine follow. Single clock, target TA completion aggregation, never sender WQE completion as ready.

Prediction falsifiers: missing or duplicate bytes, source forwarding before target completion, final replica ready with a gap, topology mismatch from pinned selection, changed Planner assignments/compute loads/results, or no streaming overlap in the designated multi-chunk canary. Negative latency ratios are valid and retained, not grounds for changing parameters.

Evidence: per-case original plan/config/input/edge graph, every native task/packet/port trace, events.csv, actual received-payloads.bin with index, independent summaries, target dependency timeline, weight WQE/TA counts/per-NPU send bytes/LayerLatency/weight finish; ordinary and -O verification, extracted fixed-code grouping oracle, live fault injections and legacy regressions. Payload files are synthetic model bytes, not real model weights.

Checkpoint: sequential build/run, verify each case before advancing, stop and diagnose correctness failure; retain failed attempt logs and subsequent fix/retry evidence. Continue all negative performance results. Prior milestones run in isolated snapshot/output directories so their evidence stays unchanged. No further approval gate is needed within the authorized scope.

## Acceptance correction: group readiness

The old per-relay implementation and raw results are retained in commit 167ffee211bafa114ccb627d6b2230bd4a02acc9. They were a premature synchronization abstraction, not a user requirement. The new default and only supported streaming readiness is upstream-group-chunk: all Stage-I selected relay targets for an expert/shard/chunk must complete before any Stage-II task for that group starts. Local payload source remains each relay's own received buffer. TwoStage retains the requested whole-expert, per-relay dependency ablation. No extra global barrier across chunks/experts is introduced.

Add slow_relay8 (four modes): same multi8 trace/model/tree, target rank 1 Stage-I completions delayed by a fixed 20000 ns. Prediction: rank 2 may finish receiving early, but none of its group children may start before rank 1 completes that group. A live early-group fault attempts the forbidden fast-relay send and must fail. Matrix is now 48 runs; all earlier parameters remain fixed.
