# Concurrent WQE completion repair

Read REPORT.md for measured results and the separate cancellation/failure notification repair. No Pair Jetty application change is part of this delivery.

Run commands from `experiments/wqe-completion-fix/`.

## Native build and tests

Use independent native A/B/C checkouts. A is `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`; B is accepted index `eda2fd75bfd1a37b28917b3ebbe721bade5f91ae`; C starts at B and applies `combined-native.patch`. The two changes are also supplied independently: `concurrent-wqe-completion.patch` applies to B, then `terminal-wakeup.patch` applies on top. The tools submodule must be at `29009175f1778f76a22d929063c3a0821cb91e56`. The existing profiling/index documentation describes obtaining the authorized native checkout and official CMake/Ninja tools.

```sh
NS3_ROOT=/absolute/native-C BUILD_TOOLS=/absolute/prefill-cpu-tools OUT=/absolute/new-build bash build-fix.sh
python3 ../jetty-resource-mapping/run-native-tests.py --native /absolute/native-C --runner /absolute/new-build/native-test-runner --out /absolute/new-unit-results
# Commit exactly the reviewed native patch before the old regression preflight.
git -C /absolute/native-C add src/unified-bus/model/protocol/ub-function.cc src/unified-bus/model/protocol/ub-function.h src/unified-bus/model/protocol/ub-transaction.cc src/unified-bus/model/ub-datatype.h src/unified-bus/test/ub-target-execution-test.cc
git -C /absolute/native-C commit -m 'Fix completion frontier for concurrent interleaved WQE admissions'
python3 regressions.py --native /absolute/native-C --out /absolute/new-regressions
```

The old regression wrapper expects the established sibling `prefill-cpu-tools` directory. It snapshots application source and changes only native revision/worktree bootstrap checks, retaining the exact bootstrap diff and commands. Do not run builds or simulators concurrently.

## A/B/C causal probes

Point each header checkout and library directory to the matching revision. The probe runner checks dynamic library resolution and refuses existing output directories.

```sh
python3 run-probes.py --a-root /absolute/native-A --b-root /absolute/native-B --c-root /absolute/native-C --a-lib /absolute/native-A/build/lib --b-lib /absolute/native-B/build/lib --c-lib /absolute/native-C/build/lib --out /absolute/new-probes
python3 analyze-probes.py /absolute/new-probes
```

The runner returns success only if A/B reproduce the original failure and C passes the original and expanded correctness probes. Original cancellation logs are a separate characterization: `hole_observed=1 errors=0` confirms the old issue. Final independent cancellation/failure wakeup tests require timely notification and full cleanup; A/B are expected to fail those oracles. All raw exit codes remain in results.json.

## Host overhead and exact regression parity

`run-overhead.sh` alternates index-only and completion-fixed executors, three repeats each at 5K and 10K assignments. It reuses identical accepted seven-file inputs, resource guard, independent payload verifier and all-398-file bytewise comparator. Harness labels A/B in these new records mean native B/C; they do not mean the original no-index version or Pair Jetty. All application source is unchanged and recompiled against matching native headers.

```sh
INDEX_BIN=/absolute/index/ns3.44-multi-npu-relay INDEX_LIB=/absolute/index/lib FIX_BIN=/absolute/native-C/build/scratch/ns3.44-multi-npu-relay FIX_LIB=/absolute/native-C/build/lib INPUTS_RAW=/absolute/prefill-cpu-raw BUILD_TOOLS=/absolute/prefill-cpu-tools GRAPH_TOOL=/absolute/graph-tool OUT=/absolute/new-overhead bash run-overhead.sh
INDEX_ROOT=/absolute/native-B FIX_ROOT=/absolute/native-C OUT=/absolute/new-sizes bash run-size-check.sh
python3 summarize-overhead.py /absolute/new-overhead --out /absolute/new-resource-summary
python3 compare-regressions.py --before /absolute/accepted-index-regressions/accepted --after /absolute/new-regressions/accepted --out /absolute/regression-parity.json
```

Inputs can be reconstructed from the accepted index delivery's fixed-inputs archive; keep each `common-5000/run` and `common-10000/run` unchanged. These are host execution overhead checks, not MoE speedup experiments. The local `guard.py` differs from the accepted observer only by catching a child-exit race while reading thread count; run-harness.py loads it without changing the accepted workload, verifier, resource limits or comparison logic.
