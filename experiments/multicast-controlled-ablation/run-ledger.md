# Controlled ablation run ledger

## Final disposition

Six unique experimental cells are PASS. Both A rows are UNSUPPORTED and have no
performance values. The original allocator is unchanged; no A+B case ran.
All original inputs and runtime sources stayed frozen. Default TA window stays 512.

| Case | Status | Whole-case wall seconds | Kernel-reported peak RSS GiB | Successful attempt |
|---|---|---:|---:|---|
| baseline-512-chunk-streaming | PASS | 977.786 | 3.596279 | original |
| baseline-512-multicast-v2 | PASS | 673.419 | 3.704288 | original |
| window-1024-chunk-streaming | PASS | 990.407 | 3.596840 | original |
| window-1024-multicast-v2 | PASS | 748.087 | 3.716568 | original |
| window-2048-chunk-streaming | PASS | 992.313 | 3.597530 | original |
| window-2048-multicast-v2 | PASS | 945.819 | 3.756607 | retry 1 |

Both fresh 512 cases passed exact accepted full-summary parity (excluding only
verification_wall_ns) and byte-identical ordered expert-compute, expert-ready,
and replica-ready outputs. All changed-window cases passed the unchanged online
payload/WQE, compute/readiness, CBFC, queue/capacity, association, and drain checks.
All observer terminal and RTT-coverage invariants passed. All six combine hashes
are equal. Detailed timing/causal interpretation belongs in the analysis report.

## Build and regression gates

- Native configure/build: PASS under retained guards.
- Initial application attempt: all four guarded compiles passed, but its final
  source-identity check rejected an analysis-only label change during compilation.
  That attempt was preserved and never used for simulations.
- Fresh build-r2: PASS with consistent source/binary/native identities; its native
  delta is exactly three passive-observation paths and the allocator is unchanged.
- Complete small gate: 428 simulator invocations PASS: 224 fixture runs, 42 faults,
  28 negative payload/completion cases, 21 rate-bound cases, 30 window-bound cases,
  12 capacity-rejection cases, 7 maximum-capacity cases, 64 legacy cases.
- Native window boundary, FIFO observer, Jetty measurement, and compute-model
  regression units: PASS.
- Exact 512 accepted/OFF/ON and separate 1024/2048 OFF/ON event order, full summary,
  and per-expert output parity: PASS.
- Pre/post frozen identity scope: 10,349 source/control files, 42 binary/library
  files, 352 accepted small-fixture/evidence files. Full postflight passed.

## Formal execution and infrastructure interruption

The original single coordinator admitted cases sequentially, in the declared
order: 512 Chunk, 512 MC, 1024 Chunk, 1024 MC, 2048 Chunk, 2048 MC. The first five
completed PASS. The execution server disappeared during the last attempt; both
coordinator and watcher sessions returned pong_timeout/unknown-session errors.
Its heartbeat and outputs stopped, host memory was released, and no terminal
simulator resource/summary/validation record exists. The exact cause is unknown.
Namespace-local process listings were not presented as host-wide PID proof.

The original private root and its incomplete attempt were retained unchanged.
After five completed results and all frozen identities were revalidated, one
explicitly authorized fresh-directory retry of 2048 MC was admitted at
2026-10-21T07:29:03.259517+00:00 using the unchanged case driver and guard limits.
The retry and the complete resolved six-cell postflight passed at
2026-10-21T07:44:50.120372+00:00. No first-five case was rerun. There are seven
attempts, six successful results, and six unique experimental cells.

The authoritative resolved private ledger is real-3136-recovered/ledger.json;
the original real-3136/ledger.json remains an unmodified interrupted execution
record rather than being rewritten to imply clean completion. Recovery preflight,
per-second liveness, resource, lineage, and final postflight records are retained.
Publication uses only aggregate evidence, never the private directory links.

## Resource and checkpoint outcome

No successful case triggered a guard. Every attempt retained 6 GiB process-tree RSS,
7 GiB address space, 1 GiB host memory, 8 GiB output-disk, 2 GiB temporary-disk reserves,
and 4800 s whole-case wall. Actual successful peak RSS was3.596–3.757 GiB; a6GiB
unknown-treatment admission forecast is not an observed footprint.

All six results, frozen identities, the original interrupted state, and the five
reused successful output sets passed the final recovery postflight. Numerical
resource evidence and sanitized manifest digests are in
validation-resource-summary.csv and validation-resource-summary.json. These include
recorded simulator user/system CPU seconds. Kernel peak RSS comes from
wait4(simulator_pid).ru_maxrss, not a simultaneous process-tree sum. The separate
process-tree RSS maximum is sampled every 0.25 seconds and can miss transients.
CPU accounting excludes the Python coordinator and separate validation stages;
all successful simulators had one observed thread per process.

The requested matrix is complete. Stop and await acceptance; no automatic rerun,
additional combination, optimization deployment, or default-window change follows.
