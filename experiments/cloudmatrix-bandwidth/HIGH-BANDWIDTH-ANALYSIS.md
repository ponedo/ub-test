# Why multicast loses to chunk streaming at 3136 Gbps in this model

## Conclusion and scope

The upstream coalescing benefit is preserved, but the measured completion-time advantage reverses. The evidence is consistent with fixed packet-grant service, per-destination native feedback, and coordinated source eligibility becoming more important than upstream wire bytes. Those mechanisms are verified in source; their individual contributions to the slowdown are **not isolated by these summary runs**. This is not evidence that the envelope parser consumes a modeled CPU penalty, nor that hardware multicast necessarily loses at this bandwidth.

The 100-Gbps rows reuse accepted project `3c2275eafea79426a441c819c8b65268492ff08e`; 3136-Gbps rows are the new verified runs. Native source references below identify the restored `bandwidth-native/src/unified-bus/` tree: base `b8375b51a094d3b1217b697989e1ab979f609e64` plus the four accepted patches, with all 109 candidate-file hashes verified against the accepted manifest. See [source-audit.md](source-audit.md) and [source-provenance.json](source-provenance.json).

Evidence links use the aggregate-only published experiment layout under `results/`, not temporary execution paths. Detailed per-node/per-expert/packet and raw host evidence is intentionally private; only the requested final Weight Ready Expert identifier is retained. The analysis is based on read-only inspection; no simulation or protocol changes were made for this investigation.

## Measured comparison

| Metric | Chunk 100 | Multicast 100 | Chunk 3136 | Multicast 3136 |
| --- | ---: | ---: | ---: | ---: |
| Weight phase, ns | 5,150,959.120 | 3,429,284.200 | 552,893.591 | 717,182.855 |
| Layer latency, ns | 5,679,449.313 | 3,957,930.193 | 732,284.971 | 898,435.170 |
| All-host weight payload bytes | 1,000,341,504 | 415,236,096 | 1,000,341,504 | 415,236,096 |
| All-host weight wire bytes | 1,076,539,392 | 498,401,280 | 1,076,539,392 | 498,401,280 |
| Weight header bytes | 76,197,888 | 83,165,184 | 76,197,888 | 83,165,184 |
| Switch-down weight wire bytes | 1,076,539,392 | 1,076,539,392 | 1,076,539,392 | 1,076,539,392 |
| All-network wire bytes | 3,166,460,416 | 2,588,322,424 | 3,166,481,976 | 2,588,417,784 |
| Maximum per-port VOQ-output peak, bytes | 731,474 | 1,188,618 | 284,316 | 567,628 |
| Sum of native CBFC blocked-query counters | 0 | 0 | 0 | 0 |
| Sum of consumed CBFC cells | 24,584,320 | 20,990,080 | 24,584,320 | 20,990,080 |

Sources: [performance.csv](results/performance.csv), [communication.csv](results/communication.csv), and [correctness-aggregate.csv](results/correctness-aggregate.csv). The published evidence contains strategy-level totals and anonymous per-port maxima only; detailed per-node/per-expert/per-packet records remain private. Peaks and credit counters cover the full run, not just the weight phase. A sum of per-port peaks is not a simultaneous occupancy measurement and is deliberately not used here.

At 3136 Gbps, multicast adds 164,289.264 ns to the weight phase and 166,150.199 ns to the layer versus Chunk. About 98.9% of the layer gap is therefore already present at the weight gate. This is timing decomposition, not a causal allocation of individual queue delays.

The identical weight payload/wire counts across rates establish that shared upstream payload did not disappear. Downstream native unicast delivery remains unchanged. The small rate-dependent difference in all-network bytes should not be mistaken for loss of coalescing.

## Timing actually used

The accepted executor [layer.cc](../qwen-roofline-compute/layer.cc):230–237,282–288 sets link rate and propagation but does not override allocator or input-processing latency. Its rate conversion explicitly promotes before multiplication at line 234; line 468 selects picosecond resolution.

- Native `model/ub-switch.cc:80–85`: `InPortProcessingDelay` defaults to **0 ns**. The 10 ns value used by a different earlier PoC is not this experiment's configuration.
- Native `model/ub-switch-allocator.cc:109–118`: `AllocationTime` defaults to **5 ns**, with direct allocation completion enabled.
- Native `model/ub-switch-allocator.cc:187–206,340–367`: allocator episodes select work and schedule a delayed allocation callback.
- Native `model/ub-port.cc:807–842`: actual bytes determine serialization; port ownership, queue service, and completion events are retained.

For scale, a 1102-byte native data packet takes about 2.811 ns on a 3136-Gbps wire, a 1352-byte fanout-four envelope about 3.449 ns, and a 62-byte ACK about 0.158 ns. A fixed 5 ns allocator round is no longer small compared with these serialization times. This does **not** mean every packet necessarily adds 5 ns unoverlapped to a critical path: prefetch, concurrent ports, and event ordering still matter.

## Preserved native feedback and coordinated eligibility

[pair-multicast-v2.h](../ultraep-multicast-integration/pair-multicast-v2.h):57–60 preserves one native round-robin queue slot per pair. Lines 63–71 prioritize native ACK/CNP/retry work and require all member transport heads to be eligible and aligned before the representative pair can emit an envelope. Native `model/protocol/ub-transport.cc:856–869` dequeues CNP/ACK first; lines 2760–2793 preserve transport-window and congestion-control eligibility checks.

Consequently one upstream envelope is not equivalent to eliminating the fanout's native protocol work. The busiest switch output-port total is 162,945 packets for Multicast versus 126,656 for Chunk; ACK/transaction-response-only maxima are 159,072 and 122,640. See [correctness-aggregate.csv](results/correctness-aggregate.csv). These anonymous full-run maxima support a packet-service/feedback hypothesis, but are not stage-local stall-duration counters or simultaneous queue occupancy.

The observed first-send span divided by 18,432 first-send grants is roughly 19.5–20.0 ns for fanout two, 29.2–29.5 ns for fanout three, and 38.9 ns for fanout four. See [multicast-fanout.csv](results/multicast-fanout.csv). This fanout-sensitive cadence is consistent with the retained service and eligibility mechanisms. It does not establish a universal 10 ns-per-destination rule.

The critical final group has fanout four; its first-send completion is **717,330,728 ps** and all weights become ready at **717,383,855 ps**, only 53,127 ps later. The explicitly requested final Weight Ready expert is 7. See [multicast-aggregate.csv](results/multicast-aggregate.csv) and [performance.csv](results/performance.csv). Source/port/group identifiers and detailed group records are not published. The source first-send tail is closely aligned with the weight-ready tail in this run, without identifying a unique causal mechanism.

## Fanout queue service and credit accounting

Native `model/ub-switch.cc:2239–2288` decodes envelopes and reconstructs ordinary native branches. `CompleteNetworkProcessing` at lines 2120–2155 places those branches in output VOQs and triggers the corresponding ports. `UbRoundRobinAllocator::AllocateNextPacket`, `model/ub-switch-allocator.cc:681–785`, grants ordinary queued packets; selection at lines 794–840 preserves RR ordering. One envelope does not bypass independent output grants or make all destinations finish simultaneously.

Native `model/ub-switch.cc:1904–1940` releases the original input reservation after the last branch dequeues, retaining original envelope-byte credit accounting. However, the measured blocked-query sums are zero. Thus a claim that CBFC credit exhaustion caused this particular reversal is unsupported.

Two other plausible bottlenecks are also not supported here:

- All 22 multicast groups were admitted at **201,000 ps**. The reservation mechanism at [pair-multicast-v2.h](../ultraep-multicast-integration/pair-multicast-v2.h):35–41 exists, but there was no delayed group admission in these results.
- The maximum codec association occupancy was **5**, versus **1000** capacity per group. Association-table exhaustion is not shown.

[multicast-aggregate.csv](results/multicast-aggregate.csv) reports 368,640 envelopes, 940,032 reconstructed branches, zero native retry packets, zero injected losses, and zero invalidated test grants. Pending associations drain to zero. These exclude those recorded failure mechanisms, not every possible eligibility delay.

The larger multicast VOQ peaks indicate more retained downstream queue work, but do not isolate its contribution to the tail. Zero recorded egress-residence totals do not imply zero network waiting: packets may wait in ingress/VOQ, allocation, or transport eligibility before egress enqueue.

## What this does not establish about hardware

Envelope encoding and metadata restoration in [adapter-v2.h](../ub-multicast-v2/adapter-v2.h):36–72,74–83 and native decoding/reconstruction at `model/ub-switch.cc:2245–2276` are synchronous C++ work. These loops do **not** carry a calibrated simulated CPU/ASIC latency. The following explicit input-processing delay at lines 2287–2288 is zero in this case. Their host execution cost must not be presented as simulated protocol latency.

Conversely the fixed 5 ns allocator and retained protocol behavior have not been calibrated here to CloudMatrix hardware. The 3136-Gbps setting is a logical aggregate endpoint-capacity assumption, not a verified single-peer physical link. See [HARDWARE-REFERENCE.md](HARDWARE-REFERENCE.md).

Therefore the defensible conclusion is narrow: **in this preserved simulator configuration, upstream wire-byte savings do not guarantee lower completion time at 3136 Gbps**. Summary evidence makes packet/grant/feedback coupling a credible explanation, but does not isolate it from other ordinary scheduling and transport effects. Neither the aggregate-bandwidth idealization nor this crossover alone establishes the hardware ranking. No new tests were run to force or fit an explanation.
