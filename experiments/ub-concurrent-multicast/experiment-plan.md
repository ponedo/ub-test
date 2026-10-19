# Bounded concurrent multicast integration experiment

## Claim and controls
Can a bounded set of expert groups use native source RR and shared physical ports concurrently, preserving child native WRITE completion and target-driven WeightReady? Can the new strategy execute the same accepted small MoE plans as Direct/Chunk?

Control: accepted lightweight adapter c28c18c7 and unchanged Direct/Chunk application paths. Treatment: one registered SharedSource per expert group, dedicated native child endpoints, strategy 3. Same topology, native RR/VL7, 100Gbps/20ns, compute, Planner, token trace, weights and segmentation. No large Qwen workloads.

Expected result: source payload transmitted once/group; online correctness and per-child feedback preserved. Lower source payload does not guarantee lower layer latency. A slow child can limit its group through the all-child-ready barrier; other groups remain native allocator candidates. Fairness is packet service opportunity including control packets, not byte or wall-time fairness.

## Fixed matrix
- Adapter: same source overlapping groups; different sources; third operation with different members starts while previous groups live; window pressure; finite CBFC pressure; duplicate/wrong/missing feedback rejection.
- Old singleton seven-case exact byte/time gate.
- Application: single4, slots_zero4, multi4_force, tail4, multi_expert8, slow_relay8, topk2_4 (explicit two-expert-per-token and same-source group coverage). Each Direct/Chunk/Multicast shares byte-identical plan and assignments.
- Representative Debug/summary parity and independent strict Debug oracle.
- Old four strategy regression; accepted network multicast and native tests.
- Fail closed tests for corrupted weight, premature WeightReady/WQE completion, duplicate and missing completion, and mutated independent membership evidence.

## Artifact contract
Per case: source hashes and input configuration, host resource result, online validation summary, actual statistics and independent preflight/postflight. Bounded adapter and selected Debug traces stay private; small selected summaries and hashes public. No restricted routing data used.

## Checkpoint policy
Stop on unexplained correctness failures; retain failed artifacts and investigate. Do not broaden native protocol scope or resources. One compile/test process at a time. Per-stage 3600s, RSS6GiB, address space7GiB, free disk8GiB, /tmp2GiB, host available1.5GiB. Native full suite's pre-existing missing parse_trace.py failure remains explicit, not PASS.
