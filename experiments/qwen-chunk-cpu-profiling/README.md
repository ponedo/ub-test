# Qwen256 Chunk Relay CPU profiling

Diagnosis only. See `REPORT.md` for measured results, limits and optimization candidates; no optimization is implemented. The accepted application/native sources remain unchanged. `experiment-plan.md` freezes the scenario and guards.

## Layout

- `evidence/reused-inputs/`: exact compact prepared simulator inputs for Qwen256 No Balancing, Direct and Chunk; no expensive preparation is needed to start simulation.
- `python-stages/`: separately measured preparation and independent preflight, cProfile Top20, statement wall/CPU and exact-input parity.
- `record.c`: user CPU-clock perf_event_open recorder, DWARF registers/8KiB stacks,19Hz,128MiB profile budget, signal-safe cutoff/finalized perf header.
- `generate-instrumented.py`, `profile-runtime.h`: source-pinned generated diagnostic copy only. Nested CPU scopes, actual loop counters and safe partial checkpoints. `instrumentation-notes.md` defines every counter and cutoff.
- `check-parity.py`: four fixtures in summary/full-debug, full event-time/order and payload identity, stable summary parity excluding only measured validation wall time.
- `analyze-samples.py`: Top20 self/inclusive and observed stacks. All sample percentages count records, not static complexity or elapsed wall time.
- `run-postflight.py`: independent fingerprint validation for every completed large result, under the original resource guard.
- `plot-phases.py`: disjoint self-scope CPU figure, avoiding double-counted inclusive timers.
- `manifest-evidence.py`: SHA256 manifests for local raw artifacts and compact delivery.
- `collect-runtime.py`: explicit completed/partial resources, phases, counters and progress; verifies completed large summaries against accepted outputs.

## Reproduction on the original dot host

Run from `/workspace/scratch/c6ba02920254`. Expensive stages must be serialized, including compilation and decoding. Never weaken the guard to obtain completion. No saved Codex environment is needed or used.

```sh
H=$PWD/qwen-chunk-profile/experiments/qwen-chunk-cpu-profiling
RAW=$PWD/qwen-chunk-profile-raw
NATIVE=$PWD/wqe-completion-native
CONTROL=$PWD/qwen-model-size-raw/build-capacity-v2/pair-layer

# Existing native tree is pinned and has matching Release -O3 -DNDEBUG -g DSOs.
# Standalone app uses original -std=c++20 -O3 -g; no frame-pointer or optimizer change.
PROFILE_RAW=$RAW NS3_ROOT=$NATIVE bash "$H/build-profilers.sh"

# Run only in a NEW raw directory or choose a new case/variant destination.
python3 "$H/run-runtime.py" --raw "$RAW" --case chunk-streaming --variant sampled \
  --binary "$CONTROL" --input-dir "$H/evidence/reused-inputs/chunk-streaming"
python3 "$H/analyze-samples.py" --run "$RAW/runtime/chunk-streaming-sampled" \
  --perf "$RAW/perf-local/perf" --out "$H/evidence/samples-chunk"
python3 "$H/run-runtime.py" --raw "$RAW" --case chunk-streaming --variant timed \
  --binary "$RAW/instrumented/pair-layer" --input-dir "$H/evidence/reused-inputs/chunk-streaming"
python3 "$H/run-runtime.py" --raw "$RAW" --case chunk-streaming --variant control \
  --binary "$CONTROL" --input-dir "$H/evidence/reused-inputs/chunk-streaming"
```

Repeat Direct and No Balancing with their own exact inputs, keeping all fixed settings. Use the existing accepted small fixtures with `check-parity.py` before interpreting diagnostic counters. Compile/build was itself executed with the existing `wqe-completion-fix/guard.py` in this measurement; wrap local builds likewise when reproducing under the full stage policy.

The perf decoder is a local extraction of the hash-pinned official Debian packages from `../prefill-cpu-profiling/setup_perf.sh` and `perf-packages.sha256-urls`, not a security-setting change. The direct permission probe and a known-hot-loop calibration must pass. The explicitly scoped perf_event_open recorder is used for user CPU-clock samples; its counts are verified against decoded records and the known-hot-loop calibration.

## Stage separation

Preparation generates the plan/config/graphs once. Independent preflight reconstructs/checks those inputs separately. Simulator process initialization, `Simulator::Run`, online Audit/Validate, terminal FinalAudit and cleanup are further separated by diagnostic scopes; none is Python preflight. Postflight is the independent check with the completed executed-graph fingerprint. A timed-out Chunk has no completed summary and therefore no successful postflight or measured layer latency. External decode/report time is never simulator time.

## Retained evidence

Large perf.data, full decoded scripts/stacks and debug payload/log artifacts stay local and are SHA256-manifested. Compact raw perf summaries, sampling tables/SVGs, timer snapshots, controls, exact input copies and parity proofs are committed. Matching ELF hashes identify the immutable binaries used by DWARF decoding; no alternative symbols are substituted.


After all serialized measurements finish:

```sh
python3 "$H/collect-runtime.py" --raw "$RAW"
python3 "$H/run-postflight.py" --raw "$RAW" --graph-tool "$PWD/ep64-scaling-raw/build/graph-tool"
python3 "$H/plot-phases.py"
python3 "$H/manifest-evidence.py" --raw "$RAW"
```

The postflight script needs full accepted config/plan files in each provenance input directory; the compact input.txt alone is sufficient only for simulator launch. It refuses existing postflight output directories. Artifact collection/plotting does not rerun preparation or simulation. `local-raw-manifest.json` records the host-local retained files; it does not make those large artifacts available remotely. `DELIVERY_MANIFEST.json` hashes committed evidence except the manifests of that same name themselves.
