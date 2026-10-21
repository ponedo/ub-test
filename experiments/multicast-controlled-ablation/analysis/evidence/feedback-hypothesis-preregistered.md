# Additional pre-result feedback-path hypothesis

Recorded 2026-10-21 06:05:16 UTC, before inspecting new formal baseline outcomes. This supplements the earlier preregistration; simulation settings and the six-cell design are unchanged.

Hypothesis: physical switch egress 3 is the shared return path into original terminal Multicast source 3. A source-3 envelope can fan out four native weight requests, plausibly producing four TP ACKs plus four TAACK responses returning toward source 3 per envelope sequence. Outgoing source 3 work might comprise one envelope and four response transport ACKs, making 5 outgoing frames against 8 return frames per sequence. At fixed 5 ns allocation service, (18432 - 512) × 8 × 5 ns = 716.8 µs, numerically near the accepted 717.182855 µs weight phase.

This is a dimensional/mechanistic hypothesis, not a finding or causal attribution. The 512 subtraction assumes an initial credit/admission pipeline and must be checked, not fitted. It is not permitted to identify all 91.534728 µs baseline idle, subtract overlapping callback/serialization durations, or manufacture a partition from this formula.

Predictions requiring verification:
- Actual direction: node64 / physical egress port3 must lead to NPU3, and reverse TP ACK versus TAACK traffic must be distinguished by packet kind or audited producer/consumer semantics. The broad ACK-response class alone cannot identify the mix.
- Traffic counts: compare observed source3 outgoing stage2 and control counts against switch-egress3 returning counts. Use whole-run and weight-phase cohorts separately, because final TAACK cleanup after receiver WeightReady is excluded from the weight critical endpoint.
- Resource pressure: inspect existing node64/port3 VOQ count/mean/max by traffic class, exact TX/allocation/idle interval partition, and successful/rejected/null callback counts and elapsed service. Counts or overlapping packet-time sums alone are not serialized wall time.
- Feedback coupling: bounded retained actual TAACK/SSN progress and physical return-port events may support the path, but UID reuse and event-order/correlation requirements still apply. No full run trace is claimed.
- Capacity migration: 1024/2048 may plateau near the unchanged TP1000 ceiling, but actual TP Inflight evaluations and distinguishable TP ACK/TAACK frontiers are required; plateau alone is not evidence of TP causation.

Falsification and alternative interpretation:
- Different actual fanout, reverse direction, traffic mix or service counts invalidates the eight-per-sequence formula.
- Large gaps/idle or overlapping service prevent multiplying counts by 5 ns as if all were exposed.
- Even an exact numerical match is not isolated mediation: B measures only the total effect of changing the Jetty capacity.
- All six cases retain the same pre-fixed observation filters. A new terminal source outside the selected sources must be reported as a coverage limitation; source3 feedback/RTT is not relabeled as the new critical path.

