# Controlled multicast ablation: preregistered analysis

Written before the six new formal cases are run. Accepted source commit: b149fdd4d40d72791a84b788443b0450c41f6180. This document records predictions, estimands, falsification and reporting rules, not results.

## Scope and independent controls

The question is whether Jetty TA admission capacity has a causal contribution to the accepted multicast reversal, not which parameter makes multicast win. The sole authorized performance intervention is B: Jetty TA window 512, 1024, 2048, independently for Chunk-Streaming and Multicast v2. Every case starts with copied accepted inputs and the original allocator. TP packet window 1000, TA size, native MTU, WQE/admission implementation, ACK policy, RR priorities/order/service, Planner, routing trace, topology, link 3136 Gbps and Roofline Compute are fixed. The Jetty out-of-order ACK bitmap remains its accepted 2048 capacity. No A+B cell, 100-Gbps formal matrix, or extra parameter search is authorized.

Formal cases: baseline-512-chunk-streaming, baseline-512-multicast-v2, window-1024-chunk-streaming, window-1024-multicast-v2, window-2048-chunk-streaming, window-2048-multicast-v2. A has no formal performance run: suppressing null callback service already has a scheduler-order counterexample, so A must be reported STOPPED/UNSUPPORTED with no invented speedup or numerical share. The audit witness is not a physical WRITE or layer-performance result.

The six runs are deterministic simulator contrasts under this fixed workload and implementation, not independent statistical samples. Do not invent confidence intervals, significance, or population generalization.

## Gates before interpretation

1. Stage-A observer/default-OFF/ON and changed-window regressions PASS. Source, build, inputs and accepted baselines remain frozen.
2. All six formal cases PASS independent correctness and resource gates. The two fresh 512 cases reproduce accepted complete online summaries excluding verification_wall_ns, plus byte-identical ordered expert-compute, expert-ready and replica-ready artifacts. Preserve checks against both diagnostic accepted and original bandwidth baselines.
3. Changed-window cases preserve logical graph, assignments, transfers, byte counts, WQE/TA/target completion counts and payload fingerprints. Timing, packet order and simulator event count may change because B intentionally changes admission.
4. All passive observer integrity counters are zero, with incomplete=false. Exact occupancy comes from actual SSN transitions, not polling, reverse-packet-count reconstruction or stale flags.
5. No analysis silently substitutes older runs for mandatory fresh 512 cases. Keep original results visibly labeled as original; label all changed-window results intervention-only.

If a gate fails, report the failed/not-run cell and reason. Do not silently drop it, choose a different denominator, extrapolate, or claim a completed six-cell causal result.

## Primary estimands and signs

For strategy s and window w, W(s,w) = weights_end minus weights_start in ps; L(s,w) = full LayerLatency in ps. WeightReady is a receiver-completion boundary, not sender cleanup.

Within-strategy absolute treatment effect: delta(s,w) = W(s,w) - W(s,512). Negative means the intervention shortened time. Also show relative change 100 * (W(s,w)/W(s,512)-1), and intervention speedup W(s,512)/W(s,w). Apply the same definitions to L separately.

At each common w, the strategy gap is G(w) = W(MC,w) - W(Chunk,w). Difference-in-differences is DID(w) = delta(MC,w) - delta(Chunk,w) = G(w) - G(512). Negative DID means the intervention preferentially benefits MC (or harms Chunk more); the within-strategy rows disambiguate. G(512)-G(w) is gap reduction under this joint capacity intervention, NOT an additive causal percentage assigned to the original 512 stall mechanism. Report MC/Chunk time ratio at each common window only, never compare MC2048 to Chunk512 as an algorithmic speedup.

Original accepted values are fixed references: W(Chunk,512)=552893591 ps, W(MC,512)=717182855 ps, G(512)=164289264 ps; L(Chunk,512)=732284971 ps, L(MC,512)=898435170 ps. Fresh baseline parity must verify them, not force them.

## Predictions and falsification

P1, capacity sensitivity: increasing the Jetty window may reduce MC full-window exposure, actual Jetty-limited query counts, source idle, and weight time if the measured 512-TA admission mechanism constrains the critical path. Direction is a hypothesis, not a gate. Equal or worse time falsifies the claimed speedup for that tested intervention, but does not erase the proven existence of a 512-full admission event. Queueing/control competition or changed bottleneck may offset benefit.

P2, relative strategy contribution: if this capacity is more important to MC's reversal than to Chunk, delta(MC,w) should be more negative and DID should be negative. Both strategies can benefit equally; MC alone getting faster does not establish that the mechanism explains the strategy gap. A persistent positive gap after both treatments means the reversal is not removed in that tested cell.

P3, plateau/bottleneck migration: 1024 to 2048 may have diminishing effect because the unchanged TP packet window is 1000 and retained WQE capacity is 1000. This is not a mathematical ceiling of 1000 TA SSNs: TAACK and TP ACK progress differ. A plateau plus actual TP Inflight branch observations supports migration to TP admission; plateau alone does not identify it. Growing Jetty occupancy above 1000 with no TP-limit branch is not contradictory, because the sequence spaces differ. Continued improvement at 2048 falsifies a simple assumed 1000-TA saturation model, not configuration correctness.

P4, queueing feedback: a larger admission window can increase switch egress 59 weight/ACK-response VOQ residence even while reducing total time, or can worsen both. Compare count-weighted mean and maximum full-residence cohorts separately for weight and ACK-response. Their sums overlap and are not additive wall time; shorter final forward suffix never rules out earlier queueing feedback.

P5, AllReady: first-failing-member query counts and query-held spans may shift from empty toward ACK-priority or other reasons. No direction is required. These are actual short-circuit observations, not continuous waits or independent mediator interventions. Never add held-span sums to measured idle or across groups.

P6, terminal-path migration: baseline MC source3→59/group8 and Chunk source36/50→17/27 are selected a priori. Treatment may change the true final dependency. Re-identify actual last WeightReady tasks for every cell rather than assuming the baseline critical source survives. Keep fixed-resource comparisons (source ports 3/36/50 and switch ports17/27/59) separate from moving-critical-path comparisons.

## Passive measurements and denominators

- Actual Jetty occupancy is ssn_next - ssn_una. Validate 0<=occupancy<=configured window and terminal completion. Time-weighted occupancy and full-window exposure are exact integration across observed transitions; state explicitly the first-observation through last/phase boundary exposure. Jetty-time totals summed across pairs are NOT elapsed wall time. Aggregate mean occupancy = sum(outstanding_ta_ps)/sum(observed_ps), and saturated fraction = sum(full_window_ps)/sum(observed_ps); include pair count and denominator. Empty and completed pairs remain in exposure unless a distinct active-period cohort is explicitly defined. Do not silently change to packet-weighted or active-only weighting.
- Report all-pair occupancy as global aggregate; separately preselected same-source and source3→5/13/52/59 pairs if available. Native Jetty IDs are local implementation identities, not guaranteed cross-strategy pair identities; match physical source/target and retain multiplicity.
- Histograms use the recorder's declared fractional-capacity bins; show absolute max occupancy too, since fractions against unequal windows can hide growth. Full-window equality is a capacity state, not automatically a harmful wait without pending work and progress evidence.
- TAACK progress must use accepted actual Jetty events and contiguous SSN advancement. A TAACK arrival may be out of order, so accepted count and frontier progress are distinct. Preserve zero-progress and rejection/duplicate evidence and do not interpret every response as one-slot release.
- Three distinct latency distributions: TA admission→accepted TAACK (includes local queueing), native packet-pop→accepted TAACK (not physical TX), first successful source physical TxStart→accepted TAACK (includes downstream network, receiver execution, ACK/control arbitration and return path). This last value is not pure propagation RTT. Count, sum, mean and maximum only unless the recorder retains a real distribution. Never invent percentiles from mean/max.
- Sample latencies are weight TA-admission cohorts selected by the recorder, and may complete after WeightReady. They are not necessarily end-in-weight-phase cohorts. Selected-source coverage differs unless explicitly equalized; compare same physical source/pair cohorts only or state unequal scopes. Missing source-TX/pop correlation invalidates those specific boundary statistics, not automatically global occupancy.
- Native TP limit counts come from actual TpLimited reason branches, never m_sendWindowLimited. TP ACK-only traffic can bypass data eligibility. An absence of a branch in a limited observation scope cannot exonerate all admission mechanisms.
- Source resource partition (TX busy union, allocation pending excluding TX, uncovered idle) is exact disjoint elapsed accounting. Use each source's own last weight dequeue, or the explicit whole phase. Do not include idle after its completion as eligibility waiting. Callback outcome durations and serialization overlap these terms and are not additional components.

## Causal classification for the final report

Confirmed causal: the total outcome changes from B within a strategy, conditional on all controls and gates; the matched DID is a causal effect modification contrast of the same capacity intervention under the two fixed strategies. Direct SSN evidence can prove the occurrence of a full-window→accepted-TAACK progress→next-admission mechanism in a selected cycle. A's null-callback deletion is not semantics-preserving, by the independent native unit witness; therefore it cannot quantify A's performance contribution under the requested constraints.

Supported but not fully isolated: whether reductions in full-window exposure, source idle, AllReady empty observations, or switch59 residence mediate B's latency effect; specific ACK/response arbitration versus RR/CBFC versus WQE/TP gates; the unique amount of original reversal attributable to each mechanism. Changed internal timing is a mediator, not a confound to freeze away; unrelated code/config/workload changes are confounds and invalidate B.

Ruled out, with exact scope: baseline observer perturbation if full parity passes; changed input/allocator/TP window as alternative explanations if identity/config audit passes; the final sender-completion tail as part of receiver WeightReady critical path; direct tested TP packet-window gating in a selected below-cap cycle if the actual branch proves it. A null/harmful B outcome rules out the predicted benefit for that cell, not all Jetty causality. Do not claim that earlier queues, ACKs, or all idle are ruled out by a short final suffix.

## Publication-safe deliverables

Candidate aggregate CSVs: six-cell timing and within-strategy deltas; two treatment DIDs; preselected-source resource partitions; physical switch17/27/59 class-specific cohorts; global and selected-pair Jetty occupancy/latency aggregates; group8 AllReady aggregates. Preserve actual new terminal identities without copying full per-expert files. A bounded timeline cap is 240 selected events total, with selection/censoring rules documented and event order retained. Never copy complete raw rings, per-token/per-node/expert private dumps or logical payloads to publication.

Plots: (1) weight/full-layer time versus window, both strategies and 512 original baseline explicitly marked; (2) within-strategy relative changes and weight DID with zero lines; (3) actual occupancy/full-window fraction with exposure labels; (4) same switch59 weight and ACK-response residence mean/max. Distinguish simulated time from host runtime. No stacked causal-percent chart.

Outputs remain private review candidates until separately authorized publication and evidence review. New analysis code only reads completed runs and never launches simulations, edits inputs, or mutates accepted experiments.
