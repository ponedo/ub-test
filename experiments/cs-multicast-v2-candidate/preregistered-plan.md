# Bounded paired experiment plan

Status: implementation and metadata preparation only; build and simulator execution await parent approval. No fixture generation or simulation has run under this plan.

## Claim, prediction, falsification

Hypothesis: a fixed 5 ns per-head APP veto can let an already submitted aligned absent member, or structurally matching priority-obstructed member, become merge-ready before fallback. Prediction: exercised eligible episodes may transition to actual full Stage I/II merge and reduce source serialization work; measured WeightDuration and LayerLatency may improve, remain flat or regress. Priority-obstructed member data readiness is UNKNOWN until exposed; classify and report that exposure separately. No expected percentage. Falsification: adequate exposure but no transition improvement, more envelopes without useful timing/resource improvement, or extra wait/NoIngress/Rejected offsetting saved work. Correctness violation is unsafe, not merely negative.

## Arms and controls

A is immutable cs-mc-private/app-build-v2/layer SHA256 2fd21591e56bf8bd9dfe7ee481e5ce935ac776722ba1e3193acb38ee0d6e5b2f. B is candidate-on; C is candidate-off only on V01/V04/V06. Native libraries are the same token-screen-native closure. No observer recompilation substitutes for A. New candidate fields cannot be attributed to A. Optional additional diagnostic-off runs are not included or authorized by this 37-run plan.

Every pair copies identical config/input/graph bytes. All rows are synthetic, <=200 tokens, <=20 ranks, chunk=4096, native TA=512 and allocation=5 ns. Graph/tree/membership/order/model/network/compute/fault/seed/diagnostic settings are fixed per pair. No real traces, real256/512/1024/2048 scale, five-strategy matrix, chunk/window/fanout/hold scan or native rebuild.

## Exact matrix

V01..V14 map respectively to B01,B02,B03,B04,B05,B06,B09,B10,B12,F01,F02,F03,F04,F05 in the frozen fixtures module. Two sequential arms each =28. C-V01/C-V04/C-V06 add three candidate-off runs; N02/N04/N08 each have A/B =6. Total37. The declaration in support.py is authoritative and small.py emits its explicit manifest, identities and row ledger without a new resume system.

V08 is B10 normalized from chunk1024 to4096 on BOTH arms, keeping its64 tokens,1082369 weight bytes and existing completion delay. It does not inherit >1024 lifetime coverage. Require actual max_outstanding512 plus native window-limited observation and safe drain, otherwise INCOMPLETE and stop. Do not enlarge weights/shrink chunks/change windows without a separately approved revision.

## Evidence and checkpoints

Every successful arm: independent frozen verifier, original byte partition, payload/token/combine correctness, native drain/CBFC/association checks and native per-port requested=effective+Rejected+NoIngress, effective=TX. Keep requested workload separate from elapsed rejected/no-ingress duration. V04 requires actual Stage I and II envelopes and physical streaming; fanout1 must have no holds. V09 compares stale rejections to same-arm V04. F03 uses the unchanged fixture-specific cumulative-ACK oracle, never an invented retry requirement. Reverse TAACK fault proof stays native, not proxy-counter-only. Candidate-off must preserve deterministic summary, physical/timeline/compute and diagnostic CSV outputs; only candidate observer files and host measurement fields are excluded. Negative rows must fail exact declared invariants, not guard kills or generic crashes.

Review V01-V04 identity/correctness/live merge, then V05-V09 causes/TA512/streaming, then faults/parity/rejections. One sequential pass; no implicit resume/retry. Stop on unsafe, invalid-pair, guard, missing mandatory witness or scope change. Keep every attempted/skipped/failed/inconclusive/negative row visible. Flat/negative valid results alone do not justify adding cases. At completion, evidence gaps in expiry-no-other-wake, priority during hold, stale event, no rearm, mismatch release or named causes remain INCOMPLETE admission even if all37 executions succeed.

## Resource limits

Reuse immutable guard: treeRSS6GiB, AS7GiB, wall4800s, admission available7GiB, runtime host floor1GiB, output disk floor8GiB, /tmp floor2GiB. One build or simulator at a time, core dumps disabled, no Debug. Guard abort kills owned process tree and stops progression. Existing build/fixture/verifier tools are reused; no native build, full validation framework, publication or commit.

Final observer clarification: absent-member data eligibility is also UNKNOWN; no peer IsLimited/CC probes are added. The complete bounded ledger includes arm, release and actual held-head consumed events. Release-to-consume delay is measured separately and is not bounded by the 5 ns APP veto.
