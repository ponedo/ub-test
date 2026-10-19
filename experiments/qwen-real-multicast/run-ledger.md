# Run ledger
2026-10-19: accepted sources/native/binaries hashes all verified. Static capacity and historical reuse audits in progress. No simulation yet.

2026-10-19 09:33 UTC: L37 No Balancing, Direct and Chunk Streaming completed, online and independent postflight PASS. Layer latencies, WQE/TA counts, key timeline and final hash match historical cases. Multicast running.

Harness review found that whole plan.json SHA includes measured planner CPU wall time. Raw files/hashes are retained; identity gate corrected to canonical plan hash excluding only top-level cpu_wall_ns. All routing, placement, quotas and other fields remain compared. The initially loaded driver will retain its old gate through completion of L37; any resulting harness-only assertion will be preserved and independently adjudicated before resuming. This does not change any generated simulation input or binary.

2026-10-19 11:10 UTC: All12 fresh simulations,48 guarded stages and online/independent validations PASS. No protection triggered. L0,L37,L52 semantic plan gates pass. All9 historical baseline input files byte-exact; simulated summaries equal excluding only verification_wall_ns; metrics equal. Final source integrity71 acceptedprojectfiles and108 nativefiles unchanged. Current regression48/49native with the same known missingparser suite failure; concurrent,singleton,oldmulticast,network and fourapplication regression checks complete. Threeharness tests PASS. Detailed output retainedprivately; onlyaggregateexports preparedforpublication.
