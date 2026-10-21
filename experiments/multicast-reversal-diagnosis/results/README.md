# Selected evidence

These files contain aggregates for
six selected physical resources and bounded event excerpts, not full per-node,
per-expert or raw-packet histories. Queue pointer identities are omitted. Packet
references are local ordinals within each strategy, not unique fragment IDs.

All times and durations use picoseconds unless a column says otherwise. Classes
0, 1 and 2 mean stage-2 weight, ACK/transaction response and other traffic.
Native cohort metric names are supplied explicitly. A full residence whose end
falls within the weight phase is not clipped phase occupancy. Service-start and
outcome-end cohorts have different boundary membership. Their sums overlap and
must not be added as wall time.

The gap-accounting and prefix-callback-union tables are exact interval/count
identities, not estimates of the speedup from an unperformed intervention.
AllReady rows contain mutually exclusive first-failing observations; held spans
are not continuous waits. The Jetty cycle is an audited reconstruction from TP
counter events, not a direct Jetty SSN sample, and does not classify total idle.
The evidence manifest explicitly identifies its observer version.

Selected critical events retain native auxiliary fields for source-level audit.
Their meaning is event-specific: TX-start aux0 is serialization plus explicit
delay duration, aux1 is busy duration, and aux2 is explicit delay; grant-start
aux0 is requested allocation duration; allocation-select aux0 is input port
and aux1 priority; VOQ aux0 is post-operation depth. Do not interpret the
auxiliary columns as a common quantity across event kinds. Packet occurrences
were traced backward from the final receive, not grouped solely by reused UID.
