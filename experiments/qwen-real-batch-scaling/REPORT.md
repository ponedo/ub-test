# Real Qwen235B batch scaling: measured results

Scoped acceptance state: PASS (raw driver state: STOPPED); 27 new verified cases plus 9 reused historical cases.

## Scope and interpretation

Real routing from 8 requests (4,275 available tokens) is concatenated into nested N=256/512/1024/2048 prefixes for each of serialized layers 0, 37 and 52. This is a controlled routing-prefix experiment, not an actual serving scheduler batch or independent samples across N. Each strategy comparison uses exactly the same (N, layer) input. Only completed, independently validated PASS cases appear in latency and speedup charts. Unexecuted or protected-stop cases are left missing; no theoretical values fill gaps.

Fixed assumptions: H=4096, I=1536, E=128, top-k=8; idealized FP8 weights (18 MiB per expert, no scale metadata), BF16 activations, 500 GFLOP/s compute, EP64 with expert main rank e//2 and source rank token_id%64; 100 Gbit/s links, 20 ns link delay, 1024-byte TA and 4096-byte chunk; pair jetty mode. These are simulator assumptions, not measured hardware throughput.

The raw outer driver records STOPPED because it was deliberately terminated at the user-requested N2048 boundary. Scope acceptance separately requires all 27 new cases to PASS plus the explicit USER_SCOPE_LIMIT_REACHED marker; this is not a resource failure.

N256 fanout counts are independently validated, reconstructed planner/graph statistics, checked against historical replica counts, weight bytes/WQEs/TAs and the complete per-NPU load vector. They are not a new performance run.

planning_ms and reroute_ms are simulated event-timeline deltas: planning_end minus layer_start, and reroute_end minus planning_end. They are not host planner wall-clock measurements. All 36 rows contain both fields.

N256 latency is reused from the earlier validated experiment. Its host elapsed/CPU times are not comparable to new runs after environment recovery. Stage spans overlap and must not be added as a serial latency decomposition. Weight-duration fraction is descriptive and is not an attribution of critical-path delay.

## Observed speedups and finite-grid break-even

- Layer 0, Direct: N=256: 0.950× (7.775 ms), N=512: 1.333× (10.396 ms), N=1024: 1.451× (15.331 ms), N=2048: 1.540× (23.644 ms); first observed winning N=512.
- Layer 0, Chunk streaming: N=256: 0.950× (7.775 ms), N=512: 1.333× (10.396 ms), N=1024: 1.451× (15.331 ms), N=2048: 1.540× (23.644 ms); first observed winning N=512.
- Layer 37, Direct: N=256: 1.277× (11.209 ms), N=512: 1.886× (10.242 ms), N=1024: 1.903× (15.334 ms), N=2048: 3.292× (27.073 ms); first observed winning N=256.
- Layer 37, Chunk streaming: N=256: 1.649× (8.680 ms), N=512: 1.886× (10.242 ms), N=1024: 1.903× (15.333 ms), N=2048: 3.515× (25.357 ms); first observed winning N=256.
- Layer 52, Direct: N=256: 1.306× (19.795 ms), N=512: 1.938× (17.113 ms), N=1024: 2.321× (17.048 ms), N=2048: 3.049× (28.802 ms); first observed winning N=256.
- Layer 52, Chunk streaming: N=256: 2.298× (11.254 ms), N=512: 2.425× (13.680 ms), N=1024: 2.321× (17.048 ms), N=2048: 3.398× (25.844 ms); first observed winning N=256.

### Main findings

- Layer 0 changes from a slight loss at N256 (~0.950×) to a win at N512 (~1.333×), then improves to ~1.540× at N2048. The tested-grid crossover lies between the 256- and 512-token prefixes; this is not an interpolated scheduler threshold.
- Layers 37 and 52 already win at the smallest tested N256. At N2048 Chunk reaches 3.515× and 3.398× respectively, so no lower critical batch was located for these layers.
- The routing distributions are non-monotone: N1024 has no actual relay forwarding in any layer, while N2048 activates two relay experts in each of L37 and L52. More tokens do not mechanically imply more useful fanout.
- At N2048, L37 is slightly more skewed than L52 and has the larger NoBalancing latency. Layer identities must not be frozen into low/medium/high skew labels.

The first observed winning size is only a tested-grid result. A continuous critical batch size cannot be identified from these discrete, changing prefix distributions. A win already at N256 provides no lower crossover bound. Non-monotone routing skew means later wins or losses need not follow a single universal threshold.

## Chunk versus Direct and bottleneck evidence

- N=256, layer 0: Direct / Chunk latency = 1.000×; weight duration 5.151 → 5.151 ms; replicas 39. Actual relay experts 0, max main copies 2 → 2.
- N=256, layer 37: Direct / Chunk latency = 1.291×; weight duration 8.586 → 6.056 ms; replicas 44. Actual relay experts 1, max main copies 5 → 3.
- N=256, layer 52: Direct / Chunk latency = 1.759×; weight duration 17.171 → 8.630 ms; replicas 43. Actual relay experts 5, max main copies 6 → 2.
- N=512, layer 0: Direct / Chunk latency = 1.000×; weight duration 5.151 → 5.151 ms; replicas 32. Actual relay experts 0, max main copies 2 → 2.
- N=512, layer 37: Direct / Chunk latency = 1.000×; weight duration 5.151 → 5.151 ms; replicas 45. Actual relay experts 0, max main copies 3 → 3.
- N=512, layer 52: Direct / Chunk latency = 1.251×; weight duration 12.019 → 8.586 ms; replicas 49. Actual relay experts 3, max main copies 4 → 3.
- N=1024, layer 0: Direct / Chunk latency = 1.000×; weight duration 5.151 → 5.151 ms; replicas 34. Actual relay experts 0, max main copies 2 → 2.
- N=1024, layer 37: Direct / Chunk latency = 1.000×; weight duration 5.151 → 5.151 ms; replicas 48. Actual relay experts 0, max main copies 3 → 3.
- N=1024, layer 52: Direct / Chunk latency = 1.000×; weight duration 6.867 → 6.867 ms; replicas 45. Actual relay experts 0, max main copies 3 → 3.
- N=2048, layer 0: Direct / Chunk latency = 1.000×; weight duration 3.437 → 3.437 ms; replicas 41. Actual relay experts 0, max main copies 2 → 2.
- N=2048, layer 37: Direct / Chunk latency = 1.068×; weight duration 6.867 → 5.151 ms; replicas 53. Actual relay experts 2, max main copies 4 → 3.
- N=2048, layer 52: Direct / Chunk latency = 1.114×; weight duration 8.585 → 5.627 ms; replicas 46. Actual relay experts 2, max main copies 4 → 3.

Cases with zero actual relay experts cannot demonstrate a relay-forwarding benefit. Sub-microsecond Direct/Chunk differences in those cases are reported as tiny timing differences, not attributed to relay; their exact cause was not isolated.

### Bottleneck shift at N2048

The measured maximum NPU compute interval is 19.781 ms for both balanced strategies on all three layers. This occupies about 84%, 78% and 77% of Chunk layer latency for L0/L37/L52. NoBalancing max compute intervals are 35.711/87.426/86.143 ms, almost the full layer latency; load balancing sharply lowers the long compute tail. These are interval comparisons, not additive critical-path attribution.

For L37, Chunk reduces weight completion duration by 1.716 ms and layer latency by 1.716 ms versus Direct; for L52 the corresponding reductions are 2.958 ms and 2.958 ms. Both activate two relay experts and lower maximum main-origin copies from 4 to 3. This closely aligned measured reduction supports weight distribution as the remaining Direct-to-Chunk lever, while compute occupies most of the final balanced latency. It does not prove a general hardware bottleneck or isolate forwarding from readiness effects.

Direct and Chunk use the same placement objective but differ in graph forwarding and readiness; their observed difference is the combined effect, not a pure causal estimate of fanout alone. Compare actual relay counts and main-origin copies before attributing a benefit to relay. Main outgoing copies count distinct physical targets; thousands of chunk tasks are not thousands of replicas. R is replicas excluding the main; total physical instances include the main. Eligibility is distinct from actual forwarding, especially for Direct.

Skew is measured separately at each N. In particular layers 37 and 52 reverse order at N2048; fixed low/medium/high labels would be misleading. Input-skew plots include audited inputs even where execution remains unmeasured.

## Out-of-scope retained input evidence

The audited N4096 source-prefix skew remains in input-skew.json as static provenance only. N4096 is excluded from performance scope, planned-case counts, missing-case inventories and all main plots. It is not scheduled or accepted as a performance result.

## Artifacts and reproduction

- performance.csv and aggregate.json: whitelisted per-case aggregates, including provenance and paired speedup.
- input-skew.json: audited prefix skew.
- coverage.json: current completion status.
- plots/01–06: PNG and SVG plot sets.
- collect.py accepts explicit private aggregate-ledger root, historical results directory and audited skew file. analyze.py reads only the collected results. Neither executes the simulator or reads token/payload artifacts.

Pinned graph authority: https://github.com/ponedo/ub-test/blob/93bdf7fef154743738910da9e561d796f5955507/experiments/direct-weight-forward/weight-distribution.h

No raw tokens, payloads, native simulator logs or host command lines are included in these public outputs.

## Regression checks

The accepted small8 case passes all four strategies, including TwoStage. The H64/I128 N256 Zipf regression exactly matches the baseline for all three tested strategies in latency, WQEs, TAs, replicas, simulator events, completion counts and routing SHA256. Planner strict-floor and upstream-compatible checks, dependency-index equivalence, source extraction, independent validation, precision, fanout and scope-gate tests also pass. See results/regression-summary.json and its companion regression JSON files.

No native protocol source was changed in this milestone. The full native regression matrix was not rerun; the baseline evidence is retained. These synthetic regression checks are separate from the real-routing performance measurements above.
