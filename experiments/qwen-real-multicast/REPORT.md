# Real Qwen N2048 multicast comparison

**Final twelve-case measured report, 2026-10-19 11:09 UTC.** Multicast improves layer latency by **2.54% at L37** and **4.32% at L52** versus Chunk Streaming, but makes **L0 2.81% slower**. All three reduce source request traffic. Recipient-link cost and the global weight-ready gate therefore matter alongside source savings. All campaign cases pass; the separate regression run retains one known native-suite parser failure, detailed below.

## Scope, provenance, and completion

The preregistered comparison is No Balancing, Direct, Chunk Streaming, and Multicast at N2048, with L37 followed by L0 and L52. It uses the same audited eight-request routing prefix and accepted planner for each same-layer comparison. Routing is real; transmitted payload contents are deterministic synthetic validation bytes, not downloaded model weights or actual inference activations. The batch is an offline concatenation of real Qwen3-235B routing requests, not an observed serving-scheduler batch.

Fixed assumptions: EP64; 128 experts/top-8; H4096/I1536 and three expert matrices; BF16 activations; idealized FP8 weights, 18,874,368 B/expert without scale metadata/padding; 1,024-B TAs and 4,096-B relay chunks; 500 effective GFLOP/s; 100-Gbps links with 20-ns delay and one switch. Main placement and token-source placement follow the frozen model assumptions.

The accepted multicast implementation is [a848419](https://github.com/ponedo/ub-test/commit/a848419aa4324668c7a17cefbf1ee601ce60d9eb), with native revision `b8375b51a094d3b1217b697989e1ab979f609e64`. [Accepted-source verification](results/accepted-source-verification.json) records byte-exact receipt verification of 71 public files, 108 native source checks, and binary verification. This establishes provenance without claiming that the partial local Git checkout has the public commit object.

Historical application/native sources differ from this accepted implementation, and old archives lack the classified packet/queue metrics needed here. Consequently, all 12 cases were freshly executed. Historical timings are used only for a separate parity check, not substituted for current measurements. The accepted protocol, planner, and fixed model remained unchanged across all 12 runs.

| Layer | No Balancing | Direct | Chunk Streaming | Multicast |
|---|---|---|---|---|
| L37 | PASS | PASS | PASS | PASS |
| L0 | PASS | PASS | PASS | PASS |
| L52 | PASS | PASS | PASS | PASS |

PASS above requires current native validation and independent preflight/postflight. The [independent campaign audit](results/campaign-verification.json) also passes all 12 cases, including packet-total reconciliation and receiver gating; its multicast checks cover all 140 children, exact group-completion maxima, and cross-link credit conservation. [Performance](results/performance.csv), aggregate CSV/JSON exports, and five charts cover all 12 runs. The historical parity audit, capacity recheck, harness tests, and final native/small-case regression run are complete; the regression status is qualified as described below.

[CAPACITY.md](CAPACITY.md) records the static PASS for all three layers, including frame sizes, child endpoint/TA counts, identifier/window bounds, and memory lower bounds. Static admission does not establish runtime completion. The unchanged protections remain 3,600 seconds/stage, 6-GiB process-tree RSS, 7-GiB address space, 8-GiB free case disk, 2-GiB free temporary disk, and 1.5-GiB available host memory.

### Preserved plan-identity harness correction

After all four L37 simulations and validators passed, the initially loaded driver stopped on a raw `plan.json` hash comparison. The only plan difference was top-level measured `cpu_wall_ns`. The corrected identity comparison excludes only that field; routing, assignments, placement, quotas, and every other plan field remain compared. Raw files/hashes, the initial driver ledger, and the independent L37 gate adjudication were preserved. No generated simulation input or accepted simulator binary changed, and L37 was not rerun to erase the stop. This was a separately adjudicated harness assertion, not a waived protocol/correctness failure.

The [historical parity audit](results/historical-parity.json) passes all nine No Balancing/Direct/Chunk cases across L0/L37/L52. Online summaries match exactly except host `verification_wall_ns`; simulator metrics match semantically; execution input, graph input, assignments, and weight edges are byte-identical. Plans match except top-level host `cpu_wall_ns`. All three standalone plan-identity harness tests also pass.

## Measured latency

All times below are simulated milliseconds. Layer latency is `layer_end - layer_start`; weight duration is `weights_end - planning_end`. Host verification/runtime is excluded.

| Layer | Metric | No Balancing | Direct | Chunk Streaming | Multicast |
|---|---|---:|---:|---:|---:|
| L37 | Layer | 89.129315416 | 27.073308104 | 25.357403064 | 24.712331144 |
| L37 | Weights | 0 | 6.867179560 | 5.150959120 | 4.505728640 |
| L0 | Layer | 36.422500656 | 23.644312664 | 23.644193504 | 24.308629384 |
| L0 | Weights | 0 | 3.436629800 | 3.436510640 | 4.101682080 |
| L52 | Layer | 87.811907672 | 28.802009584 | 25.844268464 | 24.727259944 |
| L52 | Weights | 0 | 8.585059200 | 5.626751000 | 4.509512480 |

- **L37:** MC saves 0.645230480 ms in weight readiness and 0.645071920 ms in final layer latency versus Chunk. The post-gate tail is nearly unchanged: 20.206243944 versus 20.206402504 ms. MC is 8.72% faster than Direct. Most improvement over No Balancing comes from load balancing: maximum NPU load falls from 1,158 to 262.
- **L0:** MC adds 0.665171440 ms to weight readiness and 0.664435880 ms to the layer. Its post-gate tail improves by only 0.000735560 ms. Direct and Chunk both fall back to 41 whole direct transfers, with no relay dependencies; their transfer semantics match apart from task numbering/order. The 119.16-ns difference between them is not evidence of a substantive streaming benefit.
- **L52:** MC saves 1.117238520 ms in weight readiness and 1.117008520 ms in the layer versus Chunk. Post-gate tails are 20.217317464 and 20.217547464 ms. MC is 14.15% faster than Direct. Maximum NPU load falls from 1,141 without balancing to 262 in the balanced arms.

The [application gate](../pair-jetty/pair-layer.cc#L351-L403) waits for full target-execution coverage of every replica before dispatch. It is receiver readiness, not sender feedback completion, that releases this gate. The measured weight changes consequently transfer almost one-for-one to the final layer in these cases.

## Traffic accounting: measured versus derived

“All-NPU request wire” sums measured device-egress weight packets, including any relay senders. “All-link request wire” additionally includes switch egress. “All-network wire” includes weight, token, response, ACK, and credit traffic on every transmitting link. These are serialized bytes, not unique application bytes.

| Layer | Measured bytes | Direct = Chunk | Multicast | MC change |
|---|---|---:|---:|---:|
| L37 | All-NPU weight-request wire | 1,076,539,392 | 558,692,352 | -48.10% |
| L37 | All-link weight-request wire | 2,153,078,784 | 1,942,990,848 | -9.76% |
| L37 | All-network wire | 3,166,460,416 | 2,956,473,280 | -6.63% |
| L0 | All-NPU weight-request wire | 832,794,624 | 623,370,240 | -25.15% |
| L0 | All-link weight-request wire | 1,665,589,248 | 1,565,429,760 | -6.01% |
| L0 | All-network wire | 2,605,510,696 | 2,505,388,968 | -3.84% |
| L52 | All-NPU weight-request wire | 934,354,944 | 518,197,248 | -44.54% |
| L52 | All-link weight-request wire | 1,868,709,888 | 1,699,762,176 | -9.04% |
| L52 | All-network wire | 2,836,567,552 | 2,667,701,160 | -5.95% |

**Do not equate the L37 Chunk all-NPU figure with main-origin wire.** Its validated graph contains 924,844,032 B of main-origin payload and 75,497,472 B of relay-origin payload. Applying the native unicast formula `payload + 78 B × TA count` derives 995,291,136 B main-origin wire and 81,248,256 B relay-origin wire. These reconcile exactly to the measured all-NPU total, but the packet counters do not themselves classify sender role within a node. MC's measured main-origin wire is 558,692,352 B: 43.87% below the **derived** Chunk main-origin figure.

L52 Chunk similarly contains 792,723,456 B of main-origin payload and 75,497,472 B of relay-origin payload. Its derived main/relay request wire is 853,106,688 / 81,248,256 B, reconciling to measured all-NPU wire. MC's measured main-origin wire is 39.26% below this derived Chunk main-origin figure. The public CSV labels the derivation basis separately from measured all-NPU counters.

MC's actually coalesced source payload is 415,236,096 B at L37, 528,482,304 B at L0, and 396,361,728 B at L52. Verified receiver weight payload remains 1,000,341,504 / 773,849,088 / 868,220,928 B respectively. L0 has no relay senders, so its main-origin and all-NPU request totals coincide.

Response/ACK traffic does not shrink: across Direct, Chunk, and MC, L37 has 2,458,432 all-link transaction-response packets and 4,916,864 transport ACKs; L0 has 2,022,912 and 4,045,824; L52 has 2,202,304 and 4,404,608. Their bytes also match within each layer. These counts include token traffic. MC records 2,520 / 945 / 2,033 credit frames at L37/L0/L52, versus zero / one / zero for the corresponding balanced unicast arms.

## Why source savings can coexist with an L0 regression

Fanout differs materially: L37 has 22 groups with histogram `{1:2, 2:11, 3:7, 4:2}`; L0 has 28 groups, `{1:15, 2:13}`; L52 has 21 groups, `{1:4, 2:11, 3:4, 4:2}`. Singletons use native packets. The [experimental envelope](../ub-lightweight-multicast-adapter/adapter.h#L38-L59) serializes `32 + 137 × fanout + payload` bytes, including per-child metadata. A full F2 packet is 1,330 B versus 1,102 B for native unicast. Switch egress retains envelope cost for each recipient: aggregate weight wire there increases 28.59% at L37, 13.12% at L0, and 26.46% at L52.

At L0, the latest receiver needs two F2 weights; all eight children at the four two-F2 receivers form the last eight readiness events. Its switch output transmits 36,864 weight packets in both arms, but measured bytes rise from 40,624,128 to 49,029,120 B. At 100 Gb/s, **analysis-only weight serialization lower bounds** are 3.249930240 and 3.922329600 ms, a +0.672399360-ms difference, close to the observed +0.665171440-ms weight-duration change. These bounds are not simulated completion measurements or a causal decomposition. They support recipient-link serialization as an explanation; source eligibility, arbitration, and endpoint differences remain possible contributors.

Queue evidence does not establish a general congestion regression. Mean measured egress residence falls from Chunk 22.416 to MC 18.130 ns at L37, 23.082 to 17.966 ns at L0, and 22.280 to 18.808 ns at L52, while switch-only means rise. At L0's critical output, cumulative residence actually falls from 4.489242776 to 4.006875760 ms. Peak observed egress occupancy increases from 2,204 B to 3,208 B at L37/L52 and 2,660 B at L0. These counters cover the complete layer and exclude unmeasured internal/VOQ delay.

MC records zero window-wait checks in all three layers, alongside 2,045,953 / 1,406,230 / 1,309,241 empty-child checks at L37/L0/L52. CBFC blocked queries are zero at L37/L0 but **2,679 at one device port in L52**. Thus L52 does exhibit observed credit backpressure despite its latency improvement. Polling counts are not stall durations or complete window-occupancy histories. Native and independent validation check child/queue drain and credit conservation; pending subthreshold credit returns remain accounted.

## Endpoint, readiness, and interpretation limits

The [MC integration](../pair-jetty/multicast-integration.inc#L3-L26) provisions dedicated child Jetties and TX/RX TP pairs, including singleton children. Direct/Chunk reuse Pair Jetty/TP endpoints. L37 has 4,020 token-pair Jetties plus 53 MC children, versus 4,021 total in unicast; L0 has 4,032 plus 41, versus 4,032; L52 has 4,024 plus 46, versus 4,027. Thus the experiment compares complete accepted mechanisms. A dedicated-endpoint unicast ablation is absent; the timing deltas cannot be assigned solely to packet replication or headers.

Every MC child is receiver-ready before sender-complete. Gaps range from 64.92 ns to 9.688 us at L37, 4.51792 us at L0, and 4.86736 us at L52; the final weight sender finishes that much later than the respective weight-ready gate. Final layer completion also precedes final sender completion. The accepted execution continues through native completion/drain checks, so early application readiness is not missing feedback.

Remaining limits: no comparable unicast per-receiver timing distribution in summary logs; no complete window/stall-time history or persisted internal-switch peak occupancy; no causal ablation or repeated-run variability study. The adapter excludes congestion control and retransmission. Its envelope is experimental, not a standardized UB header. Compute and weight-format assumptions are parametric, not measured hardware throughput. Real routing does not turn synthetic validation payloads into a full model inference run. These three frozen layers demonstrate conditional benefit, including a negative case, rather than a universal multicast speedup.

## Host resources and regression outcomes

All **48 guarded stages** pass in [host-resources.csv](results/host-resources.csv): preparation, preflight, simulation, and postflight for 12 cases. The longest stage is L37 Chunk simulation, 1,220.776 s wall and 1,212.864 s CPU. The highest recorded process RSS is L37 MC, 3,900,248 KiB (3.720 GiB); peak sampled process-tree RSS is 3,994,071,040 B (3.720 GiB). These remained below the unchanged 3,600-s and 6-GiB guards. Host resource cost includes validation and bookkeeping; it is not simulated layer latency or a hardware speed measurement.

The full campaign's native, payload/TA, independent postflight, and aggregate/per-child audits are complete. The executable static-capacity recheck passes all three actual inputs, and all three harness tests pass. The separate current-source regression run is recorded as **`PASS_WITH_KNOWN_NATIVE_SUITE_FAILURE`**, not an unqualified native-suite pass; see [regression-summary.json](results/regression-summary.json).

- Native suite: **48/49 pass**. The sole failure is the known `unified-bus-examples` missing `parse_trace.py` postprocessing dependency. Its wrapper reports failure from that suite result; no resource guard triggered. The failure is retained and disclosed rather than suppressed.
- Four prior application simulation summaries match exactly.
- Concurrent multicast: 5 positive cases pass and 4 expected-negative cases reject.
- Singleton parity: 7 exact pairs pass.
- Prior multicast cases: 5 positive cases pass and 3 expected-negative cases reject.
- Verifier mutations: all 5 are detected.
- Network replication: 13 positive cases pass and 4 expected-negative cases reject.

These are separate checks of the unchanged accepted source/native implementation. Expected-negative cases validate rejection behavior; the known native-suite failure does not change the measured twelve-case campaign status.

## Evidence and reproduction

See [README.md](README.md), the [preregistered plan](experiment-plan.md), [capacity audit](CAPACITY.md), and [run ledger](run-ledger.md). Measured exports include [performance](results/performance.csv), [status](results/status.csv), [packets](results/packet-counts.csv), [queues](results/queue-wait.csv), [groups](results/groups.csv), [ports/credits](results/multicast-ports.csv), [host resources](results/host-resources.csv), [input provenance](results/input-provenance.json), [execution summaries](results/execution-summaries.json), [campaign verification](results/campaign-verification.json), [historical parity](results/historical-parity.json), and [regressions](results/regression-summary.json).

Charts: [layer latency](results/layer-latency.png), [weight duration](results/weight-duration.png), [speedup versus No Balancing](results/speedup.png), [all-NPU weight-request wire](results/source-weight-bytes.png), and [all-network wire](results/network-bytes.png). The source-weight chart includes relay senders; main-origin measured/derived figures are separately identified in the CSV and discussion above.

Private raw requests, token routing/mapping, payload bytes, and per-child identity records are excluded from publication.
