# Multi-NPU Chunk Streaming Relay

Base: `ea78e1ba7ce7fce7caa747b96d02c3d324765383`. This milestone extends the accepted weight strategy interface and adds an independent executor. Planner placement, quota/reroute, token WQE rules and the FLOP-based batched compute implementation are unchanged. Direct remains supported and its old executor remains runnable.

## Reproduce

```bash
bash experiments/multi-npu-relay/run.sh
```

Dependencies remain the pinned ns3 checkout `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`, ns3 tools `29009175f1778f76a22d929063c3a0821cb91e56`, Python 3.12 and C++20. Defaults: `/workspace/ns-3-ub`, `/workspace/build-tools`, `/tmp/ub-relay-build/graph-tool`. Override `NS3_ROOT`, `BUILD_TOOLS`, `BUILD_JOBS`, `EVIDENCE`, `RELAY_GRAPH_TOOL`. No new third-party packages. `build.sh` builds only the scenario, graph compiler, extracted-reference oracle and coverage tests. `suite.py` runs the frozen matrix; `tests.py` verifies oracle equivalence and executes faults; `regressions.py` runs the full accepted Direct suite and its complete older regressions in separate output locations.

`EVIDENCE=/tmp/relay-reproduce bash experiments/multi-npu-relay/run.sh` preserves delivered evidence. `python3.12 experiments/multi-npu-relay/analyze.py --out /tmp/relay-reproduce` generates that run's report. All commands are sequential; no concurrent builds are required.

## Fixed-source selection and grouping

Primary sources: [paper §6.2](https://arxiv.org/html/2606.04101v3#S6.SS2), [fixed task builder](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/csrc/kernels/weight_sync.cu#L126-L503), [chunk constants](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/csrc/kernels/config.cuh#L20-L23), [ready publication/wait](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/csrc/kernels/weight_sync.cu#L640-L678), and [Forward ordering](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/README.md#L134-L148).

The production C++ strategy ports the fixed selection, not a new routing/placement optimization:

1. Start sender loads at zero; visit mains by rank then local main slot. Preserve each expert's original Planner `ordinal_physical_order` / l2p replica order (never sort that list by physical ID).
2. For R replicas, relay count is min(floor(sqrt(R)), max_relays, R−1), or zero for R<=1. Adaptive eligibility requires R>=4 and R−max(relays,ceil((R−relays)/relays))>=2 by default. The paper's verbal threshold is resolved using the code's inclusive >=4. Explicit force-relay coverage uses the existing public force option; single replica always falls back to Direct.
3. Select relays from the final replica set using (rank-already-used penalty, accumulated sender bytes, rank, replica ordinal). A selected relay is also a final replica and keeps its own received weight.
4. Keep unselected leaves in l2p order. Seed the first min(leaves,relays) one per relay; assign subsequent leaves by (projected sender bytes, child count, relay rank, relay ordinal). Update main and relay send loads before the next expert.
5. Main seeds selected relays only. Each leaf has exactly one relay parent. Direct fallback updates sender loads too. Both relay strategies use the identical tree; only transfer granularity/dependencies differ.

`reference/selection.inc` is a verbatim extraction of the public selection/grouping block, with source hash and license. The independent CPU wrapper does not include the production strategy header. Tests compare 120 fixed-seed graphs plus all matrix graphs against it, and require examples that change when l2p order is sorted or cross-expert sender loads are reset. This validates selection semantics; it does not execute GPU kernels.

## Strategy and execution contract

The backwards-compatible `experiments/direct-weight-forward/weight-distribution.h` still exposes `PhysicalExpert`, `WeightEdge` and `WeightDistributionStrategy::Edges`. New options carry node count/domain membership, chunk size, public relay thresholds and the FC1/FC2 shard boundary. The supported network is one connected scale-up domain, realized by the same single switch as Direct. Multiple domains are explicitly rejected; no distance-aware relay optimization is added.

- **Direct**: one whole-weight task from each main to each final replica, as before.
- **TwoStageRelay**: one whole-weight task per tree edge. Each relay's outgoing tasks depend on its entire incoming expert weight. Relays execute independently; there is no global all-relay barrier. This is a whole-expert ablation of the public topology, not a separately claimed public kernel mode.
- **ChunkStreamingRelay**: fused FC1 (2HI elements) and FC2 (HI) are divided into chunks in shard/offset order, preserving nondivisible tails. Each chunk/edge is one WRITE WQE, further segmented into native UB TAs. Every outgoing chunk depends on all Stage-I target TA completions for the same expert/shard/chunk across the entire selected relay set. All Stage-II tasks in that group become eligible together at group_chunk_ready, without waiting for later chunks or other experts. This is the default and only streaming readiness mode; the extended interface explicitly names it GroupChunk. Noneligible experts retain Direct fallback.

`graph-tool.cc` compiles edges for the Python adapter. The C++ executor independently recompiles the same graph from placement/options/original ordinal order; `executed-transfers.csv` is compared field-for-field with adapter transfers. Dependency IDs are scoped to each unique task, physical expert and range. Two-stage full-expert and streaming group-chunk dependencies are explicit task lists, not inferred from sender callbacks. The verifier independently reconstructs the full Stage-I group rather than trusting the emitted dependency list.

A transfer owns its target byte buffer and the exact original PoC `ChunkTracker` (the accepted `nb-tracker.h` is byte-identical). Every target validates WRITE identity, explicit payload bytes and range. Only target execution completion advances coverage. Duplicate notifications with identical identity/range are idempotent; conflicting identities and invalid ranges are rejected. Final replica coverage is aggregated separately over all chunks and emits weight_ready once. Physical/task IDs, expert provenance and coverage are independently checked; no state is shared between different experts.

Relay Send copies from `weightData[sourcePhysical][offset:offset+length]`, which was written only by received payload validation. It never regenerates relay bytes. The `relay-buffer-byte` fault corrupts that stored buffer and must be detected at the leaf, in addition to direct/forwarded payload corruption faults. At successful completion `received-payloads.bin` contains all actual received transfer bytes; `payload-index.csv` identifies slices. The independent verifier checks original deterministic bytes, upstream-buffer equality and all final Combine bytes.

Planning completes, then reroute and weights start together. Dispatch waits for reroute AND every final replica weight. Original token dispatch, per-NPU serial expert batches, parallel NPUs and source top-k Combine completion follow unchanged. The source code of Duration/Compute is checked byte-for-byte against the accepted Direct implementation. Sender WQE completions are logged and drained but do not release dependencies.

## Abstraction differences and limits

GPU behavior is not silently substituted with a performance-equivalent claim:

- Public GPU tasks fan out each shared-memory tile to multiple destinations. The final tile completion publishes ready flags for the entire Stage-I chunk fan-out group. The UB model aggregates every selected relay target completion in that group before releasing any Stage-II task, preserving this dependency. Per-edge WRITE replaces GPU multi-destination stores; GPU flag-store/fence/visibility latency is not modeled. No sender WQE completion substitutes for target completion.
- GPU persistent CTA scheduling, TMA/vector copies, double buffering, NVSHMEM symmetric pointer/epoch semantics, cache/system fences and remote load/store costs are abstracted. Native UB transport, segmentation, switches/ports, arbitration and acknowledgments retain their actual simulator behavior. No separate idealized bandwidth path bypasses contention.
- Public chunks are 8×32 KiB=256 KiB. Scaled-model coverage fixes 4 KiB chunks (plus 512/1024/2000-byte boundary cases); the public 256 KiB setting is also tested. This is declared before running, not tuned for benefit. FC1/FC2 shard boundaries remain; FP8 scale shards are not modeled. Direct retains its accepted whole-expert WQE rather than GPU per-shard multicast tasks.
- Out-of-order coverage uses a fixed 20µs target execution delay on first chunks, not a claim of natural packet reordering. An additional slow_relay8 case delays rank 1 Stage-I target completions by 20µs, proving that an already-ready rank 2 relay cannot send its chunk until group completion. A live early-group fault tries precisely that prohibited send. Both per-chunk TA coverage and inter-chunk completion order are checked.
- CPU graph/planner work is precomputed. Configured planning/reroute delays alone enter Simulator time. Connection setup, GPU allocation/launch/flag latency and source memory-copy costs are not timed. Payload data and compute results are synthetic; this is not numerical SwiGLU inference.

Model/network remain accepted defaults: H64/I128/dtype2, three matrices (6HI FLOPs per token-expert, 3HI×dtype weight bytes), peak1000 GFLOP/s×0.5, setup100ns/expert, planning200ns/reroute100ns, 100Gbps links/20ns propagation, segment1024, CC=false. All are synthetic assumptions. Explicit fixed tail-case overrides and completion-delay controls are in each spec. Both submission-based and stricter first-native-TA-admission→target-ready overlap witnesses are retained. No hardware acceleration, link busy utilization or causal performance attribution follows from either kind of overlap.

See REPORT.md for all four-way observations, including regressions/slowdowns. No packing, new placement, new relay selection algorithm, core protocol modifications, Phase 2 sweeps, multi-layer, decode, training/backward, EPLB or TTFT work is included.

## Acceptance correction history

[Commit 167ffee211bafa114ccb627d6b2230bd4a02acc9](https://github.com/ponedo/ub-test/commit/167ffee211bafa114ccb627d6b2230bd4a02acc9) preserves the original per-relay implementation and its raw results. That earlier readiness was less restrictive than the fixed public implementation; describing it as required by the user was incorrect. Current results replace it with application-layer upstream-group-chunk aggregation. No GPU feature or UB core modification is needed to preserve that dependency. Per-relay streaming is no longer selectable. TwoStage remains the separately requested whole-expert ablation.
