# Native Jetty resource-mapping controlled experiment

## Final disposition

C status: BLOCKED_NOT_IMPLEMENTED. The original native completion bug was reproduced; pair mapping was not implemented or run and is excluded from this round. No C execution is scheduled or promised. A/B completed measurements and the MRE are in REPORT.md. The original planning material below is retained solely as historical experimental intent; its conditional language is not a current work queue.

## Historical declared hypothesis and controls (before execution)

- Block AB: replacing native per-WQE scan lookup with the reverse index reduces host simulator CPU/wall growth, without any output change. A is the preserved original native per-WQE binary; B changes only native reverse-index lookup.
- Block BC: adding app-level pairJetty reuse on the same indexed native library reduces resource creation/count growth and host CPU/RSS. This is a separate resource-mapping intervention; simulated latency and native Jetty identifiers/SSNs may change.
- A source: `prefill-cpu-raw/baseline-binaries`. B/C indexed native build: `jetty-index-native/build`. All are external workspace paths, supplied explicitly; never use old A measurements as fresh controls.
- Fixed controls: exact EP64/E128/top-k8 accepted assignments at A=5K/10K/20K/50K; original no-balancing synthetic prefill inputs, seed, graph, routing, single-switch topology, WQE/TA meaning, explicit payloads, network/compute/logging/verification settings. No packing or planner changes.
- Fresh A timing is required at every evaluated size. Prior profiling results are historical references only.
- Prediction: B CPU/wall is lower than A at larger scales and scan hotspots decrease; C further lowers creation cost and Jetty resource count where capability permits. No numerical speedup is pre-promised.
- Falsification: mismatched A/B bytes, C WQE/TA/payload or causality violation, guard failure, changed inputs/libraries, or unchanged/worse cost invalidates or weakens the corresponding claim. One trial is descriptive, not statistically established.

## Gate and checkpoint policy

`checkpoint_policy: pause_for_user` on invalidated assumptions, correctness failure, guard stop, or needed matrix revision. The lead owns sequencing; this package performs no build and launches no work by mere import or preparation.

1. Native regressions and multi-segment concurrent pairJetty capability gate must pass before any C run. A/B can proceed independently when approved by lead.
2. Run one process at a time, with no concurrent build/test/profile. A raw-root lock prevents duplicate harness execution; cross-workspace exclusivity is the lead's responsibility.
3. At each size run fresh A then B, verify all 398 files bytewise, then C only if capability gate passed. C uses the unchanged strict verifier and task/offset-based logical invariants; native wire headers and timestamps are not parity oracles.
4. Preserve failures. Stop escalation on any error. Record skipped/blocked C explicitly if capability fails; do not characterize an unrun C as accepted.
5. Sample representative 50K A/B/C only after the respective successful timing run, serially, 99Hz using existing custom collector and official perf decoder. Sampled output must match same-arm timing output bytewise.
6. A100K is conditional. Lead must approve after 50K safety/correctness gates. Generate only through existing `prefill-capacity/stage.py` generate/planner/adapter, guarded and recorded. Harness never auto-generates inputs; it requires an explicit prepared common directory and approval flag.

## Evidence and artifact contract

Each attempt retains exact invocation, minimal child environment, source and copied input hashes, frozen executable/all native library hashes, simulator/strict-verifier console and resource samples, wait4 CPU/wall/RSS, 398-file output hashes, task/TA/payload invariant digest, parity report, and every failure. Runs use a new output directory and never overwrite prior evidence. `run-ledger.jsonl` and `run-ledger.md` append lifecycle events, including failed attempts. `attempt.json` is the current per-attempt state.

Native ELF files are copied (not hardlinked) into raw/frozen/ARM before running and hash-checked afterward. Sampling uses those frozen executable/library paths. Decode copies exact absolute MMAP ELF paths into a portable symfs and retains unknown/missing symbols; system ELF copies are post-capture snapshots, not proof of unchanged system files during capture.

Host timings are fresh uninstrumented guarded measurements, not the older opt-in fine-scope timing table. CPU hotspot analysis reuses the established decoder's raw sample counts, loss/throttle, unknown/unwind coverage, Top20 self/inclusive and folded stacks. Inclusive membership overlaps and is not additive.

Guards unchanged: 6GiB process-tree RSS, 7GiB address space, 8GiB free output disk, 2GiB free /tmp, 1.5GiB available host memory, 600s per stage. Guard polling adds approximately 250ms wall granularity. Guard/verifier code is imported or invoked unchanged.

## Script contract

- `harness.py`: explicit inputs/binary/lib/tools/raw/graph-tool paths; creates only declared fresh attempt and frozen ELF directories under the supplied raw root. Requires `--execute`; no builds, implicit downloads, or input generation.
- `compare.py`: reads raw attempts and outputs JSON to stdout; no writes or subprocesses.
- `decode.py`: reads one successful sample and existing official perf; writes a new explicit output directory with symfs and reused decoder deliverables. Never launches simulator/build.
- External writes are confined to the explicit raw root/output arguments. Original `prefill-cpu-raw`, stage/model/planner/verifier sources stay untouched.

## Optional instrumented evidence

`--phase instrumented` uses a separately supplied instrumented binary/library tree, frozen independently under ARM-instrumented. It requires a successful same-arm uninstrumented timing reference and exact all-398-file parity. Only this phase adds NATIVE_CPU_PROFILE=1 and NATIVE_CPU_PROFILE_OUT=attempt/timing.tsv to the minimal environment. A uses the existing instrumentation; B additionally uses the declared index instrumentation. C must share B-instrumented libraries. These runs provide exact counters and scoped CPU timers, not sampling percentages or unbiased speedup controls. Reuse analyze.py analyze_timing for timing.tsv; do not overwrite the uninstrumented frozen ELF. Optional instrumented cases appear explicitly in matrix/manifest and are not automatically launched.
