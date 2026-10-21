# Controlled ablation of the 3136 Gbps multicast reversal

**Six-cell analysis completed 2026-10-21.** All six formal cells and the 428-case regression gate passed. All durations below are simulated time unless labeled host execution time. Changed-window results are controlled ablations, not original Multicast v2 performance.

## 1. Main findings

1. **Increasing the Jetty window helps MC modestly, but does not reverse the ranking.** Against its own fresh 512 baseline, MC weight time falls 2.641184% at 1024 and 3.955758% at 2048. Full LayerLatency falls only 0.349907% and 1.343416%. Chunk is unchanged at both windows. MC remains slower than same-window Chunk by 145.347144 and 135.919245 µs in the weight phase, respectively. This is the total causal effect of the parameter change in this fixed simulator/workload, not a unique mediator share.
2. **The original reversal reproduces exactly.** Fresh 512 runs give 552.893591 µs for Chunk-Streaming and 717.182855 µs for MC weight completion, the accepted 164.289264 µs gap. Full online summaries, excluding verifier host-runtime noise, and ordered expert/readiness artifacts reproduce accepted baselines exactly.
3. **Feedback service supplies a rigorous baseline model constraint.** Audited admission and protocol rules require at least 143,360 distinct return packets through switch 64 / egress 3 before final admissions in original group 8. Serialized original 5 ns allocation requires at least 716.8 µs inside its measured 717.182855 µs weight phase. This conditional necessary-service bound is specific to the one-logical-port model, not hardware throughput, fitted mediation, or an A result. Its 0.382855 µs gap to observation is not an achievable-gain claim.
4. **A is stopped, with no measured performance benefit.** Immediate suppression of a no-candidate callback reverses cross-TP arbitration order in the native RR/CBFC witness even with unchanged 5 ns service. This fails the required semantics-preservation condition. It is not an intra-TP reliability failure and does not rule out every future scheduler optimization.
5. **The simple hard-1000 plateau hypothesis is falsified.** MC improves another 9.427899 µs in weight time from 1024 to 2048, and all four source-3 Jetties actually reach 2048 outstanding TAs. The separate 1000-entry native retained-segment/PSN capacity can still be observed on selected request paths; it is not a 1000-TA-response limit. Actual fullness, a bounded TAACK→slot-release→admission cycle, and sustained return-port queueing support the coupled feedback/admission mechanism without uniquely isolating its elapsed-time contribution.

## 2. Controlled design and gates

Experiment overview: [README](../README.md). Native audit: [SOURCE-AUDIT](../native/SOURCE-AUDIT.md). Verified gate and host-resource evidence: [JSON](../validation-resource-summary.json), [CSV](../validation-resource-summary.csv). These host measurements are distinct from simulated latency.

Accepted repository reference: `b149fdd4d40d72791a84b788443b0450c41f6180`.

The six formal cells are the Cartesian product of Jetty capacity {512, 1024, 2048} and {Chunk-Streaming, Multicast v2}. All retain the original allocator and its RR priorities/order/service. The workload, inputs, logical transfer graph, Planner, routing, topology, 3136 Gbps links, 20 ns propagation, native MTU 4096 B, TA size 1024 B, WQE/admission implementation, ACK policy, TP packet window 1000, retained WQE-segment capacity 1000, ACK bitmap 2048 and Roofline compute model remain fixed. Both A and B begin from their independent original baselines; A and B are never combined.

**Model boundary:** 3136 Gbps is modeled as one logical aggregate port, while that port retains the original single-frame 5 ns allocator pipeline. This permits at most 200 million successful packet callbacks per second, whereas a 62-byte ACK has 158 ps of modeled serialization at this rate, about 31.6 times shorter than allocation service. Bitrate and packet-service capacity are not scaled together, so higher bitrate alone need not proportionally shorten this workload. This is a property of the audited abstraction, not a claim about CloudMatrix384 hardware ACK throughput or multicast capacity. It does not establish that 14 physical UB ports share one 5 ns pipeline. This round does not change AllocationTime, port count or any other fixed model parameter; the window sensitivity likewise is not a measurement of real-hardware capability.

The stage gate passed 428 cases: 224 small, 42 fault, 28 negative, 21 invalid-rate, 30 invalid-window, 12 invalid-capacity, 7 maximum-capacity and 64 legacy cases. Native/model boundary and observer invariant tests also passed. At 512, accepted/default-OFF/observer-ON event order is exact. At 1024 and 2048, OFF/ON comparisons are independently exact at the same window. Equal-window summaries match after excluding only verification host runtime.

The fresh baseline cases passed the full accepted-summary and ordered expert-compute/expert-ready/replica-ready parity checks, against both accepted diagnostic and original bandwidth references. Correctness, source/binary/input identity, resource and passive-observer gates passed for every treatment before final analysis.

**Attempt provenance:** the first 2048 MC execution lost its executor/session connection and did not produce a complete result. The exact infrastructure cause is unknown; this is not a demonstrated simulator correctness or resource-guard failure. The original interrupted tree is preserved unchanged. After termination checks and revalidation of the five PASS cases and frozen identities, exactly one unchanged final-cell retry began at 07:29:03 UTC in a separate recovery root. The first five cases were referenced read-only; the final case used a fresh physical directory. The retry and resolved six-cell ledger passed at 07:44:50 UTC. Lineage verification confirmed unchanged frozen identities, unchanged first-five outputs, and an untouched interrupted attempt. Only the six resolved PASS cells are analyzed; incomplete outputs are excluded. Host execution/resource results and complete identity provenance accompany the experiment separately.

This is a deterministic fixed-workload simulator experiment. Six cells are not six statistical replicates; no population confidence interval or significance claim is appropriate. There is no additional 100-Gbps formal matrix or parameter search.

## 3. Original baseline, kept separate from ablation results

| Original default-window strategy | Jetty TA capacity | Weight phase (µs) | Full LayerLatency (µs) | Fresh parity |
| --- | ---: | ---: | ---: | --- |
| Chunk-Streaming | 512 | 552.893591 | 732.284971 | Exact PASS |
| Multicast v2 | 512 | 717.182855 | 898.435170 | Exact PASS |

Original MC−Chunk weight gap: **164.289264 µs**. Original full-layer gap: **166.150199 µs**.

Weight phase is `weights_end − weights_start`; its endpoint is receiver WeightReady, not completion of all source-side response cleanup. Full LayerLatency is reported separately. Because the Jetty parameter is global, later dispatch/combine timing can also change under B; the full-layer change must not automatically be attributed entirely to the weight phase.

## 4. A: semantic-preservation stop

The bounded native-linked RR/CBFC witness retains 5 ns allocation service and uses the accepted native implementation. With the original empty callback present, committed order is A at 10 ns, then B at 25 ns. With immediate no-candidate suppression, order becomes B at 6 ns, then A at 11 ns. The empty callback coalesces arrivals before its later selection; removing it changes which TP is selected first.

The verified conclusion is that **this proposed suppression is not semantics-preserving at the cross-TP shared-port arbitration level**. It is a scheduler-unit witness, not a physical WRITE correctness or layer-latency experiment. A remains STOPPED / UNSUPPORTED_SEMANTIC_PRESERVATION, `measured=false`. No formal A cell or A+B combination exists. Native unit callback times are not a model of achievable application speedup.

## 5. B: paired intervention effects, all six cells PASS

| Window | Chunk weight (µs) | MC weight (µs) | Chunk change vs own 512 | MC change vs own 512 | MC−Chunk gap (µs) | Weight DID (µs) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 512, original baseline | 552.893591 | 717.182855 | 0 | 0 | 164.289264 | 0 |
| 1024, intervention only | 552.893591 | 698.240735 | 0 | −18.942120 µs (−2.641184%) | 145.347144 | −18.942120 |
| 2048, intervention only | 552.893591 | 688.812836 | 0 | −28.370019 µs (−3.955758%) | 135.919245 | −28.370019 |

For each strategy, report absolute time change, relative change and speedup against that strategy's own fresh 512 baseline. For each common changed window, weight DID is `(MCw−MC 512)−(Chunkw−Chunk 512)`, equal to the change in the MC−Chunk gap. Negative DID means a relative shift in multicast's favor, which can be caused by multicast improving, Chunk worsening, or both; therefore within-strategy effects are mandatory alongside DID.

| Window | Chunk layer (µs) | MC layer (µs) | MC layer change vs own 512 | Layer DID (µs) | MC weight speedup vs own 512 | MC layer speedup vs own 512 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 512, original | 732.284971 | 898.435170 | 0 | 0 | 1.000000× | 1.000000× |
| 1024, intervention | 732.284971 | 895.291479 | −3.143691 µs (−0.349907%) | −3.143691 | 1.027128× | 1.003511× |
| 2048, intervention | 732.284971 | 886.365447 | −12.069723 µs (−1.343416%) | −12.069723 | 1.041187× | 1.013617× |

Chunk's layer change is zero and its within-strategy speedup is 1× in every cell. Same-window MC/Chunk weight-time ratios are 1.297144, 1.262884 and 1.245833; layer-time ratios are 1.226893, 1.222600 and 1.210411. Ratios above 1 mean MC is slower. No cross-window comparison is presented as original algorithmic performance, no favorable cell is omitted, and no percentage of the original gap is assigned to an unisolated mediator. See `data/timing.csv`, `data/contrasts.csv` and Figures 1–2.

### Why weight and layer gains differ

The postweight wall interval grows 181.052315→196.850744 µs, an increase of 15.798429 µs. The latest node compute-batch start remains node 3 and moves 776.243381→776.821261 µs, 0.577880 µs later in absolute time despite dispatch opening 18.942120 µs earlier. The dispatch envelope therefore grows 58.859526→78.379526 µs (+19.520000 µs). Node 3's compute-batch span remains 98.901689 µs. The final cut from latest node compute-batch end to layer end shrinks 23.291100→19.569529 µs (−3.721571 µs).

The node-level `compute_start` event is emitted once before serial expert scheduling, and `compute_end` follows the summed node work (`../layer.cc:399–405`). These landmarks are not the latest individual expert start: at 2048, node 3 begins its batch at 767.895229 µs but its last expert begins at 822.253409 µs. These are disjoint event-landmark cuts: weights_end→latest node compute-batch start→latest node compute-batch end→layer_end. They account arithmetically for the endpoint difference but are not additive dispatch+compute+combine stage latencies. The actual stage envelopes overlap; compute and combine for other nodes occur inside these cuts.

There is specific support for residual weight feedback overlapping dispatch. At WeightReady, each source 3 member has 511 outstanding TAs at 512, versus 999 at 1024, adding 1952 unacknowledged TAs across the four members. Whole-lifecycle weight-return work is unchanged 147456 frames. The weight-phase RX count drops 143372→139468, leaving 4084→7988 feedback frames not yet received; corresponding not-yet-transmitted counts are 4080→7984. The 3904 additional residual frames correspond to 19.520 µs of total nominal allocation-service demand at the original 5 ns per frame, numerically equal to the dispatch-envelope increase. This is not an exact measurement of added postweight allocator wall time: each phase ends with one callback pending, and total successful callback counts can include other traffic. The last selected source 3 weight TAACK shifts 776.120728→776.698608 µs, also 0.577880 µs later, and precedes node 3 compute-batch start by 122.653 ns in both cases. This is strong conservation/timing support for shared feedback contention, not a direct measured postweight port partition or unique mediation proof: the intervening native per-packet stream is not retained.

At 2048 the postweight interval is 197.352611 µs, 16.300296 µs longer than baseline, leaving a 12.069723 µs full-layer gain from the 28.370019 µs weight gain. The three disjoint postweight cuts are 78.881393, 98.901689 and 19.569529 µs. Source 3 has 5,766 outstanding weight TAs at WeightReady: 1,432 each toward 5/13/52 and 1,470 toward 59. Of the same 147,456 lifecycle feedback frames, 9,713 have not yet transmitted and 9,717 have not reached source 3. These are different boundary states, not lost work.

Crucially, node 3 starts its compute batch at 767.895229 µs in the 2048 case, before the last selected source-3 weight TAACK at 776.242576 µs. Final weight-response cleanup is therefore **not a universal dispatch/compute gate**. Earlier receiver readiness changes overlap and residual traffic rather than eliminating feedback work. This also prevents treating the 1024 numerical 19.520 µs equality as uniquely proven mediation. See `feedback/postweight-landmarks.csv` for exact disjoint cuts; do not add overlapping dispatch/compute/combine envelopes.

## 6. C: direct Jetty state and TAACK progress

Fresh baseline evidence for fixed source-3 pairs:

| Strategy | Source→target | Whole-observed peak outstanding TAs | Weight-phase full-window exposure (µs) | Weight-phase exposure (µs) | Full fraction |
| --- | --- | ---: | ---: | ---: | ---: |
| Chunk | 3→5 | 16 | 0 | 552.893591 | 0% |
| Chunk | 3→13 | 16 | 0 | 552.893591 | 0% |
| MC | 3→5 | 512 | 617.379728 | 717.182855 | 86.0840% |
| MC | 3→13 | 512 | 621.349728 | 717.182855 | 86.6376% |
| MC | 3→52 | 512 | 625.319728 | 717.182855 | 87.1911% |
| MC | 3→59 | 512 | 653.434728 | 717.182855 | 91.1113% |

The peak column is whole-observed-run scope, not an invented weight-only maximum. The full-window fraction is exact transition-integrated occupancy at `ssn_next−ssn_una = window` over the stated phase exposure, not sampling or a sum of failed queries. These per-Jetty intervals overlap. They cannot be added to each other or treated as a share of weight latency. Full capacity need not mean the physical source has no packet to send: already admitted work can still transmit.

At the last retained weight-phase observations, all four MC member Jetties have `ssn_next=18432`, `ssn_una=17921`, hence 511 outstanding. This directly agrees with the native response frontier. All 4021 tracked Jetties in each fresh baseline drain to zero terminal outstanding state. Global occupancy errors, rejected TAACKs and cleanup-event counters are zero. Within the selected detailed ACK-correlation coverage, unmatched accepted ACKs and duplicate-TAACK counters are also zero. The final unacknowledged weight TAs can complete after receiver WeightReady without invalidating the receiver endpoint.

**Global context:** 15 Chunk Jetties and 53 MC Jetties have positive weight-phase full exposure. Both strategies reach a global peak of 512. The source-3 control therefore does not establish that Chunk globally has no Jetty bottleneck.

A bounded fresh cycle directly connects feedback to final admission. On 3→59, a full-window query at absolute time 717.300728 µs records next=18431 and una=17919. At 717.320728 µs, TAACK SSN 17919 is accepted and advances una to 17920. Two eligible tests and admission of final SSN 18431 follow in the same retained Jetty event order, restoring occupancy 512. The releasing ACK is independently matched from switch egress 3 TX at 717.300570 µs to source RX at 717.320728 µs. The final TA's first native pop and physical TX occur at 717.330728 µs, before receiver WeightReady 717.383855 µs; its own TAACK completes only at 776.120728 µs. Six selected Jetty events, four selected native events and one TA sample establish this local release/admission sequence. They do not establish a global no-send interval or assign a unique mediator share. Equal-time ordering is preserved within each stream; cross-stream linkage also uses the audited handler semantics. The release packet's switch VOQ pop is retained, from ingress 59/VL7 with 1018 packets remaining at 717.300570 µs. Its matching push predates the retained native weight ring, which spans 714.805728–717.383855 µs; exact residence for this particular packet is unavailable. Aggregate queue means must not be substituted for that censored interval.

### Explicit latency boundaries, fixed source 3→59 weight-TA cohort

| Window | Admission→accepted TAACK mean (µs) | Native pop→accepted TAACK mean (µs) | Physical TxStart→accepted TAACK mean (µs) | Physical-boundary maximum (µs) |
| --- | ---: | ---: | ---: | ---: |
| 512 | 20.575614 | 20.551683 | 20.551683 | 58.790000 |
| 1024 | 35.448688 | 35.404544 | 35.404544 | 78.595000 |
| 2048 | 67.716749 | 67.659066 | 67.659066 | 118.960000 |

Each row contains the same 18,432 selected weight TAs, with no missing native-pop or physical-TX correlation. Pop is not defined as TX even though these means coincide here. Physical TxStart→TAACK includes network, receiver execution and return arbitration, not pure propagation RTT. ACKs can finish after WeightReady. The `all_pairs` latency row in the CSV means all **selected** TAs: MC source 3 and Chunk prespecified sources 3/36/50, not all network pairs. Unequal selected-source aggregates are not a matched global RTT comparison.

Terminal coverage is checked afresh: Chunk remains tied at 36→17 and 50→27 in all windows; MC has 3→59 at 512/1024, and all four 3→{5,13,52,59} tie at 2048. Every actual terminal source remains inside the fixed selectors; the 2048 target tie is not concealed. Fixed 3→59 latency remains a same-pair control rather than being relabeled the sole 2048 terminal. See `data/critical.csv` and `feedback/terminal-coverage.csv`.

## 7. C: return-port feedback, not just forward egress 59

Switch 64 / physical egress 3 connects to source NPU 3. The baseline MC group has four receivers, 5/13/52/59, each requiring 18,432 one-packet WRITE TAs. Each request produces a native transport ACK (TPACK) and its TAACK transaction response. Therefore a whole-lifecycle envelope sequence produces eight return frames. The source's outgoing traffic is one envelope plus four ACKs for the returning TAACKs, a different five-frame direction. Link-credit control traffic is separate.

Whole-lifecycle physical opcode counts corroborate this direction and multiplicity: after separately accounting for the known token workload, switch egress 3 has 73,728 weight TPACKs and 73,728 weight TAACKs in MC, versus 36,864 of each in Chunk. This is not the same cohort as packets ending inside the weight phase.

| Fixed return port 3, weight phase | Chunk | MC |
| --- | ---: | ---: |
| ACK-response TX frames | 73,728 | 143,376 |
| ACK-response RX frames at source 3 | 73,728 | 143,372 |
| TX busy union (µs) | 11.649024 | 22.653408 |
| Allocator pending excluding TX (µs) | 357.006134 | 694.260193 |
| Uncovered idle (µs) | 184.238433 | 0.269254 |
| TX-or-allocation fraction | 66.6774% | 99.9625% |
| ACK-response VOQ mean (µs) | 0.114974 | 18.653856 |
| ACK-response VOQ maximum (µs) | 0.136873 | 20.367492 |

The first three time components form an exact disjoint partition of the respective phase. VOQ means/maxima describe full packet residence cohorts; packet-time sums overlap and are not another latency component. Four MC return frames are still on the last link at WeightReady, accounting for TX minus RX. Eight bounded matched late packets identify four TPACKs and four TAACKs; their physical TX→RX difference is 158 ps serialization plus 20,000 ps propagation.

At 1024 and 2048, source 3 remains MC's actual terminal source. Port 3 active fractions are 99.895975% and 99.987454%, while ACK-response VOQ means increase to 25.493833 and 37.603647 µs; maxima are 39.903424 and 39.893424 µs. Lower weight completion time therefore does not require shorter queue residence or TA response latency. These are accompanying mechanism observations, not additive latency attributions. Figure 5 separates the exact resource partition from overlapping packet residence.

The fixed-port comparison does not make source 3 critical for Chunk. Chunk's tied terminal sources are 36 and 50; their return ports each have 552.812811 µs active union and 0.080780 µs idle within the 552.893591 µs phase. All treatment comparisons retain this distinction between fixed controls and actual terminal sources.

### Conditional necessary-service proof

Before each of the four members admits its final TA, its 512-entry Jetty requires at least `18432−512=17920` contiguous TA retirements. Each retirement requires its own accepted TAACK; cumulative transport ACKs do not retire a WRITE that requires a transaction response. Every such TAACK is generated only after that request's distinct native TPACK has been enqueued. Audited source ACK priority, FIFO egress, link serialization, equal priority and the same switch `(egress 3, VL7, ingress-target)` FIFO prevent the TAACK from overtaking its own TPACK.

Consequently, at least `4×17920×2=143360` distinct frames must traverse switch egress 3 before the final admissions. Each uses a distinct original 5000 ps allocator interval, with at most one pending allocation per physical output and one frame committed per callback. The intervals do not overlap. The request and return path includes at least three 20 ns propagation links, so even the earliest required callback's full 5 ns interval lies after weights_start; each interval ends before the corresponding TAACK is accepted and before final admission. All counted intervals are therefore inside the weight phase.

This establishes **weight time ≥716.8 µs** for this audited baseline model with one logical aggregate return port and its unchanged single 5 ns allocator pipeline. It is not a hardware multicast or feedback-throughput limit. Measured time is 717.182855 µs. The 0.382855 µs difference is merely observed time minus a lower bound. It is not an additional causal component, an achievable reduction, a proposed optimization result, or an A result.

The proof is conditional on the same work, 512 capacity, path/order, one request TPACK plus one TAACK without aggregation or cleanup/cancellation, and original nonoverlapping 5 ns service. It does not automatically predict B by substituting a larger window into the expression, and it does not identify a unique percentage of the MC−Chunk gap. An independent source challenge review passed these counting, ordering and temporal-containment obligations.

## 8. Capacity migration: observed states, falsified plateau, and limits

The preregistered prediction allowed a plateau because the TP packet window and retained WQE-segment capacity remain 1000. **A hard 1024→2048 plateau is not observed:** MC weight time improves another 9.427899 µs and layer time another 8.926032 µs. All four source-3 Jetties reach the actual configured TA window, including 2048. These TA SSN states are distinct from request-TP packet PSNs and retained segments; a 2048 outstanding-TA state does not contradict a 1000 request-segment cap.

| MC window | Source3→5 full exposure (µs) | →13 | →52 | →59 | Whole-observed peak per pair |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512 | 617.379728 | 621.349728 | 625.319728 | 653.434728 | 512 |
| 1024 | 108.706032 | 108.746032 | 108.786032 | 150.307608 | 1024 |
| 2048 | 5.060000 | 5.060000 | 5.060000 | 27.895000 | 2048 |

Exposure is phase-clipped, while peak and full-interval count/maximum fields are whole-observed-run scope. Source3 Chunk controls 3→5/13 remain peak 16 with no full exposure at every window. Figure 3's source-3 aggregate is pair-exposure-weighted and uses each strategy's source-3 pair set, not a claim that all Chunk Jetties behave like these controls.

The native retained-segment gate can return before another admission; an already-admitted final unsent TP packet can drain so TpEmpty becomes true before the allocator reaches its packet-window reason branch. In the 1024 retained tail (696.078608–698.441735 µs), reserved-unacknowledged PSN slots reach 1000 on all four source-3 request TPs. Empty=true at 1000 occurs 174 times toward 52 and 290 toward 59. In the 2048 tail (686.622576–689.013836 µs), targets 5/13/52 reach 1000, with empty=true at 1000 observed 249 times toward 13 and 430 toward 52. **Target 59 reaches only 985 in this retained tail**, with no 1000 state recorded there. These observations are source/pair/time-local; they cannot be generalized to every terminal request path or the full run.

`tpPsnCnt−sndUna` exactly counts reserved unacknowledged PSN slots. On the audited one-packet-per-TA request path without cancellation/force removal, it lower-bounds retained segment count. Equality requires proven post-cleanup/quiescent observation: callbacks can re-enter after UNA advances but before segment erasure. A value 1000 nevertheless proves retained saturation under cap 1000. It does not prove the retained gate was evaluated at that observation, pending work was blocked, a blocking duration, or a unique cause of the B outcome. No reason-coded TpLimited/Inflight hits occur in the selected instrumented path, but `CanTrySendNewDataPacket` has a separate `IsInflightLimited` check without that reason event. Zero such emitted hits does not rule out all packet-window checks or the joint native queue/admission constraint. No new probes or treatments were introduced mid-run.

### Forward egress 59 and actual AllReady queries

The requested forward-path comparison is class-separated, not replaced by return-port analysis. In MC, egress 59 weight-packet VOQ mean/max are 0.267050/2.564612 µs at 512, 0.980716/5.126239 µs at 1024, and 1.319259/8.080000 µs at 2048. Each weight cohort has 36,864 packet residences. ACK-response mean/max are 0.022944/1.920158,0.154237/2.948187, and0.017242/1.652058 µs, with counts 36,352/35,864/35,394. Thus forward weight queueing rises while completion improves, and the ACK class is non-monotone. These are end-event-in-phase full-residence cohorts, not matched packet identities or additive wall time. See Figure 4 and `data/switch_cohorts.csv`.

AllReady group 8 records actual short-circuit evaluations, not sampled states. Ready evaluations are 75,058/76,677/80,600 at 512/1024/2048. First-empty-member failures change from member 13=1 and 59=3,086, to 13=7,749/52=7,834/59=10,277, to 13=16,192/52=16,194/59=1,890. ACK-priority failures also remain: member 13/52/59 counts are 18,461/17,920/17,976;18,671/17,468/17,863;20,193/17,000/17,379. Failure location migrates rather than disappearing. A first failure hides later member states; held spans are observation upper bounds, not continuous waiting durations. Neither their counts nor spans assign a unique delay share. See `data/allready.csv`.

## 9. Required evidence classification

### Confirmed causal factors or model constraints

- A's proposed change fails the required cross-TP semantics-preservation condition. No performance effect follows from this audit.
- Original MC 512 has a conditional necessary shared feedback-port service lower bound of 716.8 µs, derived from model invariants and independently reviewed. This is a necessary-service theorem for that model, not an isolated intervention share.
- B establishes the total causal effect of changing the Jetty window under the fixed tested workload: MC weight −2.641184%/−3.955758%, layer −0.349907%/−1.343416% at 1024/2048, with Chunk endpoints unchanged. The strategy×window interaction is measured; unique mediator shares are not.
- The bounded fresh source 3→59 cycle directly verifies full state→accepted contiguous SSN progress→eligible admission of the final TA. This establishes that local native gate mechanism, not its share of all elapsed time.

### Supported but not fully isolated

- Full Jetty exposure and sustained, queueing-heavy return-port feedback support a coupled admission/feedback mechanism in original MC.
- Forward switch egress 59 contention, AllReady short-circuit query behavior, ACK/control priority and native retained-capacity constraints can mediate outcome changes. Their unique wall-time shares are not isolated by B.
- AllReady held spans are observation bounds, not continuous wait. Queue residence sums and per-Jetty exposure sums are not additive wall time.

### Ruled out, with explicit scope

- Perturbation of measured fresh-512 baseline behavior by the new passive observer is excluded by exact accepted/full-summary and ordered readiness parity, plus observer gates. This is a tested-scope claim, not a proof of every possible workload.
- Final source-side cleanup after WeightReady is not part of the receiver weight-phase endpoint. This does not exclude earlier TAACK feedback as a cause of later admission.
- No A+B mixture, changed allocator, or substituted old baseline is used for B; final source/binary/input identity checks pass for all six cells.
- A hard 1000 outstanding-TA ceiling and an exact 1024→2048 endpoint plateau are ruled out by actual 2048 TA occupancy and further measured improvement. This does not exclude the distinct 1000-segment capacity state or all capacity-mediated effects.
- Eliminating the original reversal merely by the tested Jetty increases is ruled out: MC remains slower at both changed windows. A shorter weight phase implying the same layer gain, or uniformly shorter RTT/VOQ residence, is also contradicted by these outcomes.
- Final weight-TAACK drain being a universal prerequisite for compute is ruled out by the 2048 overlap. This does not exclude earlier feedback as a prerequisite for subsequent weight admission.

## 10. Evidence package and reading guide

- Figures1–2: `figures/window-latency.png` and `window-contrasts.png`, endpoints and within-strategy/DID effects.
- Figure3: `figures/source3-occupancy.png`, actual phase-integrated state, not blocked-work time.
- Figure 4: `figures/switch59-residence.png`, forward egress weight versus ACK-response cohorts.
- Figure5: `figures/feedback-return-port.png`, fixed return-port exact partition and queue residence, separately.
- `data/`: bounded aggregate timing, occupancy, latency, histograms, selected resources, actual AllReady queries, terminal dependencies, selected Jetty events and TA samples.
- `feedback/`: fixed/terminal return-port aggregates, physical packet-kind conservation, retained-tail capacity observations, boundary frontiers and postweight landmarks. `evidence/` contains the 11-row direct baseline cycle and conditional service proof.

Publication is explicit-allowlist only. No complete raw ring, packet payload, per-token, full per-node or per-expert dump is included. Selected detailed event/sample records total 87 rows across the main and supplemental exports, with duplicates retained transparently across different evidence views rather than claiming 87 distinct events. Other selected path/terminal/frontier rows are bounded summaries, not full traces. The report and artifact manifest identify units, scopes and hashes. Input fingerprints refer only to case IDs and basenames, with no private absolute workspace paths. Source references below distinguish audited code from measured data. All five final PNG renderings were visually checked for legibility and clipping; SVG counterparts are provided.

The feedback hypothesis was recorded at 06:05:16 UTC before inspecting fresh formal baseline outcomes. The proof was developed from accepted historical evidence and independently challenged before treatment results. The timing of these steps does not convert a conditional model argument into an intervention-based mediator decomposition.

## 11. Source anchors for reproducibility

Native line references below identify the frozen native source tree used by these runs; application paths are relative to the parent experiment folder (`../` from this report), while `src/` paths are relative to the separately fingerprinted native source tree. Source-identity hashes accompany the evidence package in `evidence/source-references.json`. The source audit and data evidence are complementary: code establishes conditional semantics, while completed runs establish the reported observations.

| Claim | Frozen source location |
| --- | --- |
| Per-pair TP identity and VL7; switch egress i→NPU i; weights_start before submissions and weights_end at receiver completion | `layer.cc:254–260, 301–302, 429, 451–456` |
| Default Jetty window 512, ACK bitmap 2048; actual window test and passive state observation | `src/unified-bus/model/protocol/ub-function.cc:1020–1033, 1049–1077` |
| Admission event and accepted TAACK before/after contiguous SSN progress | `src/unified-bus/model/protocol/ub-function.cc:1230–1272, 1479–1539`; correlation validation in `src/unified-bus/model/protocol/ub-transaction.cc:2114–2177` |
| WRITE requires its transaction response; a cumulative TPACK cannot retire the requesting Jetty TA | `src/unified-bus/model/protocol/ub-transaction-rules.cc:28–32, 69`; `src/unified-bus/model/protocol/ub-transport.cc:1418–1435` |
| A fresh request TPACK is enqueued before target TA completion; FIFO ACK queue is served before new data | `src/unified-bus/model/protocol/ub-transport.cc:601–609, 881–938, 2219–2305, 2512–2525, 2645–2647` |
| Both return packets use ordinary forwarding and the same priority/ingress-specific output FIFO | `src/unified-bus/model/protocol/ub-transport.cc:1210–1238, 2220–2269`; `src/unified-bus/model/ub-switch.cc:394–432, 726–774, 989–1024`; `src/unified-bus/model/ub-ingress-queue.cc:148–209` |
| Physical egress FIFO/BUSY exclusion and fixed serialized link delivery | `src/unified-bus/model/ub-port.cc:61–83, 136–157, 552–603, 829–899, 1068–1103`; `src/unified-bus/model/ub-link.cc:174–199` |
| Original 5 ns allocation, one pending callback per output, one frame per successful callback | `src/unified-bus/model/ub-switch-allocator.cc:110–114, 188–218, 251–266, 355–385, 708–835` |
| Fixed TP packet and retained-segment capacities; earlier retained-capacity gate | `src/unified-bus/model/protocol/ub-transport.cc:260–270, 2676–2714, 2854–2870`; `src/unified-bus/model/protocol/ub-transaction.cc:865–872` |
| TpEmpty counters; pending-transmit semantics; separate packet-window check; ACK cleanup reentrancy caveat | `src/unified-bus/model/protocol/ub-transport.cc:629–666, 1807–1837, 1865–1903, 2937–2953, 3021–3040` |
| Node compute-batch boundaries, distinct from individual expert starts | `../layer.cc:399–405` |
| Exact SSN transition integration and phase clipping; selected latency boundaries and coverage | `jetty-measurement.inc:34–82, 84–101`; `diagnostic-recorder.h:56–57, 87, 135–136` |
| A counterexample and its cross-TP scope | `audit-a/SOURCE-AUDIT.md`, `audit-a/decision.json`, `audit-a/result.json`, `audit-a/null-callback-order.cc` |
