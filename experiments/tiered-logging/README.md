# Tiered logging and online validation

The accepted EP64 baseline is `dc17ac7c12d55e7a3444e4d2716aba351a5d75f0`.
This change affects observation, validation and persistence only. It does not change the planner, network configuration, segmentation, compute model, routing or task scheduling.

## Interface

Build the existing standalone executables using `experiments/pair-jetty/build.sh` and the accepted native tree, exactly as before. `pair-layer` accepts:

- `--logLevel=summary` (default): `online-summary.json`, `validation.json`, and optionally `--capacityMetrics=...`.
- `--logLevel=events`: summary plus `events.csv` containing application phase/expert/weight/chunk/relay events. It does not contain per-TA or per-token records.
- `--logLevel=debug`: the original complete events, TA identity, received payload/index, executed graph and native files, plus the same summaries.

`--jettyMode=pair` remains the default. Logging never changes its mapping. Use a fresh output directory for each run. Existing historical full-evidence regression runners explicitly request debug so that the unchanged strict offline verifier remains usable.

Summary and events bind the existing native `UB_TRACE_ENABLE`, `UB_PACKET_TRACE_ENABLE`, `UB_PORT_TRACE_ENABLE`, `UB_RECORD_PKT_TRACE` flags false before creating ports, and do not attach native file-writing observers. No large trace is generated and then deleted. Debug retains the previous flags and connections. No native patch is required.

## Correctness contract

The execution-input reader validates individual assignments, Top-k uniqueness, physical expert identity, unchanged main placement, quotas and weight provenance. Existing real received-byte checks and coverage trackers execute in every mode. The new `online-validation.inc` independently observes all application events before any persistence decision and keeps per-task/per-segment state:

- One send/admission/receive/verification/target completion for each expected segment, with matching identity, bounds and exact configured target delay; different segments may complete out of order.
- Ready only at the maximum required target-completion time; sender completion exactly once and no earlier than ready.
- Immediate dispatch/compute/combine and relay dependency gates; complete weight coverage and group-ready dependencies.
- Per-physical-expert compute durations and contiguous NPU service; exact per-token Top-k completion.
- Final byte-for-byte validation of every retained received buffer, including relay source-buffer provenance, after execution finishes.
- No remaining native Pair Jetty work or missing response/admission state at termination.

Any failure produces an explicit error, `validation.json` with FAIL and a nonzero exit. Controlled duplicate tracker notifications remain deduplicated and recorded, while duplicate real execution/completion notifications are rejected. The existing synthetic payload is a functional byte oracle; it is not numerical GEMM.

`preflight.py` provides independent cross-file checks: it reconstructs every execution input integer and assignment from config/plan, invokes the accepted graph helper to reconstruct weight edges and group dependencies, and compares the executed graph fingerprint. It runs before and after the simulator. Keep the input configuration, seed and version identity together with `input-summary.json`; lightweight output does not mean undocumented input.

The 64-bit FNV fingerprints are supplementary deterministic parity identifiers, not cryptographic integrity or replacements for individual task and byte checks. Debug continues to pass the original independent full-file Python oracle.

## Metrics and time accounting

`online-summary.json` records phase boundary times, per-NPU compute intervals and per-stage `[first send,last target ready]` intervals. These spans overlap: never sum all phase durations to derive layer latency. Layer latency is the layer-end minus layer-start timestamp.

Packet/byte counters attach to unconditional real `UbPort::PortTxNotify` and `PortRxNotify` callbacks. Arrays index the NPUs first and the switch last. Endpoint totals are the sum excluding the final switch element. All-hop totals include switch forwarding and must not be described as unique application packets. Wire-byte counters include protocol traffic; `verified_bytes`, `remote_bytes` and `local_bytes` are application payload, by dispatch/combine/weight stage.

`verification_wall_ns` includes nested online observer time, target byte checks, and the final independent buffer/state sweep. It is measured host time already contained in simulator wall time, not simulated NPU time and not an additive extra. Input parsing/contract validation and standalone pre/postflight are measured separately by scripts. The online timer itself has host overhead in all modes.

Host wall, CPU and peak RSS come from the guarded runners. Summary schema adds no fixed network delay or scheduled observer events.

## Retention policy

Commit source, configuration, resource/statistics CSV/JSON, plots, this report and small test evidence. Keep large debug artifacts local only when needed. A normal scan must not upload raw native trace/payload archives. A fault or protocol investigation can enable debug for that specific case. This change does not remove or rewrite already accepted historical evidence.

## Reproduction

See `run.py --help` for the cross-mode/fault matrix and `preflight.py --help` for standalone input validation. The revised EP64 `run.py --log-level summary` is the normal lightweight entry; events/debug are explicit options. See `REPORT.md` for the exact executed commands, artifacts, measured reductions and limitations.
