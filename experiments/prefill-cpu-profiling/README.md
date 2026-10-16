# NB prefill CPU profiling on the dot host

This is a **new-host, diagnosis-only** replication, separate from the saved-environment run. It preserves EP64/E128/k8, H64/I128/bf16/SwiGLU, single-switch topology and the accepted prefill-capacity inputs. No Jetty reuse, packing, protocol, WQE, TA, relay, network, compute, planner, cap, log or verifier optimization is implemented.

- [Report](REPORT.md)
- [Declared plan and protection](experiment-plan.md)
- [Machine-readable run ledger](evidence/run-ledger.json)
- [Exact small-case parity](evidence/small-parity.json)
- [Compiler, flags and ELF evidence](evidence/build-audit.json)
- [Sampling calibration and limitations](evidence/calibration2-notes.md)
- [Read-only analysis outputs](evidence/analysis/summary.json)

## Reproduction

Use a fresh workspace containing this ub-test checkout and a dedicated `prefill-cpu-native` checkout pinned to d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b. Initialize its ns-3-ub-tools submodule at 29009175f1778f76a22d929063c3a0821cb91e56. Install `cmake`, `ninja`, and `psutil` from PyPI into a separate `prefill-cpu-tools` directory if needed. Python 3.12 and GCC 14.2 were used here.

For the complete ordered workflow, run `bash experiments/prefill-cpu-profiling/run.sh`. It refuses existing raw output and archives any checked-in evidence separately before initializing a new ledger. The individual steps are:

1. Run `bash experiments/prefill-cpu-profiling/build.sh` on the fresh clone. It preserves uninstrumented executable and **all** native DSOs before building the separately instrumented version. It refuses an existing baseline archive. Do not invoke this against an already-instrumented clone.
2. Set up the official Debian perf decoder with `setup_perf.sh /path/to/perf-tools`. This does not change system packages or security settings.
3. Calibrate `record` on `calibration-hotloop.c` using a minimal whitelist environment. Review sample count, CPU time, period sum, unknown symbols and record loss/throttle metadata before trusting it.
4. Run `execute.py --assignments A --variant VARIANT` for A=5000,10000,20000,50000 and VARIANT=baseline,sampled,timed, sequentially. Stop larger scales on any guard or verification failure. Never run builds/other experiments concurrently. Existing case directories are refused. `parity.py` covers small NB and relay with instrumentation enabled and disabled.
5. Run `analyze.py --perf /path/to/perf-tools/perf` only after the measurements finish. It counts each sample once, preserves unknown frames and checks decoded counts against raw records and the collector. SVG Top20 charts are equivalent hotspot views; inclusive bars overlap and must not be summed.

The scripts derive workspace paths from their location except analyzer defaults, which accept `--raw`, `--out`, and `--perf`. Raw outputs stay outside the git checkout. All subprocesses in the formal matrix receive an explicit minimal environment; stack captures never inherit ambient authentication variables.

## Method boundaries

Official `perf record` could not discover a CPU-clock event in this container's missing sysfs CPU/PMU metadata, and silently wrote zero samples. The retained verbose probe documents that failure. A small audited C collector therefore requests the same Linux `perf_event_open` user CPU-clock event directly and writes standard `perf.data`; the **official perf decoder** supplies DWARF symbolization. It does not invent samples or use gprof.

The collector covers the main thread, with inheritance disabled, at 99Hz and 8KiB user-stack snapshots. Main-thread scope is corroborated by observed process thread counts and disabled MPI/MTP, not generalized to arbitrary multithreaded applications. Unknown/unwound frames are retained. “No LOST records” is not a guarantee of complete sampling. Exact executable/DSO hashes and before/after checks accompany the profiles; retain matching ELF files when re-decoding.

Timers/counters are opt-in through `NATIVE_CPU_PROFILE=1`. `NATIVE_CPU_PROFILE_DETAIL=1` additionally enables finer trace/packet scopes and is exercised in small parity runs. Timer nanoseconds (thread user+system CPU) are **not user-CPU sample percentages**. Inclusive scopes nest; exclusive time subtracts only instrumented children. Generic ACK-slot counters include every instrumented window user, not only Jetty windows. Capacity-growth requests are not malloc byte counts.

Resource CPU totals come from `wait4`; guarded wall measurements have a 250ms completion-poll granularity. One trial per size/variant characterizes observed perturbation, not a statistical speedup claim. Host clock timestamps are retained as captured; elapsed timings use a monotonic clock.

## Raw evidence delivery

Full raw profiles, input/output files, complete logs, regression artifacts and exact ELF symbols are delivered as separate Library attachments named `dot-prefill-*-raw.tar.gz`, `dot-prefill-validation.tar.gz`, and `dot-prefill-symbols.tar.gz`. The repository intentionally does not duplicate hundreds of MB of those files. `evidence/archives.json` records each attachment's exact name, size and SHA256; corresponding `*.manifest.json` files inventory every archived file. Attachment delivery is required in addition to this repository link.

Each per-scale archive contains all three variants. Identical files are stored using standard tar hard links, so extracting the archive reconstructs every original file byte-for-byte without three compressed copies. Do not treat a tar link as missing data. Extract the symbols archive to obtain `symfs/`, then pass `--symfs /path/to/symfs` to analyzer/perf when original absolute ELF paths are unavailable. Raw stack bytes are provided only after the minimal-environment capture and publication scan described in the evidence.

After analysis, `freeze_symbols.py` must precede `regressions.py`. The latter reverses only the exact diagnostic native patch to satisfy the older PoC clean-tree preflight. Those restored-source regressions are distinct from the instrumented matrix and small parity. Failed attempts remain archived. `finish_artifacts.py` relocates bulky decoded stacks into raw/analysis-raw; `check.py` reads either location. `calibration_check.py` similarly accepts raw/calibration. Fresh analysis can regenerate decoded stacks from the raw profiles and matching symfs.
