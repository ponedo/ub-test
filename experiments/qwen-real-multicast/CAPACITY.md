# Static capacity audit: real Qwen N2048 multicast

Audited 2026-10-19 08:53:15 UTC; documented 2026-10-19 08:54:35 UTC. **Static gate: PASS for L0, L37, and L52.** No simulation was run for this audit. Runtime admission, correctness, drain, credit conservation, postflight, and resource checks remain mandatory.

## Fixed model and provenance

Qwen3-235B real-routing inputs; EP64, N2048, 128 experts/top-8; H4096/I1536, three matrices, BF16 activations, idealized FP8 weights without scale metadata (18,874,368 bytes/expert), 1,024-byte TA segments, 4,096-byte relay chunks, 500 effective GFLOP/s, and a 100-Gbps/20-ns single-switch fabric. Each weight child produces 18,432 native TAs.

Accepted multicast commit: [a848419](https://github.com/ponedo/ub-test/commit/a848419aa4324668c7a17cefbf1ee601ce60d9eb). Historical baseline: `6a870170b0519267efff6a73a6be38ee575280ae`. The verified publication receipt establishes byte-exact parity for 71 public files, rechecked when writing this audit. The parent verified 108 native source hashes and the accepted binaries; see [accepted-source-verification.json](results/accepted-source-verification.json). Native commit is `b8375b51a094d3b1217b697989e1ab979f609e64`. This resolves the partial local Git checkout's missing public commit object: provenance rests on the receipt and exact hashes, rather than claiming the local HEAD equals the public SHA.

## Actual plan aggregates, static execution expectations

| Layer | Groups | Fanout histogram | Child WQEs / TAs | Child TPs / Jettys | Total TPs / Jettys | Largest frame / cells |
|---|---:|---|---:|---:|---:|---:|
| L0 | 28 | 1:15, 2:13 | 41 / 755,712 | 82 / 41 | 4,114 / 4,073 | 1,330 B / 9 |
| L37 | 22 | 1:2, 2:11, 3:7, 4:2 | 53 / 976,896 | 106 / 53 | 4,126 / 4,073 | 1,604 B / 11 |
| L52 | 21 | 1:4, 2:11, 3:4, 4:2 | 46 / 847,872 | 92 / 46 | 4,116 / 4,070 | 1,604 B / 11 |

Maximum simultaneous provisioned groups per source are 1/1/2, and children per source 2/4/5, for L0/L37/L52. Every child retains its own native WQE, Jetty, TX/RX TP pair, TA completions, and feedback identity. Source coalescing does not reduce child TA counts. Groups are lifetime operations, not recycled slots.

Expected native request-TA admission and remote target-received/completed event counts are 1,011,456 / 1,229,216 / 1,101,152 across the complete layer. These are static application-event expectations, **not measured ns-3 scheduler event counts**. Source weight-data packet grants are 516,096 / 405,504 / 387,072; multicast envelopes alone are 239,616 / 368,640 / 313,344, with remaining weight packets using the native singleton path. The machine-readable audit records all count definitions and does not estimate total scheduler events.

## Limit checks

- Group registry: at most 128 groups/layer, 63 children/group, and ranks 0–63. Actual maxima are 28 groups and fanout 4.
- Frame formula: singleton `78 + segment`; multicast `32 + 137 × fanout + segment`. Fanout 1/2/3/4 gives 1,102/1,330/1,467/1,604 bytes and 7/9/10/11 CBFC cells.
- Unchanged capacity: 1,048,576-byte ingress reserve, 524,288-byte egress queue, 160-byte credit cells, and 6,553 initial credits/VL. All actual frames fit. Runtime `CheckCapacity` checks every node and port before submission.
- Child TPN maxima: 69,714/69,738/69,724. Jetty ID maxima: 36,905/36,917/36,910. All fit the actual 24-bit wire fields. Each child has 18,432 TAs, below one 65,536-value wire TASSN cycle.
- Native backpressure remains 512 in-flight TAs/Jetty and 1,000 packets/TP; Jetty/TP OOO windows remain 2,048. This audit does not treat total TA count as an inflight requirement.
- Physical expert counts 169/181/174 fit 1,024; 16,384 assignments fit 100,000; logical task/TA counts fit their signed-32/unsigned-32 bounds. The preserved explicit 8-GiB logical-payload and 1,000,000 weight-task budgets pass. Do not substitute the executor's smaller default payload budget.

Sources: [group-manager.h](../ub-concurrent-multicast/group-manager.h#L16-L46), [multicast-integration.inc](../pair-jetty/multicast-integration.inc#L2-L18), [pair-layer.cc](../pair-jetty/pair-layer.cc#L118-L167), and [adapter.h](../ub-lightweight-multicast-adapter/adapter.h), `SharedSource::GetNextPacketSize`. Native paths/line anchors are recorded in [static-capacity.json](results/static-capacity.json): `ub-port.cc`, `ub-queue-manager.h`, `ub-function.cc`, `ub-transport.cc`, `ub-header.cc`, and `ub-switch.cc` under `src/unified-bus/model/` in the verified native tree.

## Memory and protected execution

Logical payload totals are 1,042,284,544 / 1,268,776,960 / 1,136,656,384 bytes. Application payload-array lower bounds are 1,816,133,632 / 2,269,118,464 / 2,004,877,312 bytes. The latter include transfer payload arrays plus replica weight arrays, but exclude transient copies, native payloads, per-segment bookkeeping, allocator overhead, and other process state. **These are lower bounds, not predicted peak or measured RSS.**

Keep the accepted [guard.py](../wqe-completion-fix/guard.py) protections: 3,600 seconds/stage, 6-GiB process-tree RSS, 7-GiB address space, 8-GiB free case disk, 2-GiB free `/tmp`, and 1.5-GiB available host memory. Any unexpected limit, protocol, resource, or correctness failure stops advancement; do not raise limits or change Planner/protocol/configuration.

## Evidence handling

The original private direct-input archives were read and hashed in memory; no raw routing, mapping, request content, or per-child identities are included here. [static-capacity.json](results/static-capacity.json) preserves aggregate statistics, archive/plan/config/assignment digests, source anchors, provenance, formulas, and static estimates. Its weight wire-byte estimates include serialized request-data overhead only and exclude feedback, credit, dispatch, and combine traffic.
