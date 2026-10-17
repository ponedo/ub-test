# Relay index diagnostic instrumentation

The generator is adapted from the immutable Qwen CPU profiling experiment. Only
new files here are written. It pins the new production application and online
audit SHA-256 hashes and generates a separate diagnostic application copy:

```sh
python3 experiments/relay-dependency-index/generate-instrumented.py --out /absolute/generated
```

Compile the generated pair-layer.cc using the experiment build coordinator's
serial resource slot, accepted native libraries and `-std=c++20 -O3 -g`. Generation
is not a native build or runtime validation. Run with the existing profile contract:

```sh
QWEN_CPU_PROFILE=1 QWEN_CPU_PROFILE_OUT=/absolute/timing.json \
  /absolute/generated/pair-layer --dependencyMode=scan --onlineMembershipMode=index ...
```

All four scan/scan, index/scan, scan/index and index/index combinations use the
same generated executable. Snapshots include `dependency_mode` and
`online_membership_mode`; the initial session snapshot precedes argument parsing
and reports `unset`. Modes are recorded before Read begins.

## Cost accounting

- `Read` is the full C++ parser/setup CPU scope. Its nested `Read.dependencies`
  includes dependency-index construction and graph discovery/coverage validation.
  `Read.dependencies.index_build` separately includes map construction and index
  population. Empty-map construction and the mode branch are still timed in scan
  mode. Original local-map lifetimes are preserved: destruction occurs at the end
  of Read and is included in Read self and full Read, not the dependency subphase.
- `InitAudit.online_index_build` is nested in `InitAudit`, includes index population
  and its mode branch, and is zero-work apart from observation/branch cost in scan
  mode. Persistent online indexes are destroyed with Layer; this cost remains in
  `Layer::~Layer` and total program CPU. Index building is production work, never
  subtracted as instrumentation overhead.
- `Audit.group_scan` and `Audit.weight_scan` retain the prior schema names for
  comparison, but time either scan or indexed lookup, candidate visits and original
  validation/aggregation. They include the map lookup cost in indexed mode.
- `read_dependency_candidates`, `audit_group_scan_candidates` and
  `audit_weight_scan_candidates` count actual visited candidates, not an estimated
  full-scan equivalent. Scan counts include rejected candidates. Indexed counts
  include only retrieved vector entries. Match/edge counts count successes in both
  modes. An interrupted snapshot can include one entered but unfinished candidate.
- Additional counters expose dependency/online index-build candidate visits,
  replica/group entries appended, dependency index lookups, and group/weight audit
  index lookups. Failed lookups count as lookups but add no candidate visits.
- CPU timers use process CPU time with nested inclusive/self scopes. Inclusive
  phases overlap and must not be summed. Active scopes contribute elapsed partial
  CPU in snapshots, including in-progress index builds and candidate loops.
  Snapshot serialization/I/O CPU alone is excluded from active scopes and separately
  reported; timer, counter and checkpoint overhead is retained. Uninstrumented
  native/baseline comparisons are required for unbiased speedup claims.
- Periodic and SIGTERM snapshots are cooperative, without simulator events.
  SIGTERM only sets a signal flag; checkpoints serialize and exit. Long operations
  without checkpoints may delay the final snapshot. SIGKILL cannot produce one.
  Latest JSON is atomic; JSONL history defaults to the JSON path plus `.jsonl`.
- Other timers and progress/payload counters preserve the prior profiling runtime's
  semantics. `Simulator::Run` self includes uninstrumented application and native
  work and is not an exclusively native CPU estimate.

These measurements cover C++ Read, InitAudit, online group/weight handling and
remaining C++ phases. Python preparation and Python preflight must be measured
separately. An unfinished fixed-Qwen-256 run supports only partial CPU/counter
statements, not completed-workload speedup.

## Proof and limitations

Generation emits a SHA manifest, exact instrumentation patch, and source proof.
Reversing observer edits must reproduce both pinned source files byte-for-byte.
All Simulator expressions in both application and audit are checked byte-exact in
original order, including complete lambda bodies and arguments; the subset of
control/scheduling calls is separately checked. No schedule, stop or model event
is introduced. Protocol, model, logging and validation are not optimized.

This is a static transformation proof, not runtime semantic equivalence. Compile,
all-mode small regression parity, exact dependency graphs, validation outcomes,
and any bounded Qwen timing runs remain separate gates. The proof permits observer
statements and scopes and does not establish zero measurement perturbation.

## Completed validation in this working tree

- `test-instrumentation.py`: 3 static generator/source-pin/parser tests PASS.
- Guarded diagnostic build: PASS, 17.31 s wall, 987,252 KiB peak RSS.
- `check-parity.py --name parity-instrumented --timed --binary ...`: 20 full
  Debug comparisons PASS (five fixtures × four modes), with timing enabled.
  Event/admission files, payloads and ordered graphs are byte-exact to fresh
  baseline; summaries match after excluding only verification wall time.
- `check-instrumented-counters.py`: all 20 mode/candidate/build-cost checks PASS.
  Actual candidate counts match exact CSV edges or scan cardinalities; nested
  index-build CPU is included in parent phases.
- `check-full-cpp-graph.py`: indexed production C++ Read exports all 66,328 fixed
  Qwen256 transfer rows and ordered dependency lists byte-identically to the
  accepted graph. The driver does no topology or simulator execution. Its 0.754 s
  wall / 0.624 s CPU includes Read, CSV export and destruction; it is not a pure
  Read phase or completed simulator runtime. Peak RSS was 1,001,316 KiB.

Compact evidence: `instrumentation-source-proof.json`, `parity-instrumented.json`,
`instrumented-counter-checks.json`, and `cpp-full-graph-equality.json`. Raw generated
sources, build manifest, binary, timing snapshots and resource observations remain
in the sibling raw experiment directory. Actual Qwen simulation timing is owned by
the runtime coordinator and must be reported separately.

## Complete standalone Read attribution

`profile-cpp-read.py` builds `read-graph-timed.cc` against the generated diagnostic
source and runs fresh scan/index Read scopes on the exact accepted Qwen256 input,
with the original 300 s / 6 GiB tree RSS / 8 GiB free-disk guards. Graph export is
outside the Read scope. Both exports match the accepted 66,328-row CSV exactly.

- Full Read CPU: scan 89.551843 s; index 0.307382 s.
- Nested dependency construction CPU: 89.256855 s; 0.021725 s.
- Indexed construction includes 0.004535 s index building; 62,232 build candidates.
- Actual dependency candidates: 2,437,502,976 versus 78,336; both retain 78,336 edges.
- CPU observations include observer overhead; these are single observations.
  Full Read includes local index destruction. Program self includes graph export
  and other uninstrumented driver work; it is not an isolated export timer.

`cpp-read-profile.json` records completed scope snapshots, source/binary hashes,
compile command and guarded resources. `cpp-read-timings.csv` is the compact table.
`analyze-contributions.py` combines these completed Read measurements with separate
Python spans and, when available, matching completed timed online runs. It permits a ratio from an incomplete simulator observation only for verified
completed target scopes: Simulator::Run and all target calls must be completed,
with identical full event/time/progress counters and target matches. The online
scan process stopped during FinalAudit and remains incomplete; no full-process
ratio or scan latency is claimed. `runtime-self-cpu.csv` and its SVG
partition observed complete/partial program CPU using self times; nested inclusive index build
costs are shown as callouts rather than added twice.
