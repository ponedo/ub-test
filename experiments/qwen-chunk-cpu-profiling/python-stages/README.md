# Python preparation and independent-preflight diagnostics

This directory contains diagnostic additions only. Original planner, adapters,
graph tool, independent checks and simulator validation are not modified.

## Reproduce

Run `run_profiles.py --raw <new-directory> --input <existing-chunk-input-directory>
--graph-tool <accepted-graph-tool>` from this repository. It invokes the existing
`wqe-completion-fix/guard.py` with the original 300 s stage wall bound, 6 GiB
process-tree RSS bound, 7 GiB address-space bound, 8 GiB free-disk minimum,
2 GiB free-/tmp minimum and 1.5 GiB available-memory minimum. It never weakens
payload, assignment, WQE/task, integer-range or validation checks.

`profile_stage.py` runs cProfile and adds low-frequency per-statement timing
contexts to preparation, direct adapter emission, relay adapter emission and the
independent checker. AST wrapping leaves all original expressions, conditions,
loop bodies and assertions in place. Instrumentation is compiled in memory;
source files stay unchanged. Preparation generation subprocess and native graph
tool internals are outside cProfile, while their parent waits remain visible.
SIGTERM/SIGINT raise SystemExit, unwind timing contexts and dump partial pstats,
coverage and interruption location before the existing guard's 2 s kill grace.
A signal smoke test verifies this path. A no-balancing check smoke test returns
PASS and identical historical input/graph fingerprints.

`analyze_profiles.py --raw <raw> --out <this-directory>` exports all functions,
Top20 by self time, cumulative time and call count, call edges and SVG callpaths.
Cumulative call times and nested statement stages overlap. Do not add ancestors
to descendants. Stage peak RSS is process high-water RSS, not stage allocation.

## Known baseline and structural evidence

Historical (not freshly paired) unprofiled controls: preparation 202.066 s wall,
201.686 s user CPU, 0.553 s system CPU, 196,748 KiB RSS; independent preflight
214.112 s wall, 213.852 s user CPU, 0.079 s system CPU, 105,600 KiB RSS.
These prior controls used the accepted same source tree and scenario, but are
not sufficient to isolate profiling overhead from host/run variation.

The exact accepted large Chunk input contains 62,232 weight tasks, of which
39,168 have a replica source and need relay dependencies. Both
`multi-npu-relay/adapter.py:39-46` and `tiered-logging/preflight.py:112-118`
scan `transfers[start:]` for each such task: 2,437,502,976 candidate visits per
pass, plus copying a 62,232-reference slice 39,168 times. Only 78,336 dependency
links result. Counts are derived directly from original config/plan/edges,
not extrapolated from a smaller substitute. This is O(RW) time, up to O(W²)
when relay-dependent tasks R scale with weight tasks W. Temporary slices are
O(W) live references; final dependencies occupy O(D). This is diagnosis,
not a proposed or applied algorithm change.

Independent preflight is a separate Python rebuild/check before simulation.
Postflight repeats that independent check with an executed-summary fingerprint.
Neither is simulator online validation. This profiler does not count either as
simulator time or remove any of their checks.

## Fresh measured results

Both full-size profiles completed under all original guards. Preparation:
203.594 s wall, 202.781 s user CPU, 0.838 s system CPU, 196,644 KiB max RSS.
Independent preflight: see `stage-resources.csv` for exact fresh CPU/RSS values;
196.79 s wall. Both profiles cover the complete stage, not timeout fragments.

Preparation's Chunk dependency loop took 196.070 s wall / 196.030 s process CPU
(96.3% of total guarded wall). Relay `emit` accumulated 200.207 s inclusive
across its three calls, with 196.276 s self time (96.51% cProfile self-time total).
The Chunk JSON serialization/write took 2.883 s, parsing graph-tool CSV 0.191 s,
and constructing weight transfer records 0.087 s. Assignment mapping,
validation, graph-tool process wait and serialization are retained and visible;
none approaches the dependency scan's cost.

Independent preflight's duplicate dependency rebuild took 195.328 s wall /
195.296 s process CPU (99.3% of guarded wall). `check` took 195.530 s self time
(99.415% cProfile self-time total), 196.468 s inclusive. Graph-tool CSV parse was
0.234 s; canonical transfer serialization 0.235 s; final fingerprint return
0.245 s, including FNV1a's 0.243 s; graph-tool wait 0.024 s; independent planner
check 0.090 s. Function self time contains comprehensions under CPython 3.12
inlining, so function-level cProfile alone would hide which loop dominates.
The unchanged-statement spans identify it directly.

Fresh preparation execution/config/routing/transfer bytes match prior accepted
input. Plan semantic content matches exactly; only `cpu_wall_ns` planning
measurement telemetry differs. `preparation-metrics.json` also changes because
it measures the new run. The independent preflight output is exactly equal to
the prior PASS result, including input SHA256 and graph SHA256/FNV1a64.

Profile/control wall ratios are approximately 1.008× preparation and 0.919×
preflight. These are historical comparisons, NOT negative profiler overhead or
a speedup: host variation and cProfile perturbation cannot be isolated without
a fresh paired control. No optimization was performed. Main-process cProfile
is wall-clock based, subprocess internals are excluded, and parent wait time
must not be mistaken for Python compute. Full guard CPU includes child usage.

## Raw evidence location

Binary cProfile files remain only in the existing local evidence directory
`/workspace/scratch/c6ba02920254/qwen-chunk-profile-raw/python/` as
`preparation/profile.pstats` and `preflight/profile.pstats`.
`raw-profile-manifest.json` records that root, relative paths, sizes and SHA256
hashes. Repository publication contains text/CSV/SVG exports and manifests,
not duplicate binary profile files. Original raw evidence is unchanged.
