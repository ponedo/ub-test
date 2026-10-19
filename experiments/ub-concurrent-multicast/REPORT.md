# Concurrent UB multicast and UltraEP weight integration

## Result

The bounded multi-group adapter and UltraEP `multicast` weight strategy are implemented and actually compiled/run. **21 small end-to-end cases pass** (7 fixtures × Direct/Chunk/Multicast). The accepted singleton seven-case exact-equivalence gate remains passing. Concurrent same-source/different-source traffic, active-group member-set changes, windows, CBFC, actual feedback faults, independent validation and old regressions are covered below.

Public baseline: `c28c18c7f000de7468aecae7e89326f1509abf32`. Native checkout: `b8375b51a094d3b1217b697989e1ab979f609e64`; native tree `6e404be184201380cfe61859eca5971d1b1f3eb9`. **No ns-3-ub native protocol source changed in this milestone.** Native source hashes, source patch and reproduction commands accompany this report.

## Architecture and exact boundaries

### Concurrent operations

`ub-concurrent-multicast/group-manager.h` owns a bounded registry of at most 128 lifetime group operations per layer. Each operation has immutable members, independent sequence/task mapping, receive sequence tracking and sender-completion state. A new operation may start with a different membership while other operations remain live. There is no retirement/recycling pool or in-place rebinding in this milestone.

Each operation registers one accepted `lightweight::SharedSource` ingress queue on its source port/VL. Each child uses a dedicated native TP and Jetty. The existing `UbRoundRobinAllocator::SelectNextIngressQueue` performs arbitration across those queues and ordinary token traffic. Same-source groups share the real finite port, egress queue, CBFC credits and link. Different source ports can operate in parallel. No additional scheduler or unbounded packet queue is implemented.

Native RR grants include native control packets. It is packet-service fairness among eligible queues, not equal byte bandwidth or a guaranteed wall-time bound. The source data-only sequence does not strictly alternate when one group's turn emits feedback. Tests record actual dequeue grants and physical source sends. The all-child-ready barrier inside each group is retained.

The group registry limit does not imply constant total memory: native child state, actual payload and per-segment feedback/coverage evidence scale with the bounded input workload. Existing logical payload/task budgets and host guards remain active. Endpoints are retained until the one-layer simulation teardown; outstanding data/TA/TP state, branch buffers and egress queues must be drained before successful output.

### Identities and protocol reuse

- Group ID in the executor is `expert + 1`.
- Each physical replica retains its own logical transfer/task ID and native child WQE.
- Dispatch/Combine keep the existing Pair Jetty mapping.
- Weight children use a separate Jetty/TP namespace above the token-pair namespace. They do not borrow token TPs, because coalescing a native FIFO shared with unrelated traffic could mix operations.
- `SharedSource::SetMemberTasks` permits distinct child task IDs while preserving the prior default `task == group` behavior.
- Feedback is checked by `(source node, destination TPN) → expected child task`, source TPN and native PSN before passing to the original receive path. Unknown task and wrong endpoint faults fail closed.
- Payload/offset validation, native TA execution, native Transport ACK and transaction Response, and individual native sender callbacks are retained.
- No group completion is synthesized from counters or fixed RTTs. `Completed` consumes every individual native child success. `CheckDrained` verifies both directions' native TP state; the executor also checks child Jetty idle.

The implementation assumes fresh disjoint child endpoint pairs, as constructed by the executor. It is not a generic API for arbitrary cross-role TP reuse. There is no loss recovery, retransmission, congestion control, multi-switch routing or standardized group WQE.

### Wire model

The accepted envelope format is unchanged. For fanout `f > 1` and payload `p`, physical packet size is `32 + 137*f + p` bytes. It includes outer DL, group/sequence/bitmap information and each child's native header/correlation context. One payload is carried from source to switch. Each replicated output carries the full paid envelope. A singleton uses the exact native packet (`78 + p` bytes), with zero envelopes.

This conservative experimental metadata is not a UB-standard multicast header. The fixed model uses 160-byte CBFC cells, one switch and ranks 0–63. Startup admission rejects a frame that cannot fit the configured ingress/egress/initial-credit capacities. TA segment sizes above 4096B are rejected for this adapter rather than silently changing segmentation.

### UltraEP integration

`pair-jetty/pair-layer.cc` selects strategy 3. `multicast-integration.inc` groups the **unchanged Direct logical main→replica graph** by expert. All group operations start at planning completion. Every child WQE still uses the existing `Send` path and actual payload bytes.

The original target executor, `Ready → FinalWeight → Gate`, compute functions and `online-validation.inc` are unchanged. WeightReady is granted only after target execution and full weight coverage. Reroute starts concurrently with weight distribution; Dispatch begins at `max(reroute_end, weights_end)`. Group sender completion is recorded separately and does not advance WeightReady.

The Python Adapter and Independent Preflight support `multicast`; Preflight independently reconstructs groups from the accepted plan/main placement and native graph. It checks member/task identities, per-target timestamps, group completion aggregation and physical source bytes. Debug adds per-task event cross-checks and the existing strict Payload/TA verifier.

## Actual small-model results

All cases are explicit synthetic correctness/performance fixtures. Default H64/I128, 48KiB BF16 expert weights, parameterized effective 500GFLOP/s, EP4 or EP8, 100Gbps/20ns and the existing native protocol settings. `tail4` uses its accepted H65/I129, 50,310-byte weights and 333-byte TA tail fixture. `topk2_4` is 32 tokens with two logical experts/token. Other fixtures use Top-k1. No real Qwen workload is simulated here.

Each case generates the accepted Planner result once and uses identical plan and assignment files for all three strategies. Existing forced-relay test settings remain explicit in fixture generation; they were not tuned against observed speedup.

### Layer latency (µs)

| Case | Direct | Chunk | Multicast | Direct / Multicast |
|---|---:|---:|---:|---:|
| single4 | 5.757264 | 5.757264 | 5.757264 | 1.0000× |
| slots_zero4 | 4.544688 | 4.544688 | 4.544688 | 1.0000× |
| multi4_force | 15.095720 | 14.321600 | 8.056400 | 1.8738× |
| tail4 | 18.822160 | 19.222280 | 13.332680 | 1.4117× |
| multi_expert8 | 16.915608 | 15.050008 | 13.578368 | 1.2458× |
| slow_relay8 | 37.136920 | 35.889760 | 30.130480 | 1.2325× |
| topk2_4 | 16.117352 | 14.356392 | 12.776472 | 1.2615× |

### Weight distribution duration (µs)

| Case | Direct | Chunk | Multicast |
|---|---:|---:|---:|
| single4 | 4.594240 | 4.594240 | 4.594240 |
| slots_zero4 | 0 | 0 | 0 |
| multi4_force | 13.521400 | 12.740800 | 6.465600 |
| tail4 | 17.220320 | 17.623040 | 11.716840 |
| multi_expert8 | 13.521400 | 11.627880 | 10.179600 |
| slow_relay8 | 35.523160 | 34.276000 | 28.516720 |
| topk2_4 | 13.521400 | 11.721160 | 10.184680 |

Do not sum overlapping phase durations. The Layer start/end definition is unchanged. These are simulated small-model layer results, not real NPU measurements or Qwen inference speedups.

### Interpretation

- `single4` degenerates to a single-target native packet and is exactly equal across strategies. `slots_zero4` has no replication or weight traffic.
- `multi4_force` sends 49,152 source payload bytes with multicast versus Direct's 147,456. The source's actual weight wire bytes fall from 158,688 to 70,416; weight duration falls from 13.5214 to 6.4656µs. Final layer latency is 8.0564µs, so the weight and layer benefits are separately reported.
- Multicast is not automatically the smallest total wire-volume strategy. In `tail4`, total physical link TX bytes are Direct 552,084, Chunk 590,100 and Multicast 649,672. Paid per-target metadata is expensive with small 333B segments, yet parallel network replication still lowers this fixture's layer latency.
- `multi_expert8` has four groups: source0 serves experts0/1, source1 serves experts2/3. On each source, one fanout2 group and one singleton overlap and interleave. The independent adapter scenario also tests two simultaneous fanout2 groups on one source. `topk2_4` has actual fanouts1/2; the Planner was not adjusted to force a desired fanout.
- `slow_relay8` fast targets become ready at 8.717720µs, while the slow target is ready at 28.717720µs. Group sender completion is later, at 28.777640µs. The application weight gate uses the former target-ready boundary, preserving the required distinction.
- Dedicated per-group weight endpoints are part of this adapter model. They differ from Direct's weight Pair Jetty sharing. The results include this resource mapping and metadata cost; they do not isolate packet copying as the only causal change. Token Pair Jetty remains unchanged.

Detailed measured counts are in `results/performance.csv`, `groups.csv`, `packet-counts.csv` and `multicast-ports.csv`. WQE/TA counts are logical native child operations, not group counts. Main-source payload, all-NPU source payload, actual source wire bytes and total physical network TX bytes are distinct columns. ACK/Response counts in the performance CSV are host-origin counts for the full layer, including Dispatch/Combine; forwarded switch copies are separately available in packet counts.

## Waiting, resources and observation cost

`results/queue-wait.csv` reports actual physical egress residence integrals from native enqueue/dequeue traces, departed packets and queue peaks. Mean egress residence is `total_egress_residence_ps / dequeued_packets`. It does not include all upstream VOQ or application waiting. `groups.csv` reports native limited/empty gate-query counts; private multicast grant timelines record actual grant times and inter-grant gaps. These are not mislabeled as exact window-stall durations. The limited-query counters depend on observation frequency.

Adding queue observations changes no scheduling call. All 21 simulated summary results remain equal to the preceding instrumentation version; 15 selected Debug application/TA/Payload files are byte-identical (`telemetry-parity.json`). No correctness checks are disabled.

Measured simulator CPU time is approximately 0.04–0.22 seconds and Peak RSS about 19–23MiB for these tiny cases. Guarded wall measurements cluster near 0.25 seconds because of the guard's polling granularity; they are not precise sub-second speed benchmarks. Final O3/g build peaked around 1.21GiB RSS. No resource guard was relaxed or triggered.

## Correctness and regressions

| Suite | Actual result |
|---|---|
| Concurrent positive scenarios | 5 PASS: same source, different source, active overlap/different members, window recovery, finite CBFC |
| Actual feedback injection | 4 expected failures: duplicate, missing, wrong TPN, wrong task on a registered endpoint |
| Capacity admission | Lifetime group bound and oversized frame rejected before transmission |
| Accepted singleton native A/B | 7 exact byte/time/credit cases PASS |
| Accepted old multi-target adapter | 5 positive + 3 expected failures PASS |
| Old independent verifier mutations | 5 detected |
| UltraEP small matrix | 21 PASS, complete online validation and independent pre/postflight |
| Debug / Summary | 3 strategies PASS strict offline validator and identical simulated summaries |
| Application faults | Corrupt weight, early WeightReady, early WQE, missing WQE and duplicate completion rejected; duplicate target notification remains idempotent |
| Independent membership/output mutations | Missing member, wrong member, wrong envelope count, early receiver timestamp rejected |
| Old application regression | No Balancing/Direct/Two-Stage/Chunk simulated summaries exactly equal to accepted baseline (excluding host verification time) |
| Old network PoC | 13 positive/4 negative pass; 118 outputs byte-identical to accepted hashes |
| Native QUICK suites | 48/49; one explicitly retained pre-existing parser-related failure |

The first native test invocation had 47/49 because the restarted environment's PATH omitted its existing CMake/Ninja tools. Restoring only the process PATH/PYTHONPATH and rerunning the two affected suites gave 48/49. The remaining `unified-bus-examples` failure is the same absent `scratch/ns-3-ub-tools/trace_analysis/parse_trace.py` dependency, observed at `ub-test.cc:36248`. Later tests skipped by that failing suite are not called PASS. No native source or test assertion was changed to hide it.

Other retained development failures: an empty `--fault=` CLI argument, a data-only strict-alternation oracle that ignored native control grants, an unrelated missing EP64 fixture loaded by a generic case loader, and a mutation that originally wrote 0 over an already-zero singleton envelope count. They were corrected in runner/oracle code, with original private evidence retained. None was repaired by changing protocol or performance parameters.

## Limits and next gate

- One-layer, single-switch, no-loss experiment; at most128 lifetime groups, no slot recycling or live membership mutation inside an operation.
- Native child state is dedicated and provisioned before submission; fresh disjoint TX/RX endpoint pairs are required.
- Rank0–63, WRITE, TA≤4096B, fixed160B CBFC cells, experimental paid metadata.
- Default native retransmission and CC remain disabled as in the accepted experiments. Errors fail the run; no recovery is claimed.
- Pending credit below native return thresholds can remain. Tests prove balance and drained packet/branch state, not that every counter resets to its initial value.
- Per-segment validation/deduplication state grows with actual work. No new global memory optimization is claimed.
- No large real-Qwen run, multiple switches, real scheduler, standardized multicast WQE or GPU/NPU measurement.

The small integration gate is complete. Larger Qwen experiments and any new protocol/recovery work require the next user-approved milestone.
