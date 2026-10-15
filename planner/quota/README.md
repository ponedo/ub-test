# CPU UltraEP Planner: two explicit modes

Default **`upstream-compatible`** executes the extracted replication and quota-decomposition logic of [Dots-Infra/UltraEP 94cab099b44fffa99a82fea99e7c12d89cf65e4f](https://github.com/Dots-Infra/UltraEP/tree/94cab099b44fffa99a82fea99e7c12d89cf65e4f). **`strict-floor`** preserves the previous independent Algorithm-1-style planner and its configured replica floor. This branch is based on `132763fe8ccbe4dc57e0ffcbcfa3f4d3b1d77fc7`.

The default is a CPU semantic adaptation, not a GPU runtime or timing model. It reuses public source rather than maintaining a second handwritten replication algorithm. The previous [report](REPORT.md) and [replication investigation](REPLICATION_REPORT.md) describe the earlier strict-floor milestone; [COMPATIBILITY_REPORT.md](COMPATIBILITY_REPORT.md) describes the current implementation.

## Run

Requires Python 3.10+, g++ with C++20 and pthreads. No pip packages, GPU or network are required.

```bash
bash planner/quota/run.sh
python3 planner/quota/planner.py planner/quota/evidence/compatible/extreme_hot/input.json /tmp/compatible.json
python3 planner/quota/planner.py planner/quota/evidence/compatible/extreme_hot/input.json /tmp/strict.json --mode strict-floor
```

The CLI builds the pinned CPU engines on demand, with source and binary hash checks. `run.sh` builds both engines and runs all CPU suites in normal and optimized Python modes. It regenerates this module's evidence. Prior network regressions are separate and write to a fresh directory:

```bash
EVIDENCE=/tmp/upstream-compatible-network-regression bash experiments/no-balancing-layer/run.sh
```

## Input contract

Existing JSON field names are retained. Every saved `evidence/compatible/<case>/input.json` is executable.

| Field | Meaning/default |
|---|---|
| `schema_version` | 1 |
| `mode` | `upstream-compatible` by default; `strict-floor` explicitly selects the legacy implementation |
| `npus`, `experts`, `top_k` | EP ranks, logical expert count, unique logical selections per token |
| `main_placement[e]` | Fixed main rank; never rearranged implicitly |
| `slots[r]` | Redundant physical expert budget |
| `mapping[t]` | Token t's source rank and ordered unique logical `experts` list |
| `beta` | Decimal number/string; defaults to pinned public config's 1.0 |
| `min_replica_quota` | Positive integer, default 1024; fast upstream mode may replace it with a lower dynamic floor |
| `allow_zero_main` | False by default; otherwise zero quota on a nonempty main is allowed |
| `oracle_epsilon` | Decimal, default 0.01; used by upstream fast probes |
| `kernel_stage` | Upstream 0 or 1, default 1 |
| `locality_aware` | True by default; upstream also supports False; strict mode retains legacy True behavior |
| `rounding` | Legacy paper/code setting. Upstream always executes its original float32 arithmetic; a supplied legacy setting is explicitly recorded as overridden in output metadata |
| `reroute_mode` | Only `sparse-quota` is supported; CPU ordinals follow input order |

Upstream-compatible inputs must describe **one EP domain**, G<=72, E=G*M<=512 with M>=1, contiguous equal main partitions (`main_placement[e]=e//M`), uniform slots S and G*S<=512. Unsupported layouts are rejected, never silently rerouted to strict mode. Slots can exceed E if the public total-slot bound allows them. The wrapper caps beta/epsilon at 100 and total assignments at two million. Strict mode retains arbitrary main placement and per-rank slots (each <=E), NPU<=256, E<=4096. The NoBalancing adapter copies the original layout; incompatible layouts require an explicit `--mode strict-floor`, not automatic rearrangement.

## Execution and output contract

Λ[source rank, logical expert] counts the actual routing selections at their source. `physical` contains fixed mains, active replicas, their original slot/physical IDs and quotas U. Every main is present, even empty. Weight provenance always points to that expert's fixed main; `weight_dependencies` is readiness metadata only.

`source_quotas[source][column]` is Q, with IDs in `q_physical_ids`. Every source/expert row sum equals Λ, every physical column equals U, and `token_mapping` realizes each input selection exactly once. Logical experts and top-k order are unchanged. Original main-then-export instance order is preserved in `ordinal_physical_order` for public sparse-quota ordinal lookup, even though physical output columns are sorted by ID. GPU atomic arrival order is unavailable; per-token physical identities across GPU schedules are not claimed identical.

`metrics` reports complete initial/final rank loads, slot usage, total/local assignments, target/chosen thresholds, path (`fast`, `fallback`, `bypass`), imbalance and number of corrected assignments. The lower target does not include fast epsilon inflation; `target_met=false` need not indicate an incompatible result. `cpu_wall_ns` is observed host wall time including CPU engine startup, and initial compilation when necessary. It is not GPU performance or simulated planning latency.

With G=1 or S=0, public replication bypasses search and its search threshold is undefined. Raw output uses `threshold:null`; the CPU `chosen_threshold` convention is actual maximum final load. Its `target_threshold` is a separately computed float32 lower-bound diagnostic. Neither field is presented as an upstream search result on bypass.

## Pinned semantics and CPU adaptation

The engine executes original fast epsilon probes/retries, dynamic floor, static-floor fallback and four-warp search, fixed-main retention, export order, physical slot allocation, and float32/ceilf threshold arithmetic. `replication-manifest.json` records source/block hashes and adapter changes. `extract_replication.py` refuses a changed source snapshot. The exact source license is retained in `reference/LICENSE.UltraEP`.

128 CPU threads represent the CUDA lanes. Full-mask shuffles and synchronization use C++20 barriers. Host initialization supplies the original descending-load/ascending-ID ordering. The G>64 shared-state branch needs one extra CPU barrier after reading q and before lane 0 updates slack, to preserve the original warp read-before-write ordering. Without that boundary, independently scheduled CPU threads can disagree on q and hang. This is an explicit semantic synchronization adaptation, not a quota formula change or a claim about CUDA runtime correctness. Tests exercise rank 32/63 and high occupancy bits at 64/71, plus shared-state fallback. No TMA, CUDA scheduling, weights or packet transport is modeled.

The dynamic floor is a replacement: `max(1, ceil(need/feasible_slots))`, not max(configured floor, dynamic floor). Thus the accepted extreme-hot fixture produces seven replicas and max load 1046, including a quota-870 replica with configured floor 1024. Strict mode intentionally retains three replicas and max 2048 for that input. Both remain heuristics; no global optimality or infeasibility proof is claimed.

## Explicit conservation repair

Upstream decomposition's independent per-source integer rounding can preserve every source row but miss physical column quotas. The exact raw source stdout, original Q and all inputs are preserved under `output.upstream`. No replacement is made when both margins already match.

If only column margins mismatch, the wrapper moves assignments from surplus columns to deficit columns within the same source/expert row. Local fills are locked when locality is enabled. The deterministic ordering is original instance order, then source rank. It changes neither placement nor U, never fabricates tokens, and moves exactly `sum(max(raw_column-U,0))` assignments, the minimum required to repair the column imbalance. Each move, trigger, raw/corrected matrix and affected physical IDs is recorded in `quota_repairs`; output compatibility is labeled `integer-conservation-repaired`. Unexpected source-margin failure or fast/slow disagreement causes an explicit error rather than an undocumented fallback.

Example: raw rows `[1,0]`, `[1,0]` for two remote sources and U `[1,1]` become `[0,1]`, `[1,0]`; exactly one assignment moves. This intentionally differs from both the raw public rounding and the old strict mode's sequential-capacity rounding. `checker.py` independently reconstructs token counts, validates all applicable constraints, replays the repair ledger, checks minimal change and ordinal mapping. Checks stay enabled under Python `-O`.

## Validation independence and limits

Accepted prior-commit goldens freeze the original nine source results. New integration comparisons separately run the extracted executable on identical inputs, but share the execution engine and are **not** called an independent second algorithm. Independent checks include analytical large-rank witnesses, token-level invariant reconstruction, small exhaustive allocation searches and exhaustive minimum-distance repair checks. Reports classify exact results, explicit integer corrections, placement differences and unsupported/unverified behavior.

GPU end-to-end execution, GPU token scheduling and multiple domains remain unverified/unsupported. This module does not integrate the planner into ns3 or change Dispatch, Combine, compute, weights, relay or packing.

## Numeric safety support boundary

Compatible mode rejects inputs whose conservative bounds could overflow any upstream signed-int aggregate, even if a single threshold fits int32. For total assignments T and ranks G, a rational guard H=(1+2^-20)^4 bounds float32 conversions/rounding: L=ceil((T/G)*beta*H), F=ceil(L*(1+epsilon)*H), U=max(T,L,F). Search requires G*U<=INT_MAX, max(T,L)+99<=INT_MAX, and U+max(1,ceil(max(T,L)/100))<=INT_MAX. These are admission checks only; the original float32 algorithm is unchanged. Conservative rejection does not assert that every rejected workload would overflow. Bypass inputs check their lower-bound conversion but do not require an unused slack reduction bound.

For G=72, beta=epsilon=100, this admits T=212620 and rejects T=212621. The reported T=300000 case is rejected: float32 fast threshold 42083368 fits int32, but aggregate slack 3029702496 does not. Ordinary beta=1.01/epsilon=0.01 retains the full two-million-assignment domain. `tests/test_numeric_bounds.py` checks boundaries and arithmetic without constructing large token traces or executing unsafe C++ cases. Detailed aggregate audit is in COMPATIBILITY_REPORT.md.
