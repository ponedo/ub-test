# Qwen3-30B-A3B dimension sensitivity and capacity validation

## Scope and fixed inputs

This is a single-MoE-layer dimension sensitivity experiment. It uses official Qwen3-30B-A3B dimensions, synthetic Zipf α=1.1 routing (seed 20261016), and assumed effective NPU compute throughput. No Qwen weights or real model/router execution are involved. EP64, E128, top-k8, main placement, accepted upstream-compatible Planner, Pair Jetty, 100 Gbit/s links, 20 ns link delay, TA1024 and Chunk4096 remain the accepted configuration. The separate synthetic payload-pattern seed remains 20261015, unchanged from the baseline; it is not the routing seed.

The exact accepted application baseline is remote `099f6bcb15204afbd572fe860c7d0955c624973c` (local equivalent tree `4862889a8bfc569f66558c8e8589c871cf9ce135`). Native ns-3-ub is unchanged at `2fde39d02920e639f5b200d0c5262a517326deb8`, tree `c27d1faef570e6da9900a71aa0a37180a58dfba8`. Native library/binary/source hashes are recorded with execution evidence.

## Model connection

Official immutable sources and config checksum are in MODEL_PARAMETERS.md and provenance.json. Use H=2048 and routed expert I=768, not the config's dense intermediate size 6144. The existing model interface already computes all dimensions consistently; no compute formula change was necessary:

- Three bias-free matrices: 3HI = 4,718,592 parameters/expert.
- BF16 expert weights: 6HI bytes = 9,437,184 bytes = 9 MiB.
- Dispatch and Combine each carry 2H = 4096 bytes per assignment.
- GEMM-only compute: 6HI = 9,437,184 FLOPs/assignment.
- Existing effective throughput 1000 GFLOP/s × 0.5 = 500 GFLOP/s gives 18,874.368 ns/assignment, with 100 ns setup per nonempty physical expert. Physical experts on one NPU are serialized; NPUs can overlap.

Weight/GEMM dimensions grow 192×; vector payload grows 32× relative to H64/I128. Fixed planning 200 ns and reroute 100 ns are simulation assumptions distinct from measured Planner CPU wall time. SiLU/product/router/combine kernels, HBM weight-read costs, load-dependent GEMM efficiency and hardware-specific scheduling are not calibrated. This is not an Ascend performance measurement or full Qwen inference benchmark.

## Capacity changes

The initial real adapter rejected 256 tokens because 16 MiB of token payload plus 51×9 MiB replica weight payload equals 475 MiB, exceeding its old 256 MiB logical budget. The unchanged graph generator independently produced 62,232 weight WQEs, exceeding the old 20,000 limit. These were software guards, not observed OOM.

After explicit user approval, bounded configurable ceilings were added across adapter, independent preflight and executor: payload up to 8 GiB and weight WQEs up to 1,000,000, with the original defaults retained. Checked uint64 arithmetic and signed task-index/uint32 segment bounds are checked before payload allocation. A metadata-only edge-count prediction prevents enormous chunk range construction before task-limit rejection. Actual memory is allocated only for actual work. See CAPACITY_DESIGN.md and the boundary tests.

The process safeguards remain 6 GiB RSS, 7 GiB address space, 300 seconds per stage, 8 GiB free workspace disk, and the accepted available-memory and `/tmp` protections. Logical payload is not RSS. Preparation, preflight, simulator and postflight are measured separately; none of their host times is simulated NPU time.

## Measured results

See results/model-size-comparison.csv, results/qwen-scan-coverage.csv and four figures. Only successful completed native event executions have latency/speedup values. Missing points are not extrapolated. The H64/I128 series is the accepted historical 21-run measurement set; cross-model routing SHA256 and physical load/replica equality are asserted for completed common points.

The 256-token capacity gate reached the unchanged 300-second simulator wall protection for Chunk Streaming. Scaling stopped; 1024–12500 tokens were not run. No OOM was observed and the RSS protection was not reached. Maximum successfully executed Qwen size is **256 total EP-group tokens / 2048 assignments**, for No Balancing and Direct. There is no fully completed three-strategy Qwen point yet.

|256-token strategy|Layer latency|Speedup|Simulator host wall|Peak RSS|Completed remote WQEs / TAs|
|---|---:|---:|---:|---:|---:|
|No Balancing|7.957270688 ms|1.000|2.258 s|144104 KiB|4046 / 16184|
|UltraEP Direct|12.690087432 ms|0.6270462|120.094 s|1656376 KiB|3941 / 485576|
|UltraEP Chunk Streaming|unavailable|unavailable|300.38 s, wall guard|1527924 KiB|incomplete; no completed counts|

Direct has 51 replicas and 481,296,384 bytes (459 MiB) of weight distribution. Its 51 weight WQEs contain 470,016 TAs; weight completion duration is 12.019932360 ms. Maximum NPU assignment load falls from 406 to 34. At this small point, weight distribution exceeds the saved compute critical path, so Direct is slower. The measured maximum per-NPU compute duration falls from about 7.663 ms to 0.642 ms; exact values and endpoints are in CSV/summary.

Chunk's independently validated input contains 62,232 weight WQEs and the same 470,016 weight TAs/459 MiB. These are **planned input counts**, not a completed run result. Preparation took 202.07 seconds for the shared three-strategy inputs. Chunk independent preflight took 214.11 seconds and passed. The simulator then hit the wall guard at 300.38 seconds. The incomplete run produced no successful layer summary and was not fed into speedup calculations. The source contains repeated dependency scans, and preparation/verification are demonstrably expensive; this task did not CPU-profile the incomplete simulator and does not claim those scans alone explain its timeout.

There is not enough completed Qwen data to establish a crossover, token-scaling trend, or Direct-versus-Chunk performance comparison. The old H64/I128 12,500-token 9.85× result cannot be transferred to Qwen dimensions.

Phase span intervals overlap. Dispatch/Compute/Combine span lengths must not be added to reconstruct Layer Latency. The compute plot uses maximum individual NPU compute duration, rather than the wall-clock envelope of all asynchronous NPU compute intervals. Full stage endpoints are retained in the summary evidence.

## Correctness and regression

- Official model/formula/control-variable checks passed. The 256-token UltraEP plan exactly matches the historical plan in every field except measured host `cpu_wall_ns`, including physical placement, per-replica quotas, source quotas and token mapping; see exact-logical-plan-parity.json.
- Four unchanged small-model fixtures passed Summary, Events and Debug plus original pre-logging Debug: 16 actual runs. Timing, WQE/TA/event counts, payload and strict old-debug evidence parity passed.
- Capacity boundary tests include original defaults, maximum supported ceilings on tiny actual demand, zero/negative/above-supported/uint64-overflow CLI values, early native huge-edge rejection and adapter rejection before graph-tool invocation.
- 120 seeded metadata edge predictions matched the unchanged native graph generator across strategies, forced/fallback relay, nondivisible chunks and shard cuts.
- Nine independent preflight valid/tampered cases passed.
- All 13 existing fault injections were detected in Summary mode with nonzero exit and FAIL validation.
- Existing Planner numeric support-domain regression passed. The Planner and native protocol code were not modified; no claim is made that a fresh full native protocol test suite was rerun for these application-only capacity changes.

Every successful Qwen execution retains actual target-byte verification, segment coverage, WQE completion association, replica/chunk/relay prerequisites, logical assignment/quota checks and all top-k contributions. Aggregate counters do not replace per-task validation.

## Reproduction and limitations

Build/run and analysis commands are in README.md. Fixed configuration is fixed-config.json. collect.py selects small aggregate evidence and original routing, excluding native packet traces and payload files. Full debug logging was used only for small regression fixtures.

The existing Python relay adapter and independent verifier construct dependency lists with repeated scans over weight transfers. Large Qwen graphs can make this host work expensive; it has deliberately not been optimized in this task. An incomplete or guarded execution provides capacity evidence but no valid performance point. Actual routing still requires running the model; synthetic popularity does not establish Qwen gate behavior. Further scale or implementation changes should be decided from the measured stopping condition, without weakening validation or resource protection.
