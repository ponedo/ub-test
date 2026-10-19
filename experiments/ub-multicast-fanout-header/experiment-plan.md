# UB Multicast Fanout / Header controlled communication experiment

Approved by user 2026-10-19. Parent delivery b2b990d1fea69f7e1a1e7ed615494f821aa71913; native baseline b8375b51a094d3b1217b697989e1ab979f609e64.

## Claim and boundary
Measure how recipient fanout and explicitly hypothetical envelope bytes interact for one expert weight distribution. No Planner runs, no routing trace, no token assignments and no expert compute. Resident 128 expert metadata retained; only expert0 is copied. This is a controlled weights-only fixture, not an UltraEP placement decision or MoE Layer benchmark.

## Controls and treatments
Fixed 64 NPUs + one switch; source0; destinations1..F in ascending order;100 Gbit/s,20ns;18MiB deterministic payload seed20261016;TA1024;Chunk4096;native VL7,queues,CBFC,window,ACK/Response defaults;existing Pair Jetty/direct,existing relay graph and native multicast children. No resource-model adjustments.
Fanout F=1,2,3,4,8. Main matrix Direct,Chunk,full multicast,compact-oracle multicast (20).
Optional supplement ideal-oracle multicast at all5 fanouts (5), only after main matrix passes guards.
Header interaction block changes ONLY actual transmitted envelope bytes for a fixed multicast group; original native headers/tags omitted from oracle frames are restored from bounded context. Payload remains in received packet bytes. Singleton always retains original native WRITE bytes.
Full=P+32+137F; compact-oracle=P+32+16F; ideal-oracle=P+32 for F>1. Common32=DL4 + magic/group/sequence/payload_length/member_count/bitmap28;compact per-member16=rank,destinationTP,PSN,SSN four32-bit fields. Omitted context and metadata have zero modeled control-plane cost: explicitly Oracle, not a decoded UB protocol implementation. No changes to native protocol source.

## Preregistered predictions
For F=1 all multicast header modes must be exact native singleton equivalents. For largerF full multicast should reduce source payload injection relativeDirect but charged branch header grows withF and can offset savings. Compact/ideal may reduce recipient serialization andCBFC cells; speedup versusChunk need not be monotonic because relay activates onlyatF4/F8 and stillusesboundedresources. A slowerorflatmulticast result is retained. Failure of singleton/full baseline event parity, byte budgets, feedback, per-target coverage orcredit conservation invalidates comparison.

## Relay rule
Reuse DirectWeightDistribution/ChunkStreamingRelay without modification. Defaults minReplicas4,maxRelays8,minFanoutGain2,forcefalse; ordinalreplicas ascendingrank. Existing sqrt-based rule chooses2relays atF4/F8 andfallbackwholeexpertDirect atF1/F2/F3. Full18MiB shardCut12MiB, FC1/FC2 boundary; small12KiB fixturecut8KiB. All graphs and dependencies independently verified.

## Evidence and protection
Small12KiB all25 combinations first, legacyfull parity and fault checks. Main20 sequential thenoptional5. Exact decodedmetadata andactualwirecounts, per-targetreceiverready/sendercomplete, packetandfeedbackcounts, queuepeaks/residence, per-portCBFCconservation, nativewindow checks, onlineallbytes/perTA audit, independentpostflight. Normal Summary; one boundedDebug parity fixture. No full18MiB payload/packetlogs persisted.
Per-stage3600s,6GiBRSS,7GiBAS,minfree8GiBdisk/2GiBtmp/1.5GiBhostmemory. Stoponanyprotectedstoporcorrectnessfailure; noauto-relaxation. Development harnesserrors maybefixed thenrerunwith evidence. checkpoint_policy: continue_full_matrix onnegativeperformance; safety/correctnessstop overrides.

## Artifact contract
Per-case summary/online-summary/validation JSON,networkpacketandqueuestats,receiverstats,CBFCports,graphandidentityhashes,resourceJSON, independentvalidation. Aggregate CSV/charts/report/sourcepatches onlypublic;largepacket/payload/privatepaths excluded. Finish remoteSHA/fileverification thenstopforacceptance.

## Additional bounded correctness gate (specified before execution)

Copy the accepted multitarget test fixture into an isolated header-mode test. For full/compact/ideal: original three-target, dynamic members, native window2, original1600Bqueue/10cellCBFC pressure, and missing/duplicate/wrong native feedback (21cases). Only these correctness fixtures vary windows/queues; main matrix controls unchanged. Use actualPayload bytes/SHA, wire serialization and cross-linkcredit counts. The compact/ideal treatment must still block/recover underfinite resources. Stopanddiagnoseifvalidationfails.
