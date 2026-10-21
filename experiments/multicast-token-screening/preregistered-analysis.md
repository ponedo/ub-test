# Analysis registered before execution

Primary outcome is receiver-based WeightDuration:
`timeline.weights_end - event_spans.weights_start[0]`, in picoseconds.
The reversal test is strictly `Multicast v2 WeightDuration > Chunk WeightDuration`.
Layer latency and host CPU/wall/RSS are secondary outcomes, not substitutes for
the primary endpoint. Report the exact difference and ratio whether or not the
hypothesis succeeds.

The working prediction is that the N256 natural workload may retain the
3136-Gbps reversal under the unchanged 5-ns allocation service and default
512-entry Jetty window. This is a hypothesis, not a gate: failure to reverse is
a valid result and does not authorize more token counts or reruns. N256 has only
44 replicas across 21 replicated experts, including 3 singleton, 15 fanout-2,
2 fanout-3 and 1 fanout-5 groups. The reduced load/fanout can change the critical
path, so no historical source, target or group is preregistered as critical.

Use all-node aggregate coverage. Identify every actual last-ready weight
transfer after the run, preserve ties, and inspect its source uplink, shared
switch return port, and target forward port. Rank all 64 switch return ports
independently; do not promote historical source 3 by selection. Transfer
`first_native_send_ps`/`last_native_send_ps` refer to native-pop landmarks, not
physical-link TX completion or complete end-to-end RTT.

For each relevant port, use the exact exclusive phase partition of physical TX
busy union, allocator pending excluding TX, and uncovered idle. These must sum
to WeightDuration. Callback requested-service counts, rejected/no-ingress/
successful outcomes, packet counts, and Jetty saturation are complementary
evidence. Overlapping VOQ residence sums are not additive wall time. Phase class
1 combines ACK and transaction response; opcode-separated TPACK and TAACK
counts come from whole-Layer packet counts and must be identified as such.

The observer-only non-matching source/group selectors suppress TA RTT details.
Zero unmatched selected-TA counters under that selection do not prove global
correlation completeness. Rely on global admission/progress/completion invariants,
accepted online validation, drained native state, exact work/bytes and physical
link conservation. Avoid asserting an unexported universal drop counter.

Report successful N256 as a tested reproducer only, not the global minimum or a
repeated-run stability result. There is one formal case per strategy. Report
actual host cost; any historical N2048 timing comparison is descriptive, not a
strict speedup, because the restored host and all-node observation scope differ
from the earlier selected-node configuration.

No result triggers automatic N512, N1024, N2048, window, allocator, framework or
instrumentation experiments. Stop at the pair outcome or first failed gate.
