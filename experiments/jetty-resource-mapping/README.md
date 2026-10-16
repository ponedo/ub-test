# Jetty resource mapping A/B/C harness

The native index and A/B experiment harness are implemented and tested. Read REPORT.md for actual results and the shared-Jetty capability blocker. The matrix declares candidate cases; only completed evidence represents measurements. C is not implemented and 100K was not run.

Example fresh A5K timing (replace paths explicitly):

```
python3 harness.py --execute --arm A --assignments 5000 --phase timing \
  --attempt 5000-A-timing --raw /workspace/scratch/c6ba02920254/jetty-mapping-raw \
  --inputs-raw /workspace/scratch/c6ba02920254/prefill-cpu-raw \
  --binary /workspace/scratch/c6ba02920254/prefill-cpu-raw/baseline-binaries/ns3.44-multi-npu-relay \
  --lib /workspace/scratch/c6ba02920254/prefill-cpu-raw/baseline-binaries/lib \
  --tools /workspace/scratch/c6ba02920254/prefill-cpu-tools \
  --graph-tool /workspace/scratch/c6ba02920254/prefill-cpu-raw/aux/graph-tool
```

B uses the indexed-native application binary and build/lib, with --reference pointing to the matching fresh A timing attempt. C is BLOCKED_NOT_IMPLEMENTED: no pair-mapping binary or execution is part of this round. Same-arm 50K sampling uses --phase sampled --collector /workspace/shared/cpu_sampler/record and --reference to that arm's timing attempt. Do not run a build or another simulator concurrently.

```
python3 compare.py --raw RAW --a RAW/5000-A-timing --b RAW/5000-B-timing --mode bytewise
python3 decode.py --attempt RAW/50000-B-sampled --perf /workspace/shared/cpu_sampler/perf --out RAW/analysis-50000-B
```

The comparator only reads and prints JSON. Decoder writes only its new --out directory. It uses the prior official-perf parser and counts samples, never sampling periods, with unknown stacks retained. Freeze binaries before any rebuild; the runner does this automatically for native application/library files. Decoder copies system mapped ELFs afterward and reports missing paths.

100K was not run and no further capacity run is scheduled in this delivery. The original optional 100K manifest is historical interface documentation only. All measured 5K–50K controls use the exact seven original common/run files supplied in evidence/archives/fixed-inputs.tar.gz.

No scripts modify stage.py, model/planner code, existing verifier, original raw inputs, or original baseline binaries. No commits were made by harness preparation. Timing labels refer to host resource measurements; they do not silently enable fine-scope instrumentation.

## Optional instrumented evidence

`--phase instrumented` uses a separately supplied instrumented binary/library tree, frozen independently under ARM-instrumented. It requires a successful same-arm uninstrumented timing reference and exact all-398-file parity. Only this phase adds NATIVE_CPU_PROFILE=1 and NATIVE_CPU_PROFILE_OUT=attempt/timing.tsv to the minimal environment. A uses the existing instrumentation; B additionally uses the declared index instrumentation. No C instrumented run exists; the earlier proposed library-sharing rule is historical only. These runs provide exact counters and scoped CPU timers, not sampling percentages or unbiased speedup controls. Reuse analyze.py analyze_timing for timing.tsv; do not overwrite the uninstrumented frozen ELF. Optional instrumented cases appear explicitly in matrix/manifest and are not automatically launched.

## Lightweight partial measured summary

Run `python3 summarize.py --raw /absolute/raw --out /new/output/directory --sizes 5000 10000 20000` to create CSV resources/counters/parity, an SVG with measured curves, and source-hashed JSON metadata. The output directory must not exist. It reads only saved small attempt summaries and timing tables, never launches a simulator or rehashes bulk event/payload files. Missing, running, and failed cases remain explicit across the full declared matrix; curves use only completed selected sizes. Instrumented Jetty/query counts are never inferred for missing runs.

## Implemented and blocked scope

The native candidate index is implemented in `tpn-jetty-index.patch`, independently against native baseline `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`; the reviewed local commit is `eda2fd75bfd1a37b28917b3ebbe721bade5f91ae`. No application mapping or native completion algorithm was changed. The original native concurrent multi-segment shared-Jetty test fails in both A and B. Consequently C is **not implemented**, and its original command declarations are marked historical and non-executable. See `REPORT.md` and `shared-jetty-probe.md`.

## Build and regression reproduction

Start from the accepted application baseline `2c13237f7e6178ca3c76992f84a7be18a727a6d1` and this experiment branch. Preserve an independently built A checkout and its libraries; follow the existing `../prefill-cpu-profiling/README.md` baseline build/tool instructions. Use a separate native B checkout/worktree at the pinned native baseline and the pinned native tools submodule `29009175f1778f76a22d929063c3a0821cb91e56`.

```sh
NS3_ROOT=/absolute/native-B BUILD_TOOLS=/absolute/build-tools OUT=/absolute/new-build-evidence bash build-index.sh
python3 run-native-tests.py --native /absolute/native-B --runner /absolute/new-build-evidence/native-test-runner --out /absolute/new-unit-evidence
# Record the exact reviewed native patch in a local commit before running old pin-checked regressions.
git -C /absolute/native-B add src/unified-bus/model/protocol/ub-transaction.cc src/unified-bus/model/protocol/ub-transaction.h src/unified-bus/test/ub-test.cc
git -C /absolute/native-B commit -m 'Index TP reverse Jetty candidates without changing live resolution'
python3 regressions.py --native /absolute/native-B --out /absolute/new-regression-evidence
```

`regressions.py` currently expects the established sibling `prefill-cpu-tools` installation. It uses an isolated clone of the application commit, adapts only revision-pin/worktree preflight checks, and records the exact bootstrap diff. Native tracked sources must be clean. Run application regressions before diagnostic instrumentation, or link explicitly to preserved clean libraries.

The full native unit suite runner must use the native checkout as cwd because one existing suite creates relative `scratch` fixture files. It runs each suite individually and retains every exit/log; an aggregate invocation is not supported by this ns-3 build.

For the shared-Jetty known-failure check, set `A_ROOT`, `B_ROOT`, `FROZEN_A` and `FROZEN_B` (library directories), then run `OUT=/absolute/new-probe-evidence bash run-shared-jetty.sh`. The script compiles separate ABI-matched test binaries and verifies library resolution. Its successful exit means both original failures were reproduced and controls passed. It does not make the native shared-Jetty capability acceptable.

## Evidence reconstruction

`collect-evidence.py --raw RAW --out NEW_DIRECTORY` copies original small run metadata and creates a SHA-256 manifest of full successful-run artifacts. `summarize.py` produces resource/counter/parity tables from actual saved records only. Large duplicate payloads and binary symbol archives remain on the host; the manifest and exact commands allow independent verification. No unpublished C measurements are represented by the reserved matrix entries.

For this stage, GitHub contains the small raw evidence, compressed data where practical, and reproduction manifests; no chat attachment is required. The prior profiling README describes its historical delivery, not this stage’s packaging.
