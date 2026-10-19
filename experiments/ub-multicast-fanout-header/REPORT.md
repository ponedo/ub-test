# Single-expert fanout and multicast header sensitivity

**Final measured report, 2026-10-19.** Full multicast first beats Chunk at the first tested non-singleton fanout, F = 2 (1.601×). At F = 8, speedups versus Chunk are 1.988× full, 3.130× compact Oracle, and 3.388× ideal Oracle. The full-header F = 8 case nevertheless increases all-link weight-data bytes by 9.846%. These are conditional single-expert communication results.

**All 20 main cases, five optional ideal cases, and 25 small cases pass. The separate native regression suite is qualified: 48/49 pass, with the known unified-bus-examples missing parse_trace.py postprocessing failure retained.** No campaign case failed or hit a resource guard.

## Question and scope

This controlled experiment asks how replica fanout and charged multicast header bytes interact when distributing one 18 MiB expert weight object. It does not run the placement Planner, token routing, token assignments, or expert compute, and its weight-ready duration is not MoE layer latency. The reused Layer emits zero-duration bookkeeping outside the weight-distribution stage.

The topology is EP64 with one switch, source rank 0, and target ranks 1 through F, for F = 1, 2, 3, 4, 8. All links are 100 Gbit/s with 20 ns delay. The source bytes are deterministic (seed 20261016); each target receives the same 18,874,368 bytes. TA payload size is 1,024 bytes, Chunk size is 4,096 bytes, and the FC1/FC2 shard boundary is 12 MiB. Native VL7, queue capacities, CBFC, transport windows, ACKs, and transaction Responses are retained. Congestion control and retransmission remain disabled under the accepted adapter's scope.

The main matrix contains Direct, Chunk with its original relay policy, full-header multicast, and compact-Oracle multicast at every tested fanout. The optional supplement runs ideal-Oracle multicast only after the main matrix passes its guards. Small 12 KiB cases establish correctness, not the reported large-object performance.

## What each comparison changes

Direct sends a full object separately to each target. Chunk uses the unchanged ChunkStreamingRelay rule: minReplicas = 4, maxRelays = 8, minFanoutGain = 2, forceRelay = false. It falls back to whole-object Direct at F = 1, 2, 3. At F = 4 and 8 the original square-root policy chooses two relays, using real 4 KiB transfers and the original group-chunk readiness dependencies. No forced relay is used to make the comparison more favorable.

Multicast keeps one native child transport and logical WRITE per recipient, coalesces identical outgoing TA payloads into one source packet, and replicates that packet at the switch. A child retains its native window and real ACK/Response path. The group waits for every member's completion.

There is an important implementation boundary: Direct/Chunk use PairJettyManager and rank-pair transport endpoints, while multicast provisions dedicated per-child Jetty/TP pairs and presents their coordinated eligibility through one SharedSource ingress queue. Thus multicast versus Direct/Chunk compares those implemented paths, including their source scheduling. It is not a pure wire-byte intervention. The comparison among full, compact, and ideal multicast at a fixed fanout does isolate the selected header accounting on the same multicast path.

## Header models and their limits

For TA payload P and F > 1, the actual transmitted packet is:

| Model | Charged bytes per packet | At F = 2 / 3 / 4 / 8, P = 1,024 B |
|---|---:|---|
| Full | P + 32 + 137F | 1,330 / 1,467 / 1,604 / 2,152 B |
| Compact Oracle | P + 32 + 16F | 1,088 / 1,104 / 1,120 / 1,184 B |
| Ideal Oracle | P + 32 | 1,056 / 1,056 / 1,056 / 1,056 B |

Every F = 1 case uses the unchanged native P + 78-byte WRITE packet: 1,102 bytes per TA, regardless of header setting. Full is the accepted, byte-complete experimental envelope, not a standardized UB multicast header. Its common 32 bytes include the outer data-link header; each 137-byte member record includes the native prefix and identity tags. Compact carries rank, destination TP, PSN, and SSN explicitly as four 32-bit fields per member. Ideal charges only the common header.

Oracle modes restore omitted native metadata from a bounded, pending-envelope context with zero modeled context installation, control-plane transmission, lookup, or reconstruction time. The context contains metadata and a checksum, never a substitute payload. The receiver reconstructs the native child packet from the actual payload bytes that traversed the network. Context is checked against wire identity/membership and reclaimed after all expected recipients consume it. Compact is a field-budget sensitivity experiment; Ideal is a fixed-common-header lower-cost hypothesis. Neither establishes a deployable or achievable protocol.

The switch retains the selected envelope on every output branch. Packet::GetSize, the allocator's GetNextPacketSize, link serialization, queue accounting, and CBFC cell charging therefore see the selected size. ACK/Response bytes are never discounted, and there is no time adjustment. With 160-byte cells, the full packets above consume 9 / 10 / 11 / 14 cells; compact consumes 7 / 7 / 7 / 8; ideal consumes 7 throughout. Native singleton consumes 7.

## Metrics and interpretation

The primary metric is the simulated time from weights_start to the last target's verified full-weight readiness. Per-target ready times and sender-completion times are retained separately. Sender completion includes the native feedback tail and is not substituted for receiver readiness. Host wall time, CPU time, and RSS describe the cost of running the simulator; they do not describe network latency.

Source weight-wire bytes count the actual source data packets, including their charged headers, but exclude feedback. Network wire totals count transmissions across every traversed link; they are not distinct application bytes. Source payload injection is distinct from the logical bytes delivered to all targets. A multicast object has 18 MiB source payload injection and F × 18 MiB logical receipt.

Bottleneck interpretation uses independently inspected per-port wire bytes, egress peaks/residence, CBFC counters, and multicast window-wait counters. A value 8 × wire_bytes / 100 Gbit/s is an analysis-only serialization service demand. It is not a replacement simulation or a modeled latency correction. Whole-run port totals include final feedback after target readiness, so their serialization demand is only a near-critical-path diagnostic, not an exact lower bound on the ready metric. Data-only source/recipient serialization gives a weaker bound when all those data must precede readiness. Aggregate queue residence is summed packet waiting time and may exceed wall-clock simulated duration.

## Results

### Main 18 MiB measurements

All values below are simulated weight-ready duration in milliseconds. These are completed cases, not extrapolations.

| Fanout | Direct | Chunk, original policy | Multicast full | Multicast compact Oracle |
|---:|---:|---:|---:|---:|
| 1 | 1.717146800 | 1.717146800 | 1.717146800 | 1.717146800 |
| 2 | 3.434179120 | 3.434179120 | 2.145616200 | 1.788585920 |
| 3 | 5.150746360 | 5.150746360 | 2.439771840 | 1.904109040 |
| 4 | 6.866765880 | 4.339078120 | 2.733940640 | 2.020044400 |
| 8 | 13.737089120 | 7.772762240 | 3.910600240 | 2.483188760 |

Speedup is Chunk duration divided by the named multicast duration; above 1 is faster.

| Fanout | Full speedup vs Chunk | Compact-Oracle speedup vs Chunk | Chunk relay behavior |
|---:|---:|---:|---|
| 1 | 1.000× | 1.000× | Direct fallback |
| 2 | 1.601× | 1.920× | Direct fallback |
| 3 | 2.111× | 2.705× | Direct fallback |
| 4 | 1.587× | 2.148× | Two relays |
| 8 | 1.988× | 3.130× | Two relays |

**F = 2 is the first tested fanout where multicast beats Chunk, for both main header models.** F = 1 ties exactly. There is no claim about untested fanouts or a universal crossover. Speedup is nonmonotonic: from F = 3 to F = 4, the baseline activates its original relay policy and becomes faster (5.150746360 to 4.339078120 ms) despite serving another target, while multicast duration increases. The full speedup consequently drops from 2.111× to 1.587×. Connecting these discrete points in a chart must not be interpreted as fitting one continuous crossing curve.

At F = 8, compact Oracle cuts the measured full-multicast duration from 3.910600240 to 2.483188760 ms, with the same payload, native children, and feedback obligations. This is a 36.50% duration reduction. It is header-cost sensitivity under zero-cost omitted context, not an implementation-ready protocol speedup.

### Optional ideal-Oracle supplement

All five optional cases ran after the main matrix passed. They remain a separately labeled supplement.

| Fanout | Ideal-Oracle duration, ms | Ideal-Oracle speedup vs Chunk | Duration reduction vs compact Oracle |
|---:|---:|---:|---:|
| 1 | 1.717146800 | 1.000× | 0.00% |
| 2 | 1.741219000 | 1.972× | 2.65% |
| 3 | 1.833532440 | 2.809× | 3.71% |
| 4 | 1.925466320 | 2.254× | 4.68% |
| 8 | 2.294434800 | 3.388× | 7.60% |

Ideal charges the same 19,464,192 source data-wire bytes for every F > 1, yet duration still rises with fanout because the native per-recipient feedback remains. At F = 8 its source transmits another 9,142,272 B of ACKs. Removing the compact per-member wire fields thus does not remove fanout cost. Ideal is the first-tested F = 2 winner as well; its F = 1 path remains exactly native.

### Source payload, wire headers, and feedback are different quantities

Each large object is exactly 18,432 TAs. Direct injects F copies of the payload; Chunk injects F copies at F = 1, 2, 3 and two copies at F = 4, 8; multicast injects one copy in every case. Source data-wire bytes additionally charge the actual header. F = 8 is particularly revealing:

| F = 8 mode | Source payload B | Source charged header B | Source data-wire B | Source ACK-wire B | Source all-wire B |
|---|---:|---:|---:|---:|---:|
| Direct | 150,994,944 | 11,501,568 | 162,496,512 | 9,142,272 | 171,638,784 |
| Chunk | 37,748,736 | 2,875,392 | 40,624,128 | 2,285,568 | 42,909,696 |
| Full multicast | 18,874,368 | 20,791,296 | 39,665,664 | 9,142,272 | 48,807,936 |
| Compact Oracle | 18,874,368 | 2,949,120 | 21,823,488 | 9,142,272 | 30,965,760 |
| Ideal Oracle (supplement) | 18,874,368 | 589,824 | 19,464,192 | 9,142,272 | 28,606,464 |

These are reconciled packet counters. Source ACKs are actual 62-byte native ACK packets acknowledging the transaction Responses. At F = 8, multicast still sends 147,456 source ACKs, versus 36,864 from Chunk's main source; Chunk's relay senders carry the remaining native transaction traffic. Each direct/multicast target sends 18,432 transaction Responses plus 18,432 transport ACKs. Counting all transmitting links gives 294,912 Responses and 589,824 transport ACKs in every F = 8 strategy. Credit frames can differ with cell accounting; they are included in all-network totals.

Full multicast saves 75.59% of source data-wire bytes versus Direct at F = 8, but only 2.36% versus Chunk. Once native source ACKs are included, full multicast sends more total source wire bytes than Chunk. Source payload reduction alone is therefore an insufficient explanation of its 1.988× measured improvement over Chunk.

| F = 8 mode | All-link weight-data B | All-network wire B, including feedback/credits |
|---|---:|---:|
| Direct | 324,993,024 | 379,846,656 |
| Chunk | 324,993,024 | 379,846,776 |
| Full multicast | 356,990,976 | 411,884,928 |
| Compact Oracle | 196,411,392 | 251,270,784 |
| Ideal Oracle (supplement) | 175,177,728 | 230,031,360 |

**Full multicast increases all-link weight-data bytes by 9.846% versus Direct/Chunk at F = 8 even while reducing completion time.** Every switch branch retains the 2,152-byte full envelope. Compact instead uses 1,184-byte packets. Total network bytes, the most loaded port, and the dependency critical path are distinct objectives.

### Source versus recipient and relay bottlenecks

The following service demands come from independently inspected complete-run port counters, using 8B / 100 Gbit/s. They are analysis-only diagnostics, with the final-feedback caveat stated above.

| F = 8 mode | Source transmit demand, ms | Max relay transmit demand, ms | Max switch-to-target demand, ms | Measured weight readiness, ms |
|---|---:|---:|---:|---:|
| Direct | 13.731102720 | — | 1.716387840 | 13.737089120 |
| Chunk | 3.432775680 | 5.332008960 | 2.264924160 | 7.772762240 |
| Full multicast | 3.904634880 | — | 3.264675840 | 3.910600240 |
| Compact Oracle | 2.477260800 | — | 1.837301760 | 2.483188760 |
| Ideal Oracle (supplement) | 2.288517120 | — | 1.648558080 | 2.294434800 |

Direct and the main multicast cases are close to source serialization demand in this single-source fixture. Multicast's larger envelope increases every recipient's link cost too, but the source must additionally transmit all recipients' native ACKs, leaving its transmit demand larger than an individual output branch. In F = 8 Chunk, each of relays 1 and 2 forwards three full objects. Each relay transmits 66,650,112 total bytes, compared with the main source's 42,909,696. The relay/dependency path is material; the measured end time is not set by the main source alone.

No main or ideal case records a CBFC-blocked query, and multicast window-wait query counters are zero throughout both matrices. This does not mean feedback, cells, or windows were removed or that they can never constrain this adapter. At F = 8, observed peak egress occupancy is 2,204 B for Direct/Chunk, 4,304 B for full multicast, and 2,368 B for compact, within the unchanged 524,288-byte port egress capacity. Queue residence remains an aggregate waiting statistic, not a separate latency added to the table.

### Chunk readiness is part of the measured path

The F = 4 task timeline shows all 9,216 source WQEs submitted at the common 1 ns start, but the first complete 4 KiB group releases a relay at 2.575853960 ms after that start, 59.36% of the eventual 4.339078120 ms weight duration. The two relays become fully weight-ready at approximately 3.434 ms; the leaf targets finish near 4.339 ms. The source's entire-run serialization service demand is 3.432775680 ms, so a source-byte-only calculation does not reproduce Chunk's completion time. At F = 8 the first relay release is the same 2.575853960 ms after start, 33.14% of the 7.772762240 ms weight duration; relays finish receiving by about 3.836 ms while the last leaf completes at about 7.773 ms.

The bounded 12 KiB legacy-parity Debug fixture confirms interleaved native admissions: on the source-to-rank-1 Jetty, tasks 0, 2, and 4 each admit their first 1 KiB TA before task 0's second TA, and similarly across later offsets. The first chunk is therefore not necessarily completed before later chunks begin. The 18 MiB Summary logs preserve task submission/readiness/latest-TA-completion and online exact-once checks, not a full persisted per-TA trace, so they do not establish every detailed admission order of the larger run. These observations describe the unchanged native scheduling and GroupChunk gate. They are not a new protocol-bug finding, and this experiment does not optimize WQE submission, ordering, or relay release.

## Relation to the earlier real-routing L0 result

The earlier [real-routing campaign](../qwen-real-multicast/REPORT.md) retained a negative L0 result: full multicast weight readiness was 4.101682080 ms versus Chunk 3.436510640 ms, and final layer latency was 2.81% worse. That workload had 28 concurrent multicast groups (15 singletons and 13 F = 2 groups), 41 replica children, and a global gate over all replica weights before later token/compute phases. Its last receivers each needed two F = 2 weights. The current fixture has one expert, one source, one group, one object per target, and no tokens or compute.

Those are different load placements and bottlenecks. In the earlier L0 case, the critical recipient link carried two enlarged envelopes per TA position; in this fixture the single source must inject separate copies for Direct/Chunk fallback, while multicast coalesces them. A positive single-expert F = 2 result therefore does not overturn the earlier L0 regression. This campaign does not rerun L0 with compact/ideal headers and cannot establish that a header change would remove its regression. Source endpoint/scheduling differences and the lack of an endpoint-matched unicast ablation also prevent a universal header-only causal claim.

## Correctness, resource guards, and reproducibility

The [validation summary](results/validation-summary.json) confirms that the main 20, optional five, and small 25 cases all pass native/online checks and independent postflight. The [combined performance export](results/performance.csv) contains 50 rows with an explicit block field; [main-performance.csv](results/main-performance.csv) has only the 20 main measurements, [ideal-performance.csv](results/ideal-performance.csv) only the five supplements, and [small-performance.csv](results/small-performance.csv) only correctness fixtures. No point is stopped, omitted, or imputed in these matrices.

Online validation checks received payload bytes and individual TA exact-once/order, identity, full coverage, and target/sender gates. Summary-mode independent postflight checks the persisted per-WQE counts/bytes/latest TA completion and received-buffer SHA256, exact graph/dependencies, all-rank coverage, actual packet/feedback budgets, all 128 ports' packet/cell conservation, queue capacity/drain, and native-window drain. It does not independently replay every TA from a full-size packet log because those logs were deliberately not persisted. All large targets match source SHA256 d975935d55e82455d8c90c34d4bbb8a7e2ec6faa67921d9280471293287e0049. Omitted Oracle metadata drains to zero; at F = 8, both Oracle modes peak at four pending envelopes / 4,128 retained native-metadata bytes, with no payload stored in that context.

Pre-campaign checks pass: 25 small combinations; four old/new Debug parity pairs (singleton, Direct F = 4, Chunk F = 4, full multicast F = 8) with byte-exact events, wire, identity, task/target and network evidence; 39 header-codec tests (three positive, 36 intentional rejection tests); 17 injected-fault rejection tests; and [38 independent-verifier unit tests](results/verifier-tests.json). The frozen verifier also rechecks all 25 small runs and eight old/new parity runs. The separate [header pressure suite](results/header-pressure-tests.json) also completes all 21 cases: 12 positive cases and nine expected feedback rejections across the three header modes. A native two-packet-window fixture reaches exactly two outstanding packets and records 134 window-wait checks in every mode. A separate 1,600-byte-queue pressure fixture records 582 / 512 / 510 CBFC-blocked queries for full / compact / ideal, while checking actual packet serialization/cells, payload SHA256, member/group causality, and credit/window/context drain. Missing, duplicate, and wrong-member feedback are rejected. These are correctness-only changed-resource fixtures in a separate executable; they do not change the performance binary/defaults or enter the performance curves. Zero main-run waits are therefore not being used as the only evidence that the constraints are enforced.

The separate [prior/native regression summary](results/regressions-summary.json) records **PASS_WITH_KNOWN_NATIVE_SUITE_FAILURE**, not an unqualified native-suite pass:

- Native tests: **48/49 pass**. The sole failure is the known unified-bus-examples TaskTimes postprocessing failure due to missing parse_trace.py, also present in the accepted baseline. It is retained and disclosed, not suppressed.
- Four prior application arms (No Balancing, Direct, Two-Stage Relay, and Chunk Streaming) match every simulated summary field exactly.
- Concurrent multicast: five positive cases pass and four expected-negative cases reject.
- Singleton: seven exact parity pairs pass.
- Prior multicast: five positive cases pass and three expected-negative cases reject.
- All five verifier mutations are detected.
- Network replication: 13 positive cases pass and four expected-negative cases reject; two additional capacity-overflow cases reject.

Expected-negative cases establish rejection behavior; they are not failed performance runs. The native postprocessing failure does not change the 50-case campaign's passing simulator/online/postflight outcomes.

All 100 campaign guarded stages (simulation and postflight for 50 cases) pass without a resource stop. The slowest and largest recorded simulator stage is F = 8 Chunk: 694.073 s host wall, 693.585 s host CPU, and 519,424 KiB process peak RSS (0.495 GiB). F = 4 Chunk takes 225.878 s host wall. These are measured host costs, not simulated transfer times; no CPU-cause profiling was performed. Protections remain 3,600 s per stage, 6 GiB process-tree RSS, 7 GiB address space, at least 8 GiB case-disk free, 2 GiB temporary-disk free, and 1.5 GiB available host memory. No throughput, ordering, or resource-limit optimization was applied to shorten the campaign.

The results are deterministic single executions of this frozen scenario; they do not measure hardware variation, confidence intervals, different topologies/link rates, multiple experts, destination skew, production context setup, congestion control, or retransmission. A dedicated-endpoint unicast ablation is absent. They support a conditional single-expert result and a header-cost sensitivity curve, not a general MoE-layer or hardware speedup.

## Evidence and reproduction

Native source remains pinned to b8375b51a094d3b1217b697989e1ab979f609e64, with the experiment based on accepted application delivery b2b990d1fea69f7e1a1e7ed615494f821aa71913. The [native source hashes](native-source-sha256.json) and [unchanged execution-source hashes](unchanged-execution-source-sha256.json) define the protected sources. The isolated fixture and header-cost treatment do not change the original relay policy, native transport implementation, or default resources.

Source and methodology: [experiment plan](experiment-plan.md), [header models](HEADER_MODELS.md), [harness](fanout.cc), [independent verifier](verify.py), [command manifest](command-manifest.yaml), and [run ledger](run-ledger.md).

Measured aggregates: [main performance](results/main-performance.csv), [ideal supplement](results/ideal-performance.csv), [per-target timing](results/targets.csv), [packet kinds](results/packet-kinds.csv), [port/credit counters](results/port-counters.csv), [queue counters](results/queue-counters.csv), [header/context accounting](results/header-accounting.csv), [host resources](results/host-resources.csv), and [run status](results/run-status.csv).

Charts: [weight duration](results/weight-duration.png), [speedup versus Chunk](results/speedup-vs-chunk.png), [main-source weight-wire bytes](results/source-wire-bytes.png), and [main-source charged headers](results/header-overhead.png). The last two charts exclude source feedback; the source-budget table above includes it. Lines connect tested points only.

No full-size payload, packet dump, or private workspace path is part of this public report.
