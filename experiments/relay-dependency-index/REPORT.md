# Relay Dependency Index

## Scope and correctness

Exactly four production changes replace repeated whole-weight-task candidate scans with lookup indexes. Default behavior uses indexes; independent scan controls remain available for the Python adapter, independent preflight, C++ Read and online immutable audit membership. No scheduling/control expressions or task/TA submission/readiness logic changed. The original native/protocol/Planner/router/placement/model/compute/network implementations remain untouched.

Each index derives from the complete old predicate. For GroupChunk, keys are `(expert, offset, bytes)` and vectors include only main-origin transfers. Otherwise the key is receiver physical ID. Candidates append in original global task order. No sorting or count-based readiness substitution occurs. The online audit still checks every member's ready state and finish time. Coverage, per-task/per-TA event ordering, payload bytes, timestamps and terminal validation remain enabled.

### Completed correctness gates

- 20 full Debug comparisons to the accepted production binary: NB, Direct, TwoStage, Chunk and multichunk/multiTA, each in scan/scan, index/scan, scan/index and index/index modes. All event/TA/dependency/payload/native trace bytes match. Stable summary, latency, token and simulator totals match; only measured `verification_wall_ns` is excluded.
- Another 20 full Debug comparisons with diagnostic timers enabled, and 20 exact candidate/index-entry/timer-inclusion checks pass. Generated instrumentation erases to the exact frozen production source and preserves all 18 Simulator expressions (including 11 control expressions) byte-for-byte and in order.
- Python tests cover 160 seeded randomized/adversarial cases, including 80 valid shuffled graphs, plus accepted fixtures and explicit malformed graph checks.
- Full fixed Qwen256 Python preparation and independent reconstruction preserve every transfer and ordered dependency list. Complete canonical graph is 66,328 transfers, 62,232 weight WQEs, 78,336 dependencies; SHA256 `0361b47ac43fae9bc05ecd20ba0cc9f7cd2e08d3a01bf6d4d354000933e7322f`, FNV1a64 `6ada88bf8945a70f`.
- Production C++ Read of the same fixed Qwen input emits byte-identical full graph CSV. This proof executes no simulated layer and is not a latency measurement.
- 64 guarded regression/build/verification commands using the original suites pass, including Planner normal/-O, relay tracker and 120 graph-oracle trials, PairJetty basic/lifecycle cases, original negative tests, and 39 tiered live faults across summary/events/debug. Explicit missing dependency, wrong group, duplicate/reordered dependency checks pass in scan and indexed independent preflight. Premature readiness and duplicate/WQE failure checks remain active.

Exact input/config/transfer/weight-edge bytes match the accepted Qwen preparation. The only plan JSON difference is pre-existing diagnostic `cpu_wall_ns`; an independent complete recursive comparison establishes every actual Planner decision, routing, physical placement and quota unchanged. This exception does not extend to any model/event timing field.

The full historical large integration/scaling matrix was not rerun. This gate reuses the named original unit/lifecycle/negative suites, focused small full-Debug integration fixtures, and exact fixed Qwen256 scenario; see `INDEPENDENT_REVIEW.md` and `regression-results.json` for commands and coverage.

Two initial test harness issues are retained transparently in local raw evidence: a filename-suffix test initially treated JSON telemetry as byte-exact, and one mutation fixture lacked enough parents to test dependency reordering. The corrected harness and multi-parent fixture passed; neither was a product regression.

## Measurement rules

Exact accepted EP64/E128/top-k8/H2048/I768, seed20261016 Zipf1.1, pair Jetty, summary logging, TA1024/chunk4096 and 100Gbps/20ns are fixed. All expensive stages are serialized. Guards remain 300s wall, 6GiB process-tree RSS, 7GiB address space, 1.5GiB host available memory, 8GiB free disk and 2GiB tmp free. No old user data is deleted.

Python preparation and independent preflight are separate processes. C++ Read, online audit, Simulator::Run, terminal FinalAudit and postflight are separately labeled. Nested inclusive CPU times overlap and must not be summed. Index construction and destruction costs remain charged to their owning full scopes. Timed builds measure observer-perturbed performance; unchanged production controls are reported separately. Single observations are not confidence intervals. Truncated runs provide partial progress, not completed layer latency or full-run speedup.

## Measurements

The optimized production Qwen256 run completed under the unchanged guard: **266.486s wall, 266.322s process CPU, 1,545,056KiB peak RSS**. All 256 tokens completed. The executed graph fingerprint matches the exact accepted full graph. Terminal per-byte/per-task/per-TA audit and separate independent postflight pass.

Actual simulated LayerLatency is **5.844141552ms** (5,844,141,552ps), with 66,122 remote WQEs, 485,576 total TAs, 23,439,135 simulator events, 51 replicas and 2,681 pair Jettys. Weight-only totals remain 62,232 WQEs, 470,016 TAs and 481,296,384 bytes. Assignment dispatch/combine accounts for the difference between weight-only and full-layer totals.

This is a completed optimized simulation, while the accepted historical scan baseline stopped at 300s. The ratio 300/266.486 is **not** an exact full-run speedup: the baseline denominator is censored. Isolated fresh A/B stage attribution and observer checks are recorded separately below when available.


### Fresh Python stage attribution

Same cProfile + statement-timer harness, identical input/complete graph, serialized on the same host. These are profiled single observations, not uninstrumented whole-pipeline estimates. Full process CPU includes child processes; statement CPU is Python process CPU. Index construction is included in the dependency span.

| Stage | Mode | Wall s | Process CPU s | Dependency span CPU s | Peak RSS KiB |
|---|---|---:|---:|---:|---:|
| preparation | scan | 204.324944 | 204.507680 | 198.298787 | 197952 |
| preflight | scan | 198.041132 | 197.906035 | 196.705943 | 106368 |
| preparation | indexed | 5.768761 | 5.835829 | 0.107902 | 197436 |
| preflight | indexed | 1.505362 | 1.326741 | 0.149466 | 111184 |

- Preparation: observed whole-stage wall ratio 35.42×; dependency-span CPU ratio 1837.78×.
- Preflight: observed whole-stage wall ratio 131.56×; dependency-span CPU ratio 1316.06×.

Independent preflight remains independent: it reconstructs from validated Planner data and the accepted graph tool, not from the adapter index or a shared helper. It still compares the complete transfer objects, including ordered dependency lists. No checksum-only shortcut replaces reconstruction.

### Fresh complete C++ Read attribution

A separate diagnostic driver calls the unchanged production Read logic, exports the complete graph and destroys Layer; it does not initialize topology or run a simulation. Both modes use the same timed executable and emit byte-identical full Qwen graphs. Read scope includes local index construction/destruction and excludes graph CSV export. Program self also contains export/bookkeeping and is not claimed as pure export time. Whole process cost includes export and teardown.

| Mode | Read CPU s | Dependency CPU s | Index-build CPU s | Process CPU s | Guard wall s | Peak RSS KiB |
|---|---:|---:|---:|---:|---:|---:|
| scan | 89.551843 | 89.256855 | 0.000000 | 89.651707 | 89.747433 | 1000108 |
| index | 0.307382 | 0.021725 | 0.004535 | 0.381876 | 0.503647 | 1001624 |

Observed Read CPU ratio: 291.34×. Actual dependency candidates decrease from 2,437,502,976 to 78,336, while both emit exactly 78,336 dependencies. Indexed build visits all 62,232 weight tasks once. The 0.004535s index-build cost is already included in 0.021725s dependency work and 0.307382s Read; never add these nested times again.

### Actual Qwen runtime and observer comparison

| Read / online membership | Observer | Wall s | Process CPU s | Peak RSS KiB | Whole run |
|---|---|---:|---:|---:|---|
| index / index | production | 266.486450 | 266.321596 | 1545056 | PASS |
| index / index | timed | 268.734594 | 268.610842 | 1545168 | PASS |
| index / scan | timed | 300.640090 | 300.359536 | 1536300 | Partial: wall guard in FinalAudit |

The completed timed index/index run matches every stable production summary field, including 5.844141552ms LayerLatency, graph/payload fingerprints, per-node traffic, 23,439,135 events, and all token/WQE/TA totals. Separate postflight passes for both. Only `verification_wall_ns` differs. The observed +0.84% wall difference is a single-run production/timed comparison, **not an isolated causal estimate of instrumentation overhead**. Timer/counter overhead and code layout/host variation remain included; no correction is subtracted from phase times except explicitly measured snapshot serialization CPU.

The Read-indexed / online-scan run reached the unchanged wall guard during terminal FinalAudit. Its cooperative final snapshot records all 256 token completions, all 485,576 TAs, all 66,122 sender completions and zero pending replica weights, but FinalAudit had not completed. Thus it has **no successful whole-run validation, no postflight and no completed LayerLatency point**. It is retained as partial evidence, not relabeled PASS because simulation progress reached the end.

### Complete online membership scope within the partial control

A narrower completed-scope comparison is valid: both profiles have all 11,520 group-ready and 51 replica-weight-ready audits completed, zero active calls for those phases, and identical exact checked-member counts (23,040 group members and 62,232 replica members). Index construction also completed. The scan control then timed out later in a separate terminal audit. These counters, complete-call state and source/graph equality establish scope completion; they do not establish completed terminal validation.

| Online subphase | Scan CPU s | Indexed CPU s |
|---|---:|---:|
| Immutable index build | 0.000000701 | 0.004522132 |
| Group membership audit | 21.329433505 | 0.051152543 |
| Replica-weight membership audit | 0.030070908 | 0.001123257 |
| Non-overlapping sum of these completed scopes | 21.359505114 | 0.056797932 |

Observed targeted CPU ratio is 376.06× including indexed construction. Group candidate visits fall from 716,912,640 to 23,040, and replica candidate visits from 3,173,832 to 62,232. Every matching member's readiness and maximum completion time remains checked. Online map destruction is part of Layer teardown and whole-process cost, outside the targeted membership sum; no uncompleted teardown comparison is claimed for the partial control.

Do not divide the 300s cutoff by the optimized completion time to claim a full-run speedup. Do not add inclusive Audit, Send, Ready and Simulator::Run scopes: they overlap. The separate runtime-self chart uses disjoint self CPU with explicit complete/partial labels. Simulator::Run self contains uninstrumented native and application work, not exclusively native CPU.

## Interpretation and remaining cost

The four indexes remove repeated candidate searches while retaining all matching-member and payload checks. The fixed Qwen case now has a fully validated production result within the existing 300s limit. This does not make full validation free: in the completed timed run, Read is 0.304s CPU, Simulator::Run is 238.262s inclusive, and terminal FinalAudit is 29.453s. Nested Audit is 2.469s, Validate 18.490s and Send 24.906s inclusive; these nested values overlap and are not additional runtime totals. The 192.295s Simulator::Run self bucket includes native and uninstrumented application work. No new sample-based native hotspot claim is made in this milestone; prior sampled findings describe their own historical partial windows.

No further native/protocol/Planner/compute/network optimization is included. Remaining runtime costs are outside the four allowed changes. The accepted baseline and exact original Qwen inputs remain intact; source invariants, independent scope review, build provenance, compact runtime snapshots and raw-file hashes accompany the report.
