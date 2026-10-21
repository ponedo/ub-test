# CloudMatrix-inspired logical aggregate bandwidth experiment

Accepted source baseline: `3c2275eafea79426a441c819c8b65268492ff08e`.
Only the emitted network rate changes, from 100 to 3136 Gbps. The fixed real workload is Qwen3 L37, 2048 tokens, EP64, top-k 8, 128 logical experts, H=4096/I=1536. The existing Roofline model remains 100 TFLOP/s and 2692 decimal GB/s, with zero launch charge. No native protocol or accepted compute/scheduler/planner code changes.

Read [HARDWARE-REFERENCE.md](HARDWARE-REFERENCE.md), [source-audit.md](source-audit.md), [source-provenance.json](source-provenance.json), and the generated REPORT.md before interpreting results. 3136 Gbps = 392 GB/s is a **logical aggregate dual-die endpoint** capacity assumption, not a physical-link or verified single-peer measurement. The 20 ns propagation assumption is not the paper's 2.1 µs end-to-end WRITE latency. The accepted 5 ns allocator cadence and other protocol costs are unchanged, and may limit scaling.

## Files and evidence contract

- `stage-a.py`, `rate-probe.cc`: 32 two-rate small cases, native integer-rate/serialization/cell tests and actual ordinary-link 40/160-byte packet timing (not upper-layer processing), three bounded fault smokes, accepted-100 comparison.
- `prepare.py`: fixed four-strategy matrix, exact accepted baseline hash parity, rate-only input mutation, immutable identity ledger.
- `run-case.py`, `run-real.py`, `guard.py`: bounded resource admission and independently verified real runs; stop the matrix on a failure.
- `collect.py`: strict PASS gate, baseline/current source and compute-work checks, publication allowlist.
- `plot.py`, `report.py`: use collected PASS data only; PNG/SVG plots and formal report.
- `reproduce.sh`: root-location-independent entry point, sequential setup/build/test followed by the bounded matrix. It does not rerun the old full real Roofline matrix.

The 100-Gbps baseline is the accepted Roofline rows in `../qwen-roofline-compute/results/performance.csv` and its bounded per-strategy summaries. It is labeled reused historical evidence, not a fresh real rerun. `baseline-reuse.json` must prove all four baseline config/input/assignment hashes and semantic Planner hashes. The full private source maps are verified at collection but exported only as entry count, SHA-256 and accepted native-manifest reference/hash; binary identity counts/digests and input hashes remain public. Current binary hashes need not equal historical binary hashes. Exact per-physical-expert tokens, FLOPs, HBM bytes, durations and bottleneck classifications must match across rates. Planner and assignment identities are unchanged across the three balancing strategies.

Stage spans overlap and must not be summed. The report identifies the observed last Weight Ready expert(s), checks `dispatch_gate = max(weights_end, reroute_end)`, and reports latest compute end and combine/layer end. These constraints are not a uniquely traced causal critical path. No new allocator/CBFC/queue intervention is performed to isolate a bottleneck.

## Native setup

Use a disposable native tree already matching all 109 hashes in `../ultraep-multicast-integration/candidate-native-source-sha256.json`. No patch is introduced by this experiment.

For the available accepted local native base, checkout `b8375b51a094d3b1217b697989e1ab979f609e64` and apply these four existing patches exactly once, using `git apply --check` first, then `git apply` from that native tree:

1. `experiments/ub-multicast-v2/patches/native-write-v2.patch`
2. `experiments/ub-multicast-retransmission/patches/transport-fault-seam.patch`
3. `experiments/ultraep-multicast-integration/patches/peek-original-head.patch`
4. `experiments/ultraep-multicast-integration/patches/allocator-revalidation.patch`

Paths above are relative to the project repository, not the native tree. Pass absolute paths to `git apply`. Do not reapply patches to an already prepared tree. The extra CMake header registration must match the accepted v2 patch, not a new build workaround. For reconstruction from public upstream `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`, first follow the three earlier accepted patches in [the v2 README](../ub-multicast-v2/README.md), then the four patches above. The final 109-file manifest, rather than a matching branch label alone, is mandatory.

## Reproduction

Prerequisites: C++20, CMake, Ninja, Python 3 with psutil and matplotlib, the accepted project history, required native tools/submodules, and the authorized private routing/manifest/counts files. Do not distribute those private files. Supply fresh output outside the repository and do not run a second coordinator or a build concurrently with the real matrix.

From any working directory:

```sh
bash /absolute/project/experiments/cloudmatrix-bandwidth/reproduce.sh \
  /absolute/accepted-native /absolute/fresh-private \
  /absolute/routing /absolute/manifest /absolute/counts
```

This verifies accepted historical project contents and native hashes, records source identities, configures/builds native release with assertions on, logs off, tests on, examples/MPI/MTP/native optimization off, and `-j2`. It builds unchanged accepted executors plus the test-only rate probe, runs model units and the 32+3 Stage A gate, proves baseline reuse, executes the four 3136-Gbps strategies, collects, then renders. Full native build success is not a claim that every native test-runner test was executed. Failed build/guard receipts must be retained, not relabeled success.

For already completed private runs, the analysis commands are:

```sh
python3 experiments/cloudmatrix-bandwidth/collect.py --private PRIVATE --out FRESH_RESULTS
MPLCONFIGDIR=PRIVATE/mpl-cache python3 experiments/cloudmatrix-bandwidth/plot.py FRESH_RESULTS
python3 experiments/cloudmatrix-bandwidth/report.py FRESH_RESULTS --out REPORT.md
```

The collector expects `PRIVATE/stage-a` and `PRIVATE/real-3136`. Do not run Python with `-O`. It refuses a preexisting output directory. Plots are generated only once the completed evidence gate passes; no estimated results are substituted while runs remain pending.

## Resource limits and publication

At most two independent case workers, with historical peak × 1.05 plus remaining active growth, 128 MiB margin, 1 GiB host-available reserve and CPU/load admission checks. Per case: 6 GiB RSS tree, 7 GiB address-space limit, 4800-second whole-case wall guard, 8 GiB work-disk and 2 GiB tmp free-space floors, 8 GiB logical payload, one million weight tasks. Only aggregate minimum available memory, per-strategy CPU/wall/RSS, start/end times and concurrency, and scalar build receipts are published; detailed admission events and host records remain private. Host wall times under concurrency are not strategy-performance rankings; sandbox process visibility is incomplete.

Only strategy-level aggregate timings, correctness/work/communication totals, queue maxima without node identifiers, multicast fanout histograms, compact synthetic-test summaries and the explicitly requested last Weight Ready Expert IDs/timestamps are exported. Detailed baseline/new per-case directories, per-node/per-expert tables, packet records (including synthetic packet traces), online summaries, raw host/admission records and absolute-path source/binary maps remain private. Source/binary entry counts and proof digests preserve provenance without exposing the maps. The full private evidence is still validated before aggregation. The prior detailed publication was rejected; this narrowed aggregate-only deliverable excludes those files and requires normal delivery review.
