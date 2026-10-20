# Exact input and resource admission

Read-only source audit,2026-10-20,before simulations. All8 original request files present; Git blob or canonical LFS pointer hashes and historical SHA256s matched. Independently reconstructed L37 first2048 record-0 routing entries in manifest order; exact equality and2048 unique request/ordinal pairs. No synthetic routing substitution.

- Private manifest SHA256: d5708f02b9ffa6e19500725685272ad840760d9c6b5f5f475f12bc3560405db6.
- Frozen count table SHA256: e3163d85c2ada0373cb73dad19a3efeac7d0774f1b56852aacdcf9b264c94c4e.
- L37 routing SHA256: 4b2f70871b969730a8f85aace4357d28b2e069d2f0d16a738a0c35eca691a0e5.
- Historical treatment semantic plan SHA256 (only cpu_wall_ns excluded):55b8de3bc0e6773ac265f84883f4c2940ec5ff9e049b29fcccbfb6275a0f0f94.
- Historical treatment assignments SHA256:1a7f767d035076f898f5ce7ee8ab02d65eb9f40d057cc2c99931e97c9c1bf566.
- NoBal semantic plan intentionally different:a9292a0340d86e706b40d4f499e9cbac58efea8be9916c9b49350f594abd235e.

Actual model: EP64,128 experts,top8,N2048,H4096,I1536,three matrices,BF16 activations,ideal FP8 weight18874368B/expert excluding scale/padding.1024B TA,4096B relay chunk,100Gbps,20ns,single switch,500 effectiveGFLOP/s assumed. Payload seed20261015,compute setup100ns; treatment planner/reroute200/100ns,NoBal0/0. Planning/reroute duration parameters are existing simulation assumptions,not measured planner CPU/actual routing-network duration.

Planner fixed main placement e//2,slots2/rank,beta1.01,min_replica_quota1024,upstream-compatible,allow_zero_main=false,rounding=code,epsilon.01,kernel_stage1,locality_aware. Relay minreplicas4,maxrelays8,minfanoutgain2,no forcing/reorder/slow-relay in real run. Do not copy stale30B metadata from generic fixed-config.json: real preparation overrides dimensions/precision to235B.

Historical wall/CPU seconds and peakRSS KiB: NoBal129.570/129.435/817116;Direct725.152/723.437/3828316;Chunk1220.776/1212.864/3711104;oldMC728.917/726.048/3900248. Source: ../qwen-real-multicast/results/host-resources.csv and original private resource records. These are budgeting evidence,NOT new performance results.

Keep3600s/stage (four simulator maximum14400s),6GiB process-treeRSS,7GiB address space,8GiB free work disk,2GiB free tmp,1.5GiB available memory. Sequential only. Both logical payload8GiB and weight-task1000000 limits identical for every strategy. L37 logical payload1268776960B,application arrays lower bound2269118464B,not peakRSS prediction. Historical actual peak3.720GiB. Recheck capacity and host availability before real runs; no widening on failure without diagnosis.

L37 expected planner fanout histogram {1:2,2:11,3:7,4:2},22 experts,53 weight children,976896 weight TAs. V2 maxframe atF4 is24+76*4+1024=1352B; each downstreamnativeWRITE1102B; singleton1102B. Compare to unchanged1048576B ingress reserve,524288B egress,160B cell,6553 initialcredits. New MC must use same pair endpoint inventory as Direct; old per-child endpoint experiment is not a fair baseline to substitute.

Real routing is an offline concatenation of public request traces,not an observed serving batch. Source-rank mapping tokenOrdinal%64 and compute throughput are assumptions; record-0 phase/layer IDs do not independently prove tokenizer/model execution. Transmitted payload bytes remain deterministic correctness data,not actual model weights/activations. Do not publish rawtrace,request identities,per-token configuration or payload files.

## Final re-admission after preserving assertions
The first uniform assertion-enabled NoBal diagnostic completed in816.637s, not the historical129.570s (historical native assertions were OFF). It was validated but excluded from the final comparison. Direct was operator-interrupted before a result; this is not a timeout or protocol failure. The new optional RR hook's repeated failed attribute metadata scan was removed using a presence-only static-TypeId cache; all assertions/checks remain enabled. Matched EP64 synthetic NoBal CPU fell16.821434→5.037383s, with identical events/results; paired-window host wall fell11.4→2.52s. These are admission evidence, not extrapolated real performance results.
Retain3600s per-stage cap for ALL final real strategies. Add a conservative between-case gate: if fresh NoBal exceeds380s, stop before admitting larger cases because historical relative work ratio projects Chunk beyond3600s. This projection is a heuristic, not a result. Final four modes use the same cached native library; none substitutes the first diagnostic baseline.

The rounded380s gate was subsequently replaced by the exact projection: measured NoBal wall ×1220.776/129.570 must not exceed3600s. Final NoBal380.460457s triggered the rounded check, but projects3584.603s under the exact formula. An explicit hash/receipt-checked continuation preserved that same final-library baseline and admitted the three still-unrun treatments under unchanged3600s guards. The original stopped ledger remains intact; no earlier diagnostic result is substituted. The narrow headroom is not a promise of completion: an actual runtime guard failure still stops the matrix.
