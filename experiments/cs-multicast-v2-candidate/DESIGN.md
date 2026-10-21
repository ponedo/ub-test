# Small Candidate: one-shot APP eligibility hold

Accepted control: e3efc29e901024cea6343196f6ab33958e3b02cd. The neighboring chunk-streaming-multicast tree and native transport remain unchanged. This directory is experimental, not replacement v1. The final bounded result is recorded below; no general benefit or admission is established.

## Only changed variable

Boolean --cs-mc-align-hold, default 0. Enabled mode allows a query-triggered, exact current-original-head 5 ns one-shot APP veto for Stage I/II multi-member groups only. This is not an already-RR-selected-only policy. Native eligibility scans may arm unselected queues. Registered slots, RR code/cursor policy, 5 ns allocation service, same-TP ordering, graph readiness and SubmitWqe timing remain unchanged, but realized arbitration and timing may change.

Identity is native TP plus task, full logical SSN, offset and length. Hold state is bounded per proxy; deadline never extends and the spent identity remains until head advancement. Empty/limit/priority handling precedes APP veto. No promotion, later-head scan, reservation, subset merge, ACK wait, barrier or artificial packet size. Choose/Size remain pure; IsLimited owns idempotent query-triggered entry. Expiry marks spent, refreshes registered proxy and wakes the native port. It bounds APP inhibition, not transmission latency.

All members are submitted and their first-byte offsets aligned. Every visible original must match expected task/kind/range/payload. A full match releases immediately; permanent mismatch, consumed peer, native data limit, unsupported size/header, capacity/credit/egress failure disallows or spends the hold. Missing heads and structurally matching priority-obstructed peers are speculative opportunities only. The latter's underlying data CC eligibility is UNKNOWN, not proven: no mutating CC probe. If priority clears into a native limit, spend/release without extension. Native priority on the held proxy bypasses APP veto while respecting native limits and the original immutable deadline. TAACK/RESPONSE behind an original is not promoted.

## Diagnostic and correctness boundary

Existing full online payload checks, exact fixed-group byte partition, native PSN/SSN and physical route verification remain authoritative. Candidate-only bounded records must establish one-shot arm/release identity, actual inhibition duration <=5000 ps, no expired veto, no active timer/state at drain, native-priority bypass outcomes and UNKNOWN-priority opportunity cost. The complete hold arm/release member ledger has a32768-row hard cap; pull snapshots are sampled at first32 per(role,reason), with complete aggregate counters and explicit omitted counts. The legacy131072 event cap is separate. Diagnostic overflow means incomplete evidence, never silent PASS; sampled pull rows cannot estimate complete cause distributions. Observation intervals are not continuous waiting; simultaneous ACK traffic does not prove causation. Native NoIngress and Rejected are reported separately, not relabeled as Candidate wait.

No source audit proves a 5 ns alignment opportunity or performance gain. Zero eligible opportunities, flat results and measured regressions are valid outcomes. Do not change chunk/window/fanout/graph or add scale to rescue the hypothesis.

Final observer clarification: absent-member data eligibility is also UNKNOWN; no peer IsLimited/CC probes are added. The complete bounded ledger includes arm, release and actual held-head consumed events. Release-to-consume delay is measured separately and is not bounded by the 5 ns APP veto.

## Preserved off-target 100Gbps diagnostics (2026-10-21)

These52 executions used inherited100Gbps, not the requested3136Gbps. They are not target-bandwidth evidence; the omission and corrected target results are retained explicitly.

The implementation was built once against unchanged native libraries and exercised in 52 small simulations: 15 initial attempts, 18 fresh corrected-oracle attempts, and 19 explicitly approved remaining independent cases. The logical matrix contains 37 executions. The initial 15 were intentionally repeated to validate an observer-oracle correction, not to seek favorable performance. Runtime policy, binary, graph and fixture controls were not tuned.

The initial checker incorrectly required zero native rolling-tail evictions even for aggregate-only evidence. The correction retains every true aggregate completeness/error check and reports tail overwrite count/completeness separately. Lost sampled events cannot establish complete causal history. Both original stopped ledgers remain preserved. V09 candidate performed the injected invalidation but avoided a stale-grant rejection; its required witness is NOT_EXERCISED, not PASS and not an established runtime safety failure.

All five fault pairs, three candidate-off deterministic parity cases and six exact negative rejections passed their applicable checks. Across the 14 logical candidate rows, 338 holds armed, expired and were consumed, with a maximum 5 ns APP veto. No early release or active-hold priority bypass was observed. V08 produced 514 additional envelopes and saved 516,056 source-wire bytes, but LayerLatency and WeightDuration each worsened by 4.96 ns and six extra grants were rejected. No paired completion-time improvement was measured. The candidate is NOT_ADMITTED; missing witnesses and timing costs remain part of the result.

### Fixed-target streaming coverage extension (post-observation, not tuning)
The original 3136Gbps V04 control has first downstream TX equal to full-expert
RX (311872ps), despite chunk RX and group readiness at 301872ps. Its strict
streaming overlap witness remains NOT_EXERCISED, not a dependency failure.
Exactly one additional paired synthetic 64KiB case S64 extends only weight
length/chunk count; Planner bytes, assignments, placement, tree edge/role set,
fanout, 4096-byte chunks, network, binary and policy remain fixed. It is a
coverage experiment, not an uncontaminated performance comparison or a length
search. A missing S64 streaming witness stops execution.
The explicit remaining manifest runs only 30 previously unexecuted commands
plus this pair. It may continue after exactly streaming_physical missing in
original V04 or C-V04, or stale_grant missing in V09 candidate-on, but only
after all online, independent, native, hold and applicable disabled-parity
checks pass. Such rows are INCOMPLETE_NOT_EXERCISED, never PASS. All other
failures stop. The prior seven target runs and 52 off-target 100Gbps runs are
preserved separately. No new runtime build or algorithm change is involved.


## Final fixed3136Gbps result
The original37 target executions and single paired64KiB streaming extension
completed without runtime/binary/native changes (39 target executions). Together
with the preserved52 off-target diagnostics, the actual total is91 simulations.
The V04 control's strict streaming gap remains preserved, as do the V04 candidate
and C-V04 streaming gaps and V09 candidate stale-grant gap. The inherited V12
ACK-oracle stop is preserved with a separate candidate-only posthoc proof:
complete covering ACK paths may begin before loss while their ingress is later.
All directed TP, UID, original PSN0..11, task and terminal-drain checks remain.

S64 establishes65ns of physical streaming overlap for both arms at both relays.
It is a post-observation coverage extension, not a clean performance comparison.
Across original14 candidate cases44 holds expired; S64 adds85, also all expired.
No early release or active-hold native-priority bypass was observed. At3136Gbps,
V08 gains6 envelopes and saves6,024 source-wire bytes; WeightDuration improves
8.222ns but LayerLatency worsens10ns. No paired LayerLatency improvement occurs.
S64 gains40 envelopes and saves40,160 source-wire bytes but adds5ns LayerLatency.
All5 fault pairs,3 disabled-parity comparisons and6 exact negative rejections
pass applicable checks. Streaming gaps are not promoted to PASS by parity.
The outcome remains NOT_GENERAL_ADMISSION, not an established useful latency
optimization. No policy tuning, bandwidth scan, scale expansion or further
streaming-length search followed these observations.
