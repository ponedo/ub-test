# Reproduce the same-input logging experiment

These commands are sequential. Do not run them concurrently with another guarded simulator experiment. The existing 300 s wall, 6 GiB process-tree RSS, 7 GiB address-space, 1.5 GiB host-available-memory, 8 GiB free-disk, and 2 GiB `/tmp` guards remain unchanged.

## Final representative matrix

From the repository root, with these local accepted inputs available:

```sh
python3 experiments/tiered-logging/run.py \
  --binary /workspace/scratch/c6ba02920254/tiered-logging-raw/build-final/pair-layer \
  --old-binary /workspace/scratch/c6ba02920254/ep64-scaling-raw/build/pair-layer \
  --lib /workspace/scratch/c6ba02920254/wqe-completion-native/build/lib \
  --graph-tool /workspace/scratch/c6ba02920254/ep64-scaling-raw/build/graph-tool \
  --fixtures-root /workspace/scratch/c6ba02920254/prefill-cpu-profiling-dot/experiments/multi-npu-relay/evidence \
  --ep64-package /workspace/scratch/c6ba02920254/ep64-scaling-raw/tokens-256/prepared-evidence \
  --out /workspace/scratch/c6ba02920254/tiered-logging-raw/validation-reproduction

python3 experiments/tiered-logging/collect.py \
  --raw /workspace/scratch/c6ba02920254/tiered-logging-raw/validation-reproduction \
  --out /workspace/scratch/c6ba02920254/tiered-logging-raw/analysis-reproduction
```

Choose a fresh output path. Source fixture data are not changed. Only the small prepared-input archive is restored; full historical simulator trace archives are not unpacked. Use `--cases nb-small multichunk-multita --skip-faults` only for a development smoke test, not the acceptance matrix.

The five cases cover NB, direct, chunk-streaming, forced multi-chunk/multi-TA relay, and EP64 N256. Every input byte is identical across summary, events, debug and the old debug executable. Summary deliberately omits `--logLevel` to test the public default. The multichunk case must actually have multiple chunks, a multi-TA WQE, and both application and native pipeline overlap.

The acceptance matrix runs 13 faults in all three modes (39 expected failures): payload-byte, duplicate-completion, early-wqe, missing-wqe, weight-byte, premature-ready, duplicate-weight, early-compute, early-group, relay-byte, relay-buffer-byte, early-relay and early-final-ready. A positive nonzero application exit, expected diagnostic, no resource-guard kill, and FAIL validation are required; a random crash or timeout does not pass.

## Normal EP64 scan, summary default

```sh
python3 experiments/ep64-token-scaling/run.py \
  --raw /workspace/scratch/c6ba02920254/tiered-logging-raw/ep64-summary-reproduction \
  --binary /workspace/scratch/c6ba02920254/tiered-logging-raw/build-final/pair-layer \
  --lib /workspace/scratch/c6ba02920254/wqe-completion-native/build/lib \
  --graph-tool /workspace/scratch/c6ba02920254/ep64-scaling-raw/build/graph-tool \
  --reference-raw /workspace/scratch/c6ba02920254/ep64-scaling-raw \
  --reuse-prepared --tokens 256
```

This is the tested representative replay, not a full token-scale rerun. `--reuse-prepared` restores the exact accepted prepared inputs, including historical planner timing metadata. Its result records explicitly mark that planner measurement as historical, not a new planner benchmark. Without `--reuse-prepared`, the normal runner regenerates routing and plans. Comparing byte hashes against a prior prepared plan then intentionally detects any changed bytes, including the plan's `cpu_wall_ns` measurement; this is not treated as a model divergence.

Use `--log-level events` for the key event stream or `--log-level debug` for raw native/application/payload evidence plus the original strict verifier. Normal summary/events runs retain readable aggregate JSON and separately hash-verified archives of their newly materialized input copies. Debug retains the original full-evidence compaction behavior.

The projected `summary.json` uses runtime-measured times, byte/completion/packet counters and input-validated static dimensions. `weight_WQEs` and `weight_TAs` are derived from the independently validated task graph and segment size; they are not falsely labeled as per-stage runtime event counters. The total `TA_count` remains a runtime count. Finer raw-event overlap lists remain debug evidence.

## Output and measurement accounting

- Simulator-generated output: online-summary, validation, simulator-metrics, plus mode-specific events/native traces/raw payloads.
- Input copies: input/config/plan/assignments/transfers/weight graph files; separate, never counted as logs.
- Input metadata: input-summary emitted by preflight; separate from simulator-generated output.
- Strict verifier output: excluded from the measured simulator output snapshot.
- Host time/RSS: measured by the unchanged guard. Wall time has 250 ms polling granularity; tiny-run timing and inherited-process RSS floors are not reliable speedup benchmarks. Use the EP64 CPU measurements and exact byte counts for representative comparisons.

The suite requires stable online-summary/validation/counter equality across modes, exact debug comparison to the original strict verifier and old executable, and an independently reconstructed key-event stream including documented aliases. Only `log_level` and `verification_wall_ns` are excluded from cross-mode stable JSON equality.

## Lightweight tests and retained-evidence audit

```sh
python3 experiments/tiered-logging/test-harness.py
python3 experiments/tiered-logging/test-preflight.py --case /path/to/accepted/chunk-streaming --graph-tool /path/to/graph-tool --out /path/to/fresh/preflight-tests.json
python3 experiments/tiered-logging/audit-existing.py \
  --results /workspace/scratch/c6ba02920254/tiered-logging-raw/validation-final/results.json \
  --out /workspace/scratch/c6ba02920254/tiered-logging-raw/validation-final/rechecked.json
```

The retained-evidence audit does not rerun simulations or modify measured files. It verifies retained sizes, binary identity, stable modes, key events, fault coverage, and real multi-chunk/multi-TA pipeline coverage, while separating input metadata from simulator-output accounting.

## Build and retained regressions

Use the accepted native checkout with its existing optimized libraries. The following wrapper does not change native sources:

```sh
NS3_ROOT=/path/to/accepted/ns-3-ub OUT=/path/to/new/build bash experiments/pair-jetty/build.sh
python3 experiments/ep64-token-scaling/regressions.py \
  --raw /path/to/new/regressions --native /path/to/accepted/ns-3-ub \
  --build /path/to/new/build --fixtures /path/to/accepted/multi-npu-relay/evidence \
  --tools /path/to/accepted/build-tools
```

The paths in the measured commands above identify the actual execution environment. On another host substitute equivalent native libraries, accepted prepared inputs and build-tools. Existing repository build/bootstrap instructions apply; this change does not require a new ns-3-ub patch. The accepted old executable can be rebuilt from the baseline project worktree using its `experiments/pair-jetty/build.sh` and the same native libraries. The historical fixture and prepared-input manifests in the accepted project identify their contents; the matrix verifies every restored input hash. Keep a separate fresh output path for each reproduction.
