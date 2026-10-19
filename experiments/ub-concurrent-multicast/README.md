# Concurrent UB multicast and UltraEP integration

See [REPORT.md](REPORT.md) for measured results and limits. The new application strategy is `multicast` (execution strategy ID 3). Existing `direct`, `two-stage` and `chunk-streaming` remain available.

## Native prerequisite

Use the accepted lightweight-adapter native checkout, recorded as `b8375b51a094d3b1217b697989e1ab979f609e64` (tree `6e404be184201380cfe61859eca5971d1b1f3eb9`). This milestone does **not** modify any native protocol source. Its UB source hashes are in `native-source-sha256.json` and are verified before reproduction; a reconstructed checkout may have different commit metadata but must have identical source.

To reconstruct that native source, start from the original native baseline `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`, apply the accepted unicast and network-replication patches in the previous network-PoC delivery, then the lightweight adapter patch from public commit `c28c18c7f000de7468aecae7e89326f1509abf32`. Follow those milestones' release build configuration. Keep CMake/Ninja/Python 3/psutil/C++20 available. Do not use the historical `pair-jetty/build.sh` as this feature's entry point: it pins the older pre-multicast native tree.

If using this project's existing isolated build tools, restore their process environment (no installation or system change):

```sh
export PATH="$BUILD_TOOLS/bin:$PATH"
export PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
cmake --version
ninja --version
```

## One-command primary reproduction

```sh
bash "$PROJECT/experiments/ub-concurrent-multicast/reproduce.sh" "$NATIVE" "$PRIVATE/concurrent-multicast-run"
```

Choose a fresh private output directory. Builds/tests run sequentially under existing 3600s-per-stage, 6GiB RSS, 7GiB address-space, 8GiB free disk, 2GiB `/tmp` and 1.5GiB available-memory guards. Summary is the application default. One small Debug case retains full evidence privately for strict validation.

The fixed primary matrix is seven small synthetic cases × Direct/Chunk/Multicast. No Qwen data, model weights, GPU, large Token Scaling or Planner changes are needed. `run-layer.py` generates the accepted base plan once/case and copies exactly that plan and assignment list across all strategies. `preflight.py` independently reconstructs each graph and multicast membership.

For existing executables:

```sh
python3 experiments/ub-concurrent-multicast/run-concurrent.py --binary "$BIN/concurrent" --out "$PRIVATE/concurrent"
python3 experiments/ub-concurrent-multicast/run-layer.py --binary "$BIN/pair-layer" --graph-tool "$BIN/graph-tool" --out "$PRIVATE/layer" --case all
```

## Original regressions

`run-regressions.py` builds the singleton/concurrent/old-multitarget fixtures, runs old exact singleton equivalence, old multicast, independent mutations, accepted application scenarios, network PoC and native suites. Supply an accepted baseline `pair-layer` executable built from c28c18c7 source and matching native libraries:

```sh
python3 experiments/ub-concurrent-multicast/run-regressions.py \
  --native "$NATIVE" --out "$PRIVATE/regressions" \
  --layer "$BIN/pair-layer" --graph-tool "$BIN/graph-tool" \
  --baseline-layer "$ACCEPTED_BASELINE_LAYER"
```

The historical `unified-bus-examples` missing trace-parser failure is explicitly recorded; it is not relabeled PASS. Other unexpected failures stop the runner. See the report for the initial PATH-related failure and its focused rerun evidence.

## API and bounds

`GroupManager::Add` registers a distinct expert operation with native child TP/Jetty resources. `Start` marks submission; `Completed` consumes each child native success; `Receive` reconstructs target packets; `ReceiveNative` validates native feedback identity and invokes the original receive path. Existing native allocator queues perform arbitration.

The registry supports at most 128 **lifetime operations per layer**, not a recyclable 128-slot service. Members are immutable within an operation; a subsequent operation can have a different member set while others remain active. Each group uses dedicated child endpoints. Dispatch/Combine still use Pair Jetty. The one-layer executor disposes resources at simulation teardown after verifying all data, queues and protocol outstanding state are drained.

This is an experimental protocol adapter, not standardized UB multicast. Limits: one switch, ranks 0–63, WRITE, segment ≤4096B, fixed 160B CBFC cell geometry, no loss recovery, retransmission or CC. Control feedback uses real native network paths. All extra envelope bytes are charged; singleton follows the native packet path.
