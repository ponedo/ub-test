# CPU Quota-Driven Planner

Independent single-layer CPU implementation, based on [UltraEP v3, §5 and Algorithm 1](https://arxiv.org/html/2606.04101v3) and reviewed against [UltraEP v1.0.0 at 94cab099](https://github.com/Dots-Infra/UltraEP/tree/94cab099b44fffa99a82fea99e7c12d89cf65e4f). Base repository commit: `0f94188d7ecedb2f736cf3580fce0b14f494d1c9`.

## Run

Python 3.10+ and g++ with C++20 and pthread support are sufficient. No CUDA, ns3, pip packages, or network is required for the CPU suite.

```bash
bash planner/quota/run.sh
python3 planner/quota/planner.py planner/quota/evidence/skew/input.json /tmp/quota-output.json
python3 planner/quota/planner.py experiments/no-balancing-layer/evidence/n64/config.json /tmp/quota-n64.json --from-no-balancing --slots 2 --min-quota 1
```

The first command verifies pinned source hashes, builds the CPU decomposition and replication reference harnesses and runs normal and `-O` tests. It regenerates this module's evidence only. Timings vary by run. Prior network regressions are separate:

```bash
EVIDENCE=/tmp/quota-prior-regression bash experiments/no-balancing-layer/run.sh
```

## Input and output contract

See each `evidence/*/input.json` and matching `output.json` for complete executable examples.

| Input | Meaning |
|---|---|
| `schema_version` | 1 |
| `npus`, `experts`, `top_k` | EP ranks, logical expert count, unique logical selections per token |
| `main_placement[e]` | Immutable home rank of logical expert e |
| `slots[r]` | Additional physical expert capacity on rank r, 0 through expert count |
| `mapping[t]` | Token t's `source` rank and ordered, unique `experts` list |
| `min_replica_quota` | Positive integer minimum actual assignments on each new replica |
| `beta` | Rational decimal/string >=1; examples use paper setting 1.01 |
| `allow_zero_main` | False keeps at least one assignment on each nonempty main; empty experts stay zero |
| `rounding` | `paper`: ceil(beta * ceil(total/EP)); `code`: ceil(beta * total/EP) |

Λ[source rank, logical expert] counts actual router selections at their **source**, not main placement. Total assignments = tokens × top_k. U is represented by `physical[].quota`, including every fixed main (even empty) and active replicas. Physical IDs reserve each rank's main slots followed by redundant slots; unused IDs can have holes. `weight_source_rank` and `weight_source_physical` always identify the fixed main.

Q is stored as `source_quotas[source][column]`; `q_physical_ids[column]` identifies its physical instance. Summing over that expert's instances recovers Λ[source,e]; summing a column over sources recovers U. `token_mapping` materializes every input selection exactly once and preserves the logical router. `weight_dependencies` describes main-to-replica readiness metadata only: no weights are copied or scheduled.

Metrics include complete initial/final rank loads, used redundant slots, total/local assignments, target and chosen thresholds, imbalance (max/average, zero for empty input), and `target_met`. `cpu_wall_ns` measures host planning only; it is not simulated latency and excludes validation by the independent checker and JSON I/O.

## Algorithm and guarantees

The paper describes threshold search, greedy replication and local-first quota decomposition. This implementation searches integer thresholds between the configured lower target and initial maximum, visiting overloaded ranks by descending excess, their experts by descending demand, and candidate destinations by descending slack. Ties use rank/expert IDs. Transfers are min(excess, destination slack, transferable main quota), respect the floor and consume one free replica slot. A rank never holds two instances of the same logical expert.

A successful probe is a legal witness. Failure is **not an infeasibility proof**. The initial placement is always a legal fallback. The minimum quota makes this greedy oracle potentially nonmonotonic, so binary search may skip better legal witnesses. Neither `chosen_threshold` nor `target_met=false` claims global optimality or mathematical infeasibility. The exhaustive tests deliberately preserve counterexamples.

For fixed U, decomposition fills each instance with as many local-source assignments as possible. It then allocates residual source demand in ascending rank order, proportionally to current remaining capacities, with largest-remainder rounding (host rank tie-break). Capacities are reduced after every source. This guarantees both integer margins exactly and maximizes locality for the given placement and U, without claiming a global locality optimum over placements. Stable input token order consumes these source/expert quotas.

`checker.py` independently reconstructs counts from individual token assignments and checks fixed mains, uniqueness, slots, replica floors, provenance, both Q margins, unchanged router, locality, load metrics and threshold witnesses. Validation uses explicit exceptions and remains active under Python `-O`.

## Differences from the pinned public implementation

The pinned [config.py](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/ultra_ep/config.py) defaults to balance threshold 1.0, minimum replica quota 1024, positive nonempty mains, locality enabled and oracle epsilon 0.01. Our examples use beta 1.01; tiny functional examples explicitly lower the minimum quota to 1 or 2. `paper_floor` retains 1024 and correctly creates no tiny replica.

The pinned placement kernel contains a fast probe with epsilon inflation and a dynamic quota floor before fallback search. This CPU implementation retains the user's configured floor and Algorithm-1-style integer binary search; it does not reproduce the entire GPU kernel. `rounding=code` changes only the lower-bound formula, not that distinction. Arbitrary main placement and per-rank slot budgets generalize the kernel's contiguous, equal main partition and uniform extra capacity. Stable CPU token order also differs from parallel atomic ordinal arrival order.

`reference/` vendors exact MIT-licensed source files. `extract.py` enforces hardcoded SHA-256 values and mechanically extracts the unchanged slow decomposition function, fast scalar branch body, and sparse ordinal lookup from reroute. It removes CUDA attributes through macros and provides a C++ driver; no handwritten substitute reference is used. `manifest.json` records block and file hashes. Four fixtures supply identical source demands, hosts and physical quotas to both reference branches and this implementation. These are decomposition-level tests with supplied U, **not** GPU-generated placement or end-to-end GPU equivalence tests.

Three fixtures agree. In the explicit counterexample, demand `[0,0,1,1]`, hosts `[0,1]`, U `[1,1]`, both upstream scalar branches independently round both remote sources onto host 0, yielding columns `[2,0]`. Our capacity-updated decomposition yields `[1,1]`. This observed CPU scalar discrepancy is intentional here to satisfy exact physical quotas; GPU end-to-end impact has not been established. The exact upstream ordinal lookup is also executed and checked against each reference row.

No CUDA compiler or GPU runtime is available in this environment. The unresolved validation limit is full upstream GPU planner execution and comparison. No TokenPacking, ns3 planner integration, WeightDistribution, relay implementation or multilayer execution is included.


## Replication differential validation (review follow-up)

`reference/extract_replication.py` now extracts the pinned `placement.cu` replication helpers (lines 22–667), search control (954–1284), and X/U materialization (1286–1337). The generated C++ executes the original `warp_build_export_plan`, fast epsilon probe/retries, capacity precheck, four-warp fallback probes, final plan and physical mapping. Search/materialization statements are unchanged. Helper instrumentation only logs oracle entry and effective-floor assignments; all algorithmic statements remain from upstream. Hardcoded source hash verification and `replication-manifest.json` make extraction auditable. This is not a second handwritten version of our planner.

`replication_adapter.cpp` replaces CUDA attributes with empty macros and implements full-mask shuffles, warp barriers and block barriers using 128 C++ threads and C++20 barriers. Host setup supplies a single domain with contiguous equal main partitions, uniform redundant slots, and the original descending-load/ascending-ID ordering. TMA, CUDA launch machinery, GPU scheduling, runtime memory behavior and performance are not modeled. Both register-state oracle and its alternate source branch are compiled; the current nine scenarios exercise G <= 8 (register-state path). Kernel stages 0 and 1 are exercised. Input/outputs are host semantic evidence, not GPU runs.

`tests/test_replication_reference.py` feeds the same compatible inputs to the extracted reference and our planner, checks placement uniqueness, fixed mains, slot budget, expert conservation and threshold witnesses, and compares complete binary X and integer U matrices, replica counts, thresholds and per-rank loads. Our comparison uses `rounding=code` to isolate the upstream lower-bound formula; each case also records our `paper` result. Each fixture saves exact reference stdin/stdout, normalized upstream output, our output and comparison JSON. Parallel fallback trace order is canonicalized only in JSON; raw stdout is retained. No CPU-thread time is presented as planner/GPU latency.

The nine cases cover uniform, skew, extreme-hot, floor-sensitive, nondivisible, fallback, fallback with high floor, zero epsilon and stage zero. Assertions require fast retries, three failed fast probes before fallback, static-floor fallback probes, the epsilon-dependent threshold change, and dynamic-floor output below the configured floor. Critically, upstream lines 424–440 **replace** `effective_min_tokens` with `max(1, ceil(need/feasible_slots))`; they do not take the maximum with the configured floor. Therefore fast-path replicas can be smaller than 1024. The current planner's configured floor remains mandatory. See [replication report](REPLICATION_REPORT.md) and `evidence/replication-results.json` for all observed differences. The earlier four given-U decomposition fixtures remain separate tests.
