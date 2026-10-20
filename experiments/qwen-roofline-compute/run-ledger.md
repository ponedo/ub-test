# Run ledger

2026-10-20: Fresh accepted project checkout restored; native109source hashes match accepted integration candidate. No simulation yet. Host 9.73GiB visible,9logical CPUs,no other visible sim; reserve4GiB.

Native first invocation failed before configure because restored tools were not on PATH; retried with existing real-batch-build-tools. Configure PASS. Full native-j4 build stopped at248.867s by4GiB host floor, sampled tree RSS3.762GB; partial archive840MiB occupied tmpfs. Removed only this task-created partial archive, resumed same build-j2 with stricterguard, no source change. User subsequently authorized1GiB floor for future stages.

2026-10-20 20:00 UTC: Full native-j2 resumed build PASS204.51s; all4 executor/probe builds PASS. Stage A:16 independent model positive checks and6 negative parameter/overflow checks;16 parent vs16 new Legacy cases exact,16 Roofline cases PASS,6 network/scheduler smoke PASS,4 correctness negatives and7 invalid CLI cases rejected. No extra native semantic change.

Real preparation independently re-audited original raw source, exact routing/manifest/count hashes and accepted Planner/assignment identities. Single coordinator admitted NoBal+Direct, then Chunk afterNoBal, then v2 afterDirect. All4 real cases passed simulator/postflight/independent-network/independent-compute checks. Minimum sampled available memory1,592,373,248B; no real simulation guard fired.

2026-10-20 20:17 UTC: Four strategies complete; coordinator exited0. NoBal2.215507444ms,Direct7.395192433ms,Chunk5.679449313ms,Multicast3.957930193ms. Weight times unchanged. Multicast/Chunk layer speedup1.434954392x but Multicast/NoBal0.559764153x. Results and two plots generated and visually inspected. Collector rerun against private receipts produced byte-identical published outputs. Reproduction shell syntax checked; full expensive reproduction not repeated.

2026-10-20 20:21 UTC: Publication privacy review withheld per-connection TP sequence/state CSVs. Public output now uses endpoint-free transport-state-summary.json (window drain booleans and pending-state totals). Detailed CSVs retained privately; no simulation or validation was changed. Collector with privacy reduction re-executed successfully.
