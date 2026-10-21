# Pre-registered network-rate experiment

Accepted source: 3c2275e, unchanged. Run the existing roofline executable and existing independent correctness verifiers. True Qwen serialized layer 37, first 2048 tokens, EP64, 128 experts, top-8, hidden 4096, intermediate 1536; compute 100 decimal TF/s and HBM 2692 decimal GB/s. Four strategies: no-balancing, direct, chunk-streaming, multicast-v2.

Only intervention: network link_gbps 100 -> 3136 (decimal Gbit/s) in runtime/parameters configuration and execution-input token 12. No compute, allocator, planning, routing, topology, packetization, scheduling, simulator-source or native-source changes. Preserve all other execution-input bytes. No elapsed-time multiplication or synthetic timing estimates in place of measurements.

Prediction: increasing link bandwidth reduces network serialization and may reduce communication time, but the unchanged 5 ns allocator service time limits the gain. Compute may dominate total latency. Falsification: no reduction in communication timing, unexpected end-to-end regressions, or any correctness failure. An unexpected timing result is evidence, not grounds for silently changing the model.

Checkpoint decision is continue_full_matrix: after the small-stage PASS, run all four true 3136 Gbit/s cases unless a correctness or resource failure requires stopping. Baseline reuse is a separate, explicit evidence/hash-parity decision; this harness does not silently reuse 100 Gbit/s results or claim parity from labels.

Before true admission, the small-stage gate must prove both rates and all four strategies pass, the native DataRate probe passes, and fault smokes pass, against the exact source and binary identities. Preparation enforces accepted routing/manifest/counts hashes and accepted balanced Planner and assignment hashes. Execution validates immutable config, plan, graph, assignments, input, build libraries, original input artifacts and source hashes before and after each case.

Resource policy: at most two adaptively admitted case processes, retaining at least 1 GiB whole-host available memory. Each guarded subprocess has a 6 GiB tree RSS ceiling, 7 GiB address-space ceiling, 4800 s total case limit including verification, minimum 8 GiB free output disk and 2 GiB free /tmp. Admission uses historical measured per-strategy peaks, a 5% margin, 128 MiB extra, pending growth of active cases, host CPU/load and disk floors. Any failure stops further admission and terminates owned active processes. No unrelated process is killed.

Raw routing, traces, per-token and pair-state evidence remain private. Publish only aggregate conclusions and sanitized hashes/commands/resource records. Parent owns build/runtime and final publication.
