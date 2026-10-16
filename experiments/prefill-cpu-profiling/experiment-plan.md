# CPU diagnosis, 2026-10-16

Authorized base a5aa51ab19c251c9220872d4b74f30bbcae25889; native d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b. No optimization in this module.

Claim to test: lifecycle lookup may dominate large NoBalance cases and show superlinear scaling. Alternative: topology, registration, ACK-window initialization, logging, or verification dominates. Falsification: real sampled CPU and measured scoped cost show another dominant path, or lifecycle cost does not grow superlinearly. Source loops alone do not establish measured complexity.

Fixed: EP64 E128 top-k8 single switch, seed20261016 weighted sampling trace prefixes, H64/I128/bf16/3 matrices, unchanged native/model/protocol, WQE/TA/Relay and logging/checks/caps. Reuse accepted capacity generator, adapter, verifier and guard. A=5000,10000,20000,50000; T=A/8. No 100K.

Sequential treatments per scale: original release baseline; same original with perf cpu-clock:u 99Hz DWARF8192; isolated scoped-timer diagnostic native build at O3 + g. Original executor is O3 DNDEBUG, not helper O2. Timers measure inclusive/exclusive CLOCK_MONOTONIC_RAW wall, not sampled CPU; nesting avoids exclusive overlap. Inlining/code layout and timer perturbation are measured, not assumed negligible. Counters are single-thread only (MTP disabled).

Artifacts: complete raw input/output/logs, resource counters, perf.data, full perf reports/stacks and Top20, folded stacks/flame SVG, timers and scope map, patches, exact build flags/IDs/symbols, full-file parity and strict verifier outputs, regressions, report and plots. Runtime trace is never reduced. Archive raw output losslessly after measurement.

Budget: generate/planner/adapter180s each; baseline600s; perf/timed900s each; verifier300s. Guard treeRSS8GiB, cgroup12GiB, address-space12GiB, case6GiB, workspacefree8GiB and tmpfree2GiB. Old regressions1800s. No concurrent builds or simulations. On correctness/resource failure stop expansion and preserve failure. Tool capability probe failure selects honest fallback or blocks, never changes sysctl/security.

Checkpoint after each variant: process exit and guard PASS, strict verifier PASS. After each scale: exact hashes of full run files and counters across variants. Proceed automatically after passing (authorized). Preserve no-data/failed/skipped rows. One paired run per scale, no statistical confidence claims; report fixed execution order and environment drift limitations.

Phase evidence: whole-process wall/user/sys/RSS from guard, internal main/read/artifact/topology/SimulatorRun/payload/cleanup wall spans, real sampled self CPU by symbol. Registration/lookup/CreateJetty/SubmitWqe/ACK resize nested spans are not additive. ACK explicit ResizeReset excludes constructor member allocation; CreateJetty inclusive covers that allocation but cannot uniquely attribute it.

Implementation detail before first timed case: coarse scopes additionally record thread CPU time and process RSS high-water at exit. High-water is historical, not per-phase isolated memory. Fine scopes do not call CPU/RSS syscalls.

Configuration audit during 50K: trace generator RNG seed is 20261016. The inherited payload-byte/runtime seed field is 20261015, exactly as accepted capacity baseline; no parameter was changed. Full fixed runtime snapshot: evidence/fixed-runtime-config.json.

Post-measurement publication safeguard: known inherited credential bytes were found in raw DWARF stacks. Local raw originals are retained; publish.py creates equal-length redacted copies and requires byte-identical decoded perf script output. No simulation/profiler trial is changed or rerun. All other raw artifacts remain byte-identical.
