# Expert Compute Roofline

Parent: `ef1ec5c801ab854363b6382a2af9aa5237ade4c8`. This experiment changes only the per-physical-Expert compute duration and adds read-only evidence. The accepted Planner, multicast adapter, native source and network configuration are unchanged.

- `layer.cc`: parent executor plus model selection, strict integer-rate CLI and Expert evidence. Existing serial NPU scheduler/Weight Ready/Dispatch/Combine dependency code remains unchanged.
- `compute-model.h`: checked integer-picosecond roofline; `oracle.py` is an independent Python implementation.
- `model-probe.cc`, `test-model.py`, `verify-compute.py`: units/overflow/zero/parameters, actual replica-token counts and serialization validation.
- `stage-a.py`: parent/legacy exact parity, roofline, fault/negative tests.
- `prepare-real.py`: frozen real L37/N2048 preparation and source audits, accepted Planner identities.
- `run-real.py`/`run-case.py`: peak-budgeted independent subprocesses, immutable inputs/builds, per-case output, bounded resource guards and failure cleanup.
- `collect.py`, `plot.py`, `report.py`: allowlisted data and reproducible analysis.

## Interface

The executable defaults to `--computeModel=legacy`. Formal new runs use:

`--computeModel=roofline --compute-tflops=100 --hbm-bandwidth-gbps=2692`

Rates are positive decimal integer TFLOP/s and GB/s, not Gbit/s. Supported CLI bounds are1..1,000,000 TFLOPS and1..100,000,000 GB/s; these are input safety bounds, not realistic hardware claims. Decimal fractions, scientific notation, negative and trailing garbage are rejected rather than silently truncated. Legacy input.txt format remains unchanged; its original peak/util/setup fields remain meaningful only for Legacy. Model/rates and the active zero-launch roofline contract are recorded separately in compute-model.json.

See [MODEL.md](MODEL.md) for FLOPs, every activation read/write, HBM residency/cache assumptions and the fixed-version CloudMatrix384 source.100 TFLOPS is hypothetical.2692 GB/s is extrapolated from a single-die MLA result, not measured Expert GEMM throughput.

## Reproduction

Use the accepted native tree from the parent integration, matching all109 hashes in `../ultraep-multicast-integration/candidate-native-source-sha256.json`. To reconstruct from upstream d6aa9e2, follow the preceding v2/retransmission README patches, then apply the integration's peek-original-head and allocator-revalidation patches. This task adds no native patch.

Require C++20, CMake, Ninja, Python3 with psutil, and matplotlib for plots. No restricted routing data is distributed. Supply the same authorized private routing/manifest/raw-source files and frozen count file whose hashes are checked by prepare-real.py. All output paths must be fresh.

`bash experiments/qwen-roofline-compute/reproduce.sh NATIVE FRESH_PRIVATE ROUTING MANIFEST COUNTS`

The current reproduction intentionally uses native-j2 from the outset. The recorded run initially tried-j4, hit the then-required4GiB host reserve, and resumed-j2; that failure remains in the report. The user subsequently authorized1GiB reserve.Each simulator keeps6GiB tree RSS,7GiB AS,4800s wall,8GiB work-disk/2GiB tmp free,8GiB logical payload and1,000,000 weight tasks. No process count alone constitutes resource admission: run-real accounts for historic peaks×1.05, active expected peak growth, current host available memory,128MiB extra margin and CPU load. At most2 case workers run. Do not run another coordinator or build concurrently; sandbox PID visibility does not establish global machine idleness.

The collector validates all four case receipts and requires exact unchanged weight durations versus historical legacy. It reports historical Legacy separately, not as fresh full real reruns. Small Legacy equivalence plus unchanged native source/scheduler/input identities support that comparison; any regression failure blocks formal execution. Simulation times are compared, not overlapping host wall times.

Results include per-Expert/per-NPU aggregate evidence and synthetic small-fault packet traces. They exclude restricted raw routing, actual per-token rows, payload bytes and large Debug logs. Stop after remote delivery verification and await acceptance.

Publication privacy reduction: individual native pair/sequence-state CSVs remain private. Public transport-state-summary.json records counts, all-window-drained checks and zero pending state without endpoint pairs or individual sequence values.
