# Lightweight UB multicast adapter

See [REPORT.md](REPORT.md) for the measured scope, byte model and limitations.

This prototype reuses native per-target WRITE/TA/TP state and native ACK/transaction Response processing. A shared source queue emits one paid envelope containing one Payload plus each target's native header/correlation records. The switch uses its parent/branch replication path. This is an experimental protocol adapter, not a UB-standard group WQE.

## Build and reproduce

Use a disposable native checkout reconstructed from the previous network PoC delivery (native baseline `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`, then its accepted-unicast and network-replication patches). Apply this directory's incremental patch:

```sh
git -C "$NATIVE" apply --check "$PROJECT/experiments/ub-lightweight-multicast-adapter/patches/lightweight-adapter.patch"
git -C "$NATIVE" apply "$PROJECT/experiments/ub-lightweight-multicast-adapter/patches/lightweight-adapter.patch"
bash "$PROJECT/experiments/ub-lightweight-multicast-adapter/reproduce.sh" "$NATIVE" "$PRIVATE/new-adapter-run"
```

The native tree must already be configured using the previous release build settings. Required tools: C++20, CMake/Ninja, Python 3 and psutil. The script builds serially, runs the seven **shared-wrapper** singleton equivalence gates, then five multi-target cases and three expected feedback rejections. It also runs five independent-verifier mutation tests. No GPU, model weights or private Qwen Routing data is used.

Resource guards are the existing project guard: 3600 seconds per stage, 6 GiB process-tree RSS, 7 GiB address space, 8 GiB free working disk, 2 GiB free /tmp, 1.5 GiB available host memory. No limits are relaxed.

For already-built binaries:

```sh
python3 experiments/ub-lightweight-multicast-adapter/run-singleton.py --shared --binary "$BIN/singleton" --private "$PRIVATE/singleton"
python3 experiments/ub-lightweight-multicast-adapter/run-multi.py --binary "$BIN/multitarget" --private "$PRIVATE/multi" --singleton-gate "$PRIVATE/singleton/results.json"
python3 experiments/ub-lightweight-multicast-adapter/collect.py --single "$PRIVATE/singleton" --multi "$PRIVATE/multi" --out "$PUBLIC/compact-evidence"
```

The multi-target runner rejects gates that were run without the shared wrapper or whose adapter/harness source fingerprints differ. Binary hashes remain in the gate evidence. Do not reuse a prior result after changing source or native libraries; rebuild and rerun.

## Regression commands

Build old network PoC and the native test runner with the same native tree/settings, then run sequentially:

```sh
CLICOLOR=0 cmake --build "$NATIVE/cmake-cache" --target scratch_network-poc scratch_ub-quick-example test-runner -j2
python3 experiments/ub-network-multicast-poc/run.py --binary "$NATIVE/build/scratch/ns3.44-network-poc" --private "$PRIVATE/network-regression" --public "$PRIVATE/network-collected"
python3 experiments/ub-network-multicast-poc/run-native-tests.py --native "$NATIVE" --out "$PRIVATE/native-regression"
python3 experiments/ub-network-multicast-poc/regress-unicast.py --baseline "$ACCEPTED_UNICAST_NATIVE" --native "$NATIVE" --private "$PRIVATE/application-regression"
```

The native examples suite requires the original pinned tools submodule, including `scratch/ns-3-ub-tools/trace_analysis/parse_trace.py`. A missing helper is an explicit failed/unavailable suite, never an automatic PASS. See the actual regression result in the report.

## Evidence policy

Default native tracing is disabled. These small protocol-validation fixtures intentionally record the requested packet/event/window evidence privately; they are not performance sweeps. Public evidence is summary JSON/CSV, one small full-byte singleton A/B, one multi-target packet/application timeline and one bounded window trace. Payload binaries and full build/resource logs remain private; hashes and reproducible deterministic Payload generation are provided.

`verify-multi.py` independently checks actual received bytes, TA/chunk coverage, native feedback counts, target/group completion order, one source Payload, wire metadata size, each physical hop's serialization/propagation, credit conservation and window bounds. `test-verifier.py` must reject mutated evidence.
