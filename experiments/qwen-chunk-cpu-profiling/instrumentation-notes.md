# Diagnostic application instrumentation

This is a generated-copy-only diagnostic. `generate-instrumented.py` pins and reads
`experiments/pair-jetty/pair-layer.cc` and `online-validation.inc`; it never writes
those files or the native source/build tree. The generated copy resolves the three
original local header paths absolutely, keeps a local generated validation include,
and adds `profile-runtime.h`.

## Build and run contract

Generate with:

```sh
python experiments/qwen-chunk-cpu-profiling/generate-instrumented.py \
  --out /workspace/scratch/c6ba02920254/qwen-chunk-profile-raw/instrumented
```

Compile this application's generated `pair-layer.cc` with exactly the baseline
`-std=c++20 -O3 -g`, native include/library paths, link libraries and rpath. No native
recompilation or native changes are required. The parent experiment's
`build-profilers.sh` owns this step and its recorded command.

Enable the timers with:

```sh
QWEN_CPU_PROFILE=1 QWEN_CPU_PROFILE_OUT=/absolute/path/timing.json \
  /path/to/generated-app [unchanged baseline arguments]
```

The latest complete JSON snapshot is atomically renamed onto the output path. A
history defaults to `timing.json.jsonl`; set `QWEN_PROFILE_HISTORY` to a preferred
JSONL filename, or the empty string to disable history. The parent directory must
already exist. `QWEN_PROFILE_CHECKPOINT_SECONDS` defaults to 1 and accepts 0.05–3600.
`QWEN_PROFILE_JSON` is a compatible output-path alias. With no output path,
instrumentation is inactive; `QWEN_CPU_PROFILE` set to any value other than `1`
explicitly disables it. Setting the output path alone also enables it.

## Timing and counter semantics

- CPU timers use `CLOCK_PROCESS_CPUTIME_ID`, not simulated time or wall time.
  The original single-threaded simulator/application is assumed.
- Every instrumented scope reports calls, completed calls, active calls, inclusive
  CPU ns and self CPU ns. Self subtracts nested instrumented children only.
  `Simulator::Run` self therefore includes native simulator/network work and any
  application code outside explicitly instrumented children; it is not exclusively
  native work. Inclusive values overlap and must not be summed.
- A snapshot overlays elapsed CPU for every live scope. Ongoing Read/dependency,
  Audit, Send/Validate/Ready or Simulator scopes are included even at termination.
  Active-stack order is innermost first. Sum of self times across phases equals
  program inclusive time, apart from sampling/rounding noise.
- Snapshot serialization and I/O CPU are excluded from every active scope. The
  overhead fields give the cumulative cost of earlier snapshots. Timer reads,
  counter increments, checks and observer setup are still instrumentation overhead;
  compare baseline and instrumented runs to quantify total overhead. Kernel sample
  profiles of the unchanged executable remain the primary attribution evidence.
- Read has nested edge generation, transfer allocation, dependency graph and replica
  buffer timers. InitAudit, Topology, Simulator::Run, Audit (plus group, weight and
  weights-end scans), FinalAudit, Send, Validate, Ready, summary/payload writing,
  UbUtils destruction, Simulator destruction and Layer member destruction are timed.
  Read self covers the remainder of parsing/initialization. Program self covers
  command setup and other uninstrumented application operations.
- Dependency candidates count inner parent-loop visits after the source-replica
  filter. Dependency edges count accepted graph edges. Group/weight scan candidates
  count all visited weight transfers before the matching predicate; matches count
  predicate successes. At an interrupted checkpoint the last entered candidate may
  not have completed its original predicate yet. The original loops, predicates,
  assertions and their order remain intact.
- Payload counters are bytes successfully allocated/generated/validated/checked at
  the end of the corresponding buffer operation. A partially completed current
  buffer is not counted. Final task, relay-provenance and replica checks are separate
  repeated byte visits, not distinct payload-volume categories to de-duplicate.
- `remote_wqes_planned` is the original Topology remote task count; it is not sent
  work. `remote_wqes_submitted` increments after successful original SubmitWqe.
  `TA_count`, sender completions, completed tokens and pending replica weights come
  directly from initialized application counters. Packet/byte totals sum the
  original per-node port counters, including switch ports and all protocol traffic;
  these are not end-to-end unique payload totals.
- Progress is observed only from the main thread at safe function/loop boundaries.
  The observer is installed after Layer construction and cleared before original
  members are destroyed. Model sizes can be partial during Read; nodes and physical
  experts are populated when Read finishes.

## Checkpoints, cutoff and simulated-event isolation

The SIGTERM handler only writes a `volatile sig_atomic_t` flag. It never reads
application state, accesses clocks, performs I/O or calls ns-3. At the next normal
instrumented boundary, the main thread writes a terminal `reason=signal` snapshot
including active timers, then calls `_Exit(143)`. This is an intentionally partial
measurement, not a completed validation. It does not run expensive cleanup.

There are no added Simulator scheduling, Stop, Run or Destroy operations. At coarse
phase entry/exit, a snapshot is forced. Hot function entry/exit checks inspect the
signal flag and sample steady wall time every 256 checks. Large dependency/Audit
candidate loops check every 4096 visits; the wall-clock read is therefore normally
at most every roughly one million candidates, interspersed with function checks.
The interval is a sampling target, not a real-time guarantee. A long uninstrumented
native operation or payload loop can defer the final snapshot until its next safe
boundary. An external hard-kill grace period is still required. If SIGKILL wins,
retain the last completed history/latest snapshot and disclose its wall timestamp.

Session setup starts before Time::SetResolution, but it does not call ns-3. Simulator
counters are not queried before the original Schedule/Stop setup and entry into the
original Run. `simulator_counter_live=false` with zero early counters means the
simulator has not yet been observed; it does not claim no events were scheduled in
Topology. At Run return, final event count/time are frozen before destruction so
later snapshots cannot accidentally instantiate another Simulator. On failed runs
still inside Run, the existing simulator remains the one observed.

## Required verification

Generation writes a manifest, a complete application instrumentation diff and
`instrumentation-source-proof.json`. It verifies pinned baseline SHA-256 values
before and after generation, exact reverse-erasure of all diagnostic edits, and
byte-exact equality/order for all 11 original Simulator control call expressions,
including scheduling arguments and lambda bodies. This is a static transformation
check; it does not substitute for runtime parity.

The parent experiment's `check-parity.py` is the runtime gate. Use identical inputs,
arguments and log levels for unchanged and instrumented executables. Full small
`debug` runs must have byte-exact event timestamps/order, TA identity CSV, graph and
payload artifacts. Stable summary/validation JSON must match after removing only
`verification_wall_ns`. Summary-mode counts, packet/byte totals, simulator event
counts and simulated completion time must match too. Do not infer event parity for
a stopped large run from matching wall-clock progress.

Initial state of this deliverable: generator/static proof and Python syntax checks
passed. Native application compile, runtime parity and total-overhead measurement
are owned by the parent experiment and were not run by this worker.
