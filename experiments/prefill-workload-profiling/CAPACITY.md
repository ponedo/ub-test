# EP64 executor and planner capacity audit

This is a read-only audit of base `6fb74a83cdf025036ea9f9487aef69669b3c5d3f`. No planner, model or simulator is executed for this profiling task. `evidence/executor-audit.json` verifies audited source hashes match that base; `capacity-bounds.csv` derives bounds algebraically. These are rejection conditions and cost drivers, not measured feasible runtimes or memory guarantees.

## Hard bounds and actual buffers

The [relay executor](../multi-npu-relay/multi-npu-relay.cc#L60) accepts N≤72, E≤512, T≤100,000, physical instances≤1,024, per-expert W≤64 MiB, and weight tasks≤20,000. Its decisive check at line 71 is:

```
A = T * k
A <= 100000
2 * A * H * dtype_bytes + R * W <= 256 MiB
W = matrices * H * I * dtype_bytes
R = physical_instances - logical_experts
```

T is **global input tokens across the EP domain**, not requests and not tokens per rank. EP64 does not multiply this budget by 64. Top-k2 allows at most 50,000 tokens by assignments; Qwen's top-k8 allows at most 12,500. Planner validation alone accepts A≤2,000,000, so a valid planner JSON can still be rejected by the executor.

The checked byte expression is not RSS. `AddTransfer` allocates every dispatch, combine and weight transfer buffer (line 58), retained through execution. Lines 125–127 also allocate a full W-byte `weightData` buffer for each replica. For the current tree with one complete incoming weight per replica, persistent payload arrays alone total **2AHd + 2RW**. The extra RW is omitted from the admission expression. Original model weights are synthetic byte generators, not loaded resident model tensors. Send vectors, native explicit-payload packets/copies, local callback captures, target TA buffers, chunk coverage, dependencies, Python dictionaries, JSON input/output and traces add further costs.

For pinned Qwen dimensions H=4096, I=1536, bf16=2, three SwiGLU matrices, each expert is **36 MiB**. At R=31, weight transfers alone are **1,116 MiB**, so the 256 MiB admission check fails even with zero tokens. With k8 and R=0/1/2/4/7, its algebraic token ceilings are 2048/1760/1472/896/32; R≥8 fails at zero tokens. A 64 MiB per-expert allowance does not make many real-size replicas feasible.

The previous scaled prototype uses H=64, I=128, d=2, W=48 KiB. At R=31 and A=100,000 its checked bytes are 27,123,712; another 1,523,712 bytes of persistent replica buffers are outside the check. The assignment ceiling binds before that byte ceiling. Scaling these dimensions changes the communication/computation model; it cannot stand in for a Qwen-size payload experiment.

## Planner, transport and verification costs

| Component | Evidence and scaling implication |
|---|---|
| Planner constraints | [planner.py](../../planner/quota/planner.py#L49), lines 61–79: A≤2M; upstream EP≤72, E≤512, E divisible by EP; contiguous equal main placement; uniform slots, total redundant slots≤512; conservative int32 guards depend on beta/epsilon. E128/EP64/two slots allows up to P=256 physical instances and a 64×256 source-quota table (16,384 cells). |
| Planner materialization | Per-token source/logical top-k/physical mapping, N×E demand, N×P quota matrices, audit/reference/repair JSON and Python objects remain explicit. Token mapping scales with Tk; a packed integer count is not a Python RSS estimate. |
| CPU reference | [upstream.py](../../planner/quota/upstream.py) launches reference subprocesses with 120-second timeout per call. [replication_adapter.cpp](../../planner/quota/reference/replication_adapter.cpp#L77) starts 128 CPU threads with cooperative barriers emulating CUDA lanes. This is not GPU planner latency. Compilation/hash preparation is another separate cost. |
| Relay dependency graph | Executor lines 109–121 scan weight tasks against weight tasks: O(weight_tasks²) construction. Group-chunk prerequisites may hold many parent references. Smaller chunks preserve weight bytes but increase task/dependency counts. |
| Native traffic | Executor creates a Jetty/WQE per remote transfer; there are two token tasks per assignment, not packed all-to-all tensors. Weight tasks are R for whole transfers or roughly R×ceil(W/chunk) for chunk trees. Remote TA count is sum ceil(task_bytes/segment_bytes). Local transfers have buffers and events but no remote WQE. |
| EP64 topology/TP | 64 hosts plus one switch, 128 ports. Only required rank pairs get TPs, at most 2,016 undirected pairs / 4,032 directional TPs. These are transport connections, distinct from tensor parallelism. E128 alone does not fix the actual pair count; source routing does. |
| Event/packet costs | Every remote TA has admission, receive, payload verification and target completion events, plus protocol ACK/sender/native port events. Dispatch/combine gate logic and assignment scans also scale. Simulator Stop(10 seconds) is a modeled-time guard, not a wall-time prediction. |
| Independent verifier | [verify.py](../multi-npu-relay/verify.py) loads JSON and the entire event table, builds indices, reads whole payload binary and copies per-task slices. Lines 116–119 scan all A assignments for each token: O(TA). Relay checks and overlap scans are O(weight_tasks²); it also allocates a W-byte temporary buffer for relay provenance. Per-segment repeated list filtering can add cost. The final combine hash joins payload copies. Thus simulator admission is not a practical verifier performance guarantee. |

The existing accepted fixed64/chunk-streaming evidence is T=128, k=2, A=256, R=31, 372 weight WQEs, 1,488 weight TAs, 752 remote WQEs, 1,868 target segments, 13,058 event rows and 10,594,044 artifact bytes. We only read these files. Its 45,750,904 ps layer latency is a modeled result from that historical case, not this task's runtime and not a prediction for larger batches. [Existing summary](../multi-npu-relay/evidence/fixed64/chunk-streaming/summary.json)

## How to use measured workload points next

`evidence/recommended-token-points.csv` and the generated results report select future **global-token** points from actual chat-length quantiles and IID batch sums, rounded up to a multiple of 256 for convenient allocation. Each retains its source/B/quantile, exact measured value and algebraic checks. No request is silently truncated to fit a cap. A point outside the current limit is a workload target requiring a separate design change, not an executable benchmark promise.

Keep three dimensions separate: (1) real prompt lengths measured here; (2) deliberately synthetic gate skew/top-k/source-rank assignments for testing planner and relay behavior; (3) actual layer-wise model gate traces, which remain unavailable. Text lengths do not identify expert popularity, skew, correlation, local/remote ratio or replica count. Label any later synthetic gating as synthetic and record its seed and distribution independently.

For a later implementation phase, first retain a small correctness case, then choose a few measured length-derived points that pass both assignment and byte checks for the chosen synthetic model and replica count. Large LongBench batches and real-size Qwen replica traffic need explicit changes to allocation/admission, transfer aggregation/event granularity, dependency indexing and verifier indexing or streaming before attempted scaling. Planner-only limits should be checked separately. No scans, edits to those modules, runtime estimates, or claims of speedup are part of this delivery.
