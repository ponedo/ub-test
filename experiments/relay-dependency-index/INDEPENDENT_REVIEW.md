# Independent correctness and regression review

## Production code: PASS

Reviewed all four changed production files against the accepted local baseline. The adapter indexes incoming destination and main-origin `(expert, offset, length)` candidates. Preflight independently reconstructs from graph-tool edges and validated plan, without consuming adapter dependency lists or importing adapter logic. It still compares the complete ordered transfer objects and executed canonical graph when supplied. Existing identity, quota, placement, input-contract and capacity checks remain intact.

C++ Read uses the same predicates, appends candidates in original transfer order, and retains the original add-parent predicate, coverage notification and dependent insertion. Duplicate candidates retain multiplicity; returned dependency lists are separate copies. Keys do not incorrectly include relay/group identity absent from the original predicate. Both C++ and Python preserve empty-vector behavior. All key component types cover the original fields without narrowing.

Online indexes are built before events. Group and replica checks iterate every original matching task, require its ready flag, and calculate the same maximum completion timestamp. They do not substitute counts for readiness or skip coverage checks. Empty membership retains prior behavior; this optimization does not claim to strengthen that pre-existing case.

## Executed regression evidence: PASS

`regression-results.json` contains 64 accepted command outcomes, no resource-guard triggers, plus eight independent full-contract dependency mutations. Runtime failures in negative tests are expected and checked against their specific error, not treated as generic successful rejection.

- Original Planner numeric bounds, full planner tests, extracted replication reference and compatibility scripts, each normal and Python `-O`, in an isolated copy
- Original relay tracker, including out-of-order/tail/duplicate/conflicting duplicate/bounds/union coverage checks
- Original 120 topology/reference-oracle trials, with 79 ordering-sensitive and 99 global-load-sensitive differences
- Original six PairJetty basic probe cases and six directional/cancel/fail/wrap lifecycle cases
- Original tiered helper tests and nine valid/tampered preflight cases
- Fresh candidate Debug runs and strict verification for the multi4 canary and slow-relay8
- Original PairJetty nine live fault rejections, duplicate-notification execution with strict summary/payload/graph equality, and two independent verifier corruptions
- All 13 original tiered fault types in summary/events/debug: 39 correctly rejected runs, including missing/early WQE, duplicate completion, premature readiness, early-group readiness, relay corruption and early final readiness
- Missing dependency, wrong group, duplicate dependency and reversed dependency list rejected independently in both scan and index preflight modes

The first harness attempt correctly refused a reordering test whose canary had only one parent. The test was rerun using slow-relay8, which contains multiple parents. This is recorded as a fixture-setup failure, not a product regression. Previously passed commands were not silently rerun or discarded.

## Scope limitations

The historical complete 48-case Direct/Relay/NoBalancing integration matrix was not rerun. The original topology/tracker/subsystem tests and fresh candidate native/fault executions above were actually executed. Existing accepted basic/lifecycle probe binaries test unchanged subsystem code; fresh candidate pair-layer is used for the changed execution path and live faults. Large historical evidence was not restored.

## Parity and performance review

Independently inspected `parity-final.json`: 20 complete Debug comparisons, covering NB/Direct/TwoStage/Chunk/multichunk-multiTA with all four C++ toggle combinations, passed against the accepted baseline. Hash comparisons include executed graph, events, payload, TA identities and native trace files. Stable online/validation/simulator metrics match; only documented observer wall telemetry is excluded. This is event/order parity, not only final-result equality.

Final numerical scope review: PASS. Fresh complete Python preparation/preflight compare identical graph outputs under the same profiling harness. Complete C++ Read A/B uses one timed executable, includes index construction and local destruction, excludes graph export, and emits the same full graph. Read CPU is 89.551843289s scan versus 0.307381791s indexed. Dependency candidates fall from 2,437,502,976 to 78,336 without changing the 78,336 emitted links.

The production indexed Qwen256 run completes in 266.486450261s wall, with 256 tokens, 23,439,135 simulator events and 5,844,141,552ps LayerLatency. Terminal validation and independent postflight pass. The timed indexed run also completes and matches stable output, at 268.734594468s wall. Their difference is an observed single-run measurement, not an isolated causal instrumentation-overhead estimate.

The timed index/scan control is explicitly incomplete: 300.640089718s wall cutoff during FinalAudit, with one active and zero completed terminal-audit calls. It must not be presented as a successful full run or assigned a completed LayerLatency. Nevertheless, all targeted online group/weight calls and index-construction scopes are complete in both treatments: 11,520 group and 51 weight calls, no active calls, identical 23,040 group-member and 62,232 replica-member checks. Group+weight+build CPU is 21.359505114s scan versus 0.056797932s index. This supports a complete targeted-lookup scope comparison, not a whole-Audit or full-run speedup. Runtime CSV correctly leaves completed metrics blank for the cutoff.

Inclusive scopes overlap and are not added together. The historical full-scan baseline is censored; neither its 300-second cutoff nor the fresh terminal cutoff establishes exact whole-run speedup. Final artifact hash-manifest verification remains a separate packaging gate.


## Final source and artifact syntax freeze

Rechecked all four production source SHA256 values and the production binary against the executed regression proof: unchanged. All 20 diagnostic parity comparisons remain PASS. git diff --check passes; 20 experiment Python files compile and 19 current JSON artifacts parse. This review text is frozen before final manifest generation; final hash verification will be reported without modifying frozen files.
