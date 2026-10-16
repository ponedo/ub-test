# Concurrent WQE completion correctness experiment

A = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b, B = eda2fd75bfd1a37b28917b3ebbe721bade5f91ae, C = B + actual-admission-frontier completion fix.

Fixed controls: accepted two-node shared-jetty probe, native release O3 build, all network/payload/TA settings unchanged. Predictions: A/B retain original concurrent-multisegment failure; C passes target-before-success and exact-once accounting. Falsification: any early success, missing/duplicate notification, payload mismatch, invalid cleanup or changed old one-WQE-per-Jetty output. No Pair Jetty app changes.

## Batch Reuse Map
Pre-refactor commit: eda2fd75bfd1a37b28917b3ebbe721bade5f91ae.
Semantic batch: replace inferred WQE completion endpoint with actual committed SSN endpoint and all-admitted gate.
Old active symbols: UbJetty::PushWqe, CommitWqeSegmentAdmission, IsWqeCompleted; UbWqe private admission state.
Old call paths: native transaction admission -> Jetty commit; valid semantic segment completion -> global ACK bitmap -> prefix advance -> completed WQE check.
Reuse: all native ACK/response validation, bitmap, ordering and terminal cleanup unchanged.
Lifecycle: initialize optional admission frontier at PushWqe; update only at committed admission; WQE owns constant state and releases it with object.
Preserved: Jetty global-prefix notification barrier, WQE/TA schedule, timeout/failure/cancel and cleanup.
Explicit delta: no success based on a fictitious contiguous reservation or before all bytes are admitted.
Excluded: protocol state-machine redesign, uint32 logical SSN overflow support, independent out-of-order WQE completion, Pair Jetty.
Focused validation: exact old MRE A/B/C; concurrent, staggered, delayed, single segment and multi segment; native tests plus all accepted UltraEP regression and exact old-output parity.
Checkpoint: report immediately if change requires ACK/response state-machine modifications or regressions alter legitimate semantics.
