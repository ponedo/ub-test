# Qwen prefill token scaling

Frozen control is accepted remote e5494d274b4b80f643809f86e7a3b52bc632657f, local 9059c77d6f4081e7602b1df181752380d16fc29b, tree 27a64ee042984c687c7800d13510851718a538d0. No Planner, placement, routing, Relay, network, compute, native, WQE, TA, packing or optimization changes.

Vary total EP-group tokens 512, 1024, 2048, 4096. Reuse accepted completed 256 control. At each new level run No Balancing, Direct, Chunk-streaming in order, and advance only after independent preflight, online and independent postflight validation for all three. Stop the entire scale on any failed stage or resource guard. Failed and unreached arms have no LayerLatency or speedup point. Identical routing hash across each trio; Direct and Chunk plan equality required.

Controls: EP64/E128/k8; H2048/I768/BF16; expert weight 9437184 bytes; synthetic seeded Zipf1.1 router seed20261016; effective compute500GFLOPS; 100Gbps/20ns; TA1024; chunk4096; pair Jetty; summary logging with full online validation. See fixed-config.json for complete controls.

Prediction: increased tokens may amortize replicated weight distribution and expose a Direct crossover; Chunk may reduce readiness delay. More replica growth may offset amortization. These are hypotheses; falsified if measured ordering/amortization does not follow. No hardware or real-router inference.

Each Preparation, Preflight, Simulator and Postflight receives an independent 3600-second wall limit. All other bounds unchanged: process-tree RSS6GiB, address space7GiB, free disk8GiB, free tmp2GiB, available host1.5GiB. Logical payload budget8GiB, weight WQE1M, assignments100000. No automatic relaxation/retry after resource failure. Interrupted attempts retained and require state inspection before any retry.

Evidence: stage commands, resource ledger (wall/user/system CPU/maxRSS), separate preflight/postflight reports, online validation, planned counts distinguished from actual completion counts, exact capacity arithmetic, routing and input hashes, source/binary/native provenance. Reuse accepted regression results only for byte-identical subsystem sources; clearly label not rerun. Collect small aggregates, CSV, four figures and report; no raw TA, Packet or payload publication. No extra formal profiling.
