# Validation equivalence review checklist

The accepted offline oracle is `experiments/multi-npu-relay/verify.py`, augmented by
`experiments/pair-jetty/verify.py`. Its inputs are config/plan JSON, application
`events.csv`, `executed-transfers.csv`, `ta-identity.csv`, payload index and bytes,
and simulator metrics. Native packet CSVs are diagnostic evidence, not inputs to
these two application correctness oracles.

## Checks that must survive persistence being disabled

| Accepted check | Required compact-mode counterpart |
| --- | --- |
| Config/plan assignments match logical routing, physical expert and quotas | Independent `preflight.py` reconstructs each assignment and runs the accepted Planner checker for UltraEP |
| Input file actually matches documented config/plan | Preflight reconstructs the entire integer execution input, compares every field, and fingerprints source inputs |
| Actual execution graph equals configured transfers | Reconstruct weight edges using the unchanged accepted graph tool; compare every transfer/dependency; compare executor canonical graph fingerprint (debug also exact CSV) |
| Each remote task has all intended TA offsets, sizes, and endpoints | Per-task/per-segment admission, receive, payload-verify and target-complete state machine, with exact-once states |
| Logical SSN belongs to task and correct byte offset | Retain actual admission map, wire/logical SSN checks, response association, and all pending-response cleanup checks in every mode |
| Payload really received and correct | Verify every received explicit byte, retain buffers needed by computation/relay, independently recheck final buffers before reporting PASS |
| Sender completion does not stand in for target readiness | Target coverage grants ready; sender success requires corresponding task ready; both per-task terminal states required |
| Target execution delay and readiness aggregation | Check receive/verify/completion order and configured target service delay, task ready at final segment completion |
| Chunk/whole-expert/group barriers and immediate forwarding | Check source buffer provenance and full dependency set, group aggregation, ready-before-forward, exact immediate forwarding time |
| Replica complete only after all chunks | Full weight range coverage and readiness max over incoming edges, one readiness event per replica |
| Dispatch/compute/combine prerequisites and durations | Exact dispatch gate, per-physical quota/weight readiness, per-NPU sequential expert intervals using unchanged model duration, combine at compute completion |
| Token contributions and final layer result | Per-token logical identity and all distinct Top-k assignments, one completion at last combine, layer end at last token (or empty gate) |
| Duplicate/early/missing events | Per-identity event cardinality, per-task/segment state, terminal task and Jetty-idle checks; nonzero error exit |

Hashes summarize identity only; they do not replace per-task validation or byte
checking. Native diagnostic callbacks and packet path tags may be disabled, but
transport processing and target execution callbacks must remain connected.

## Native trace switch audit

The accepted native source already has `UB_TRACE_ENABLE` gates in
`UbUtils::TopoTraceConnect()` and `SingleTpTraceConnect()`. Packet path recording
uses `UbPacketTraceTag` metadata; it does not alter `Packet::GetSize()` or link
serialization time. `UbPort::PortTxNotify`/`PortRxNotify` fire at actual port
send/receive boundaries regardless of the file logger switches, so small counter
callbacks can remain connected in all three modes.

Count semantics must distinguish endpoint counters from all-hop counters: a
single-switch path appears at both endpoint and switch ports. The counter is not
an estimate derived from TA count. Summed all-hop bytes must not be described as
application payload bytes.

## Required runtime evidence

- Identical-input summary/events/debug comparisons, including EP64 and multichunk,
  multi-TA relay overlap; all simulation times/counts/placement/quota/payload
  fingerprints must match, apart from host resource metrics and output metadata.
- Debug must still pass the unchanged strict offline oracle and match the accepted
  executor's legacy fields/content (additional separate metadata is permitted).
- Genuine payload, duplicate-completion, early/missing WQE, early relay, premature
  final weight ready, and compute dependency faults must trigger actual checks.
- Legitimate idempotent tracker notifications remain explicitly distinguishable
  from illegal double target execution or double WQE-success notification.
- Summary/events must never create native traces or payload dump files, rather
  than create then delete them.
- Resource totals must include any independent preflight/postflight time clearly;
  callback verification CPU time is nested in simulation wall time and must not
  be added to it.

This checklist describes acceptance criteria, not an assertion that runtime tests
have passed. Final results and limitations are in the stage report and test JSON.
