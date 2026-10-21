# Reproduce the passive reversal diagnosis

Read [REPORT.md](REPORT.md), [source-audit.md](source-audit.md), and
[DIAGNOSTIC-SEMANTICS.md](DIAGNOSTIC-SEMANTICS.md) before interpreting counters.
This package diagnoses the existing strategies; it does not optimize them.

## Inputs and workspace

The harness intentionally reuses the accepted private CloudMatrix experiment
workspace. It does not download or publish restricted routing traces. Reproduction
requires the same authorized L37/2048 input and accepted control outputs, with the
identities checked by the harness. Keep the existing `bandwidth-work`,
`bandwidth-native`, and `bandwidth-private` controls unchanged. Use this delivery
checkout as `diagnosis-work`, a separate native copy as `diagnosis-native`, and
fresh output directories under `diagnosis-private`.

The native base is b8375b51a094d3b1217b697989e1ab979f609e64. First apply the four
accepted patches, in order, from this checkout:

1. `experiments/ub-multicast-v2/patches/native-write-v2.patch`
2. `experiments/ub-multicast-retransmission/patches/transport-fault-seam.patch`
3. `experiments/ultraep-multicast-integration/patches/peek-original-head.patch`
4. `experiments/ultraep-multicast-integration/patches/allocator-revalidation.patch`

Then apply this package's `patches/native-diagnostics.patch`. The adjacent native
manifest records all nine accepted/diagnostic file hashes; the patch was verified
forward and reverse against the accepted patched tree. Do not apply these patches
to the accepted control tree.

## Guarded commands

Run from the workspace containing these directories, using new output paths:

```sh
H=diagnosis-work/experiments/multicast-reversal-diagnosis
python3 "$H/build-native.py" --native diagnosis-native --out diagnosis-private/native-repro --tools real-batch-build-tools
python3 "$H/build.py" --native diagnosis-native --out diagnosis-private/build
python3 "$H/stage-a.py" --build diagnosis-private/build --out diagnosis-private/stage-a
python3 "$H/prepare.py" --build diagnosis-private/build --stage-a diagnosis-private/stage-a --out diagnosis-private/real-3136
python3 "$H/run-real.py" diagnosis-private/real-3136 --build diagnosis-private/build
python3 "$H/analyze.py" diagnosis-private/real-3136
python3 "$H/compare-resources.py" diagnosis-private/real-3136
python3 "$H/verify-prefix-union.py" diagnosis-private/real-3136
python3 "$H/export-evidence.py" diagnosis-private/real-3136 --out diagnosis-private/evidence-review
python3 "$H/verify-prefix-outcomes.py" diagnosis-private/real-3136 --out diagnosis-private/evidence-review/prefix-outcome-decomposition.csv
python3 "$H/plot.py" diagnosis-private/real-3136/analysis/analysis.json diagnosis-private/figures
```

Omit `--tools` when the same CMake/Ninja tools are already on PATH. Native build
uses two compiler jobs, assertions enabled, logging disabled, and only the
unified-bus library target; it is not a claim that every native test suite ran.
The delivered native-build wrapper uses the same executed configuration and guard;
its CLI/syntax were separately checked after the final runs. Runtime native and
application sources were frozen during all runs.

The formal coordinator admits only Chunk and Multicast at 3136 Gbps, with
independent output paths and conservative peak-aware admission. In the delivered
run it chose sequential execution. It keeps 6 GiB process-tree RSS, 7 GiB address
space, 1 GiB host memory reserve, 8 GiB output-disk and 2 GiB temporary-disk reserves,
and a 4800-second whole-case limit. Never lower guards to reproduce a timing.

Instrumentation defaults OFF. No new events are scheduled by observation. Only
actual evaluated predicates and existing queue/port events are observed.
The private full outputs are not publication artifacts. Public CSVs intentionally
contain aggregate controls and a bounded, selected critical-event subset.

## Evidence quality

- Final v3: exact accepted latency, complete online validation, and per-expert
  compute/readiness parity; all seven observer integrity counters zero.
- Earlier v2: a duplicate-UID residence-key defect was found. Its VOQ residence
  aggregates were discarded. Final published queue evidence comes from repaired
  FIFO matching and reruns; no protocol correction was involved.
- Observation intervals, overlapping packet-time sums, and disjoint resource
  occupancy are different quantities. Do not add them as independent latency.
- Zero arithmetic residual is not complete causal attribution. The report labels
  reconstructed Jetty state and the still-unquantified causal share of idle time.

The sanitized postflight exporter was rerun and reproduced all ten base evidence CSVs byte-for-byte. It fails closed if a complete v3 Jetty cycle is not retained; it does not silently substitute older evidence. Exported candidates still require human review before publication.
