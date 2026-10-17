# Relay Dependency Index: controlled equivalent optimization

## Claim and treatments

Replace only four repeated candidate scans with immutable lookup indexes: Python adapter dependency construction, independent Python preflight dependency reconstruction, C++ Layer::Read dependency construction, and online replica/group membership lookup. Each retains a scan mode. Expect lower preparation/initialization/audit CPU with identical actual decisions, graph order and simulation outcomes. Falsification: any dependency, membership, event, payload, TA, token, timing, or gate difference.

Accepted baseline remote `1322262a6764b51b6959e9df47defc11361bfa3d`, local `0697146f40a09d08ecdcef517a47357ed5f9995a`, tree `0439285dc1eca9956f9699f47b4ea22e4050e08a`. Work is isolated on `perf/relay-dependency-index`; baseline and native trees remain unchanged. Historical large evidence is sparse-excluded, not deleted from the baseline.

## Fixed controls

Exact accepted Qwen256 input, EP64 E128 top-k8 H2048 I768 seed20261016 Zipf1.1, pair Jetty, summary logs, TA1024 chunk4096, 100Gbps/20ns. 62,232 weight WQEs, 78,336 dependency links, 470,016 weight TAs, 459 MiB weight payload. Native tree `c27d1faef570e6da9900a71aa0a37180a58dfba8`, standalone `-std=c++20 -O3 -g`.

No scheduling, submission order, ChunkReady/WeightReady semantics, native/protocol/Planner/router/placement/compute/network/chunk/TA/Jetty modifications. Every old predicate is represented by the key and every matching member is still checked individually. Vectors append in original task/edge order. Online indexes are built before any simulation event and are immutable thereafter.

## Matrix and checkpoint gate

1. Python scan/index complete dependency graph equality, independent reconstruction and adversarial predicate tests.
2. Small NB, Direct, TwoStage, Chunk, multichunk/multiTA full Debug output comparisons to accepted baseline; all four C++ flag combinations. Compare full event order/time, WQE/TA, graph, payload bytes, latency and token outputs. Only nondeterministic observer wall telemetry may differ.
3. Original subsystem regression and corruption/fault rejection checks.
4. Actual Qwen256 summary run with index/index, isolated Read-only and online-only treatments and scan baseline under unchanged resource limits. Separate fresh Python measurements from simulation initialization/online/terminal validation. Generated timer instrumentation must erase byte-exactly and keep simulator control calls unchanged. Report measured CPU/wall, nested scopes and observer perturbation separately; do not sum inclusive scopes.

All expensive work serialized. Per process group: 300 seconds wall, 6 GiB tree RSS, 7 GiB address space, 1.5 GiB host available, 8 GiB free disk, 2 GiB tmp free. No old data deletion or guard relaxation. At guard cutoff retain partial progress and mark incomplete; never invent completed LayerLatency. Large local logs/profiles/payload are hash-manifested, only compact proofs/reports/CSV/figures committed. Freeze a clean commit for independent parent review; no worker push.

## Attribution refinement (before new A/B execution)

After the production index/index run completed, use complete standalone Read scan/index graph-export runs for Read attribution and full actual timed index/index versus index/scan for online membership attribution. Read CPU scope excludes CSV export, which is additionally exposed in process wall/CPU. All four combinations retain small Debug parity. This design avoids claiming speedups from unequal-progress 300s cutoffs; additional full scan/scan runtime is not necessary when same-input accepted timeout evidence and a complete fresh Read A/B already establish the control cost. The accepted historical timeout is explicitly labeled historical. Large timed runs must match the newly completed production output exactly apart from observer wall telemetry, or be labeled partial at guard cutoff.
