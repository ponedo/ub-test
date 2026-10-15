# Upstream-compatible CPU Planner — validation report

Base: `132763fe8ccbe4dc57e0ffcbcfa3f4d3b1d77fc7`. Public source: `94cab099b44fffa99a82fea99e7c12d89cf65e4f`. Default mode now executes pinned replication and decomposition source; `strict-floor` retains the previously accepted implementation.

Normal and optimized Python modes passed: 26 typical scenarios, 9 accepted prior-commit source goldens, 60 random compatible inputs (including top-k > 1), 20 independent tiny allocation enumerations, 63 exhaustive minimum-change transportation repairs, and 11 rejected unsupported inputs. The legacy strict suite also passes 10 scenarios, 250 random cases, 80 exhaustive comparisons, 5 corrupted-output tests, 6 invalid inputs and 4 decomposition fixtures. Its 4 optimality gaps and nonmonotonic oracle regression remain.

| Case | Path | Compatible max | Strict max | Compatible replicas | Strict replicas | Repaired assignments |
|---|---|---:|---:|---:|---:|---:|
| uniform | fast | 16 | 16 | 0 | 0 | 0 |
| skew | fast | 20 | 20 | 2 | 2 | 0 |
| extreme_hot | fast | 1046 | 2048 | 7 | 3 | 0 |
| floor_sensitive | fast | 7 | 20 | 2 | 0 | 0 |
| nondivisible | fast | 10 | 9 | 2 | 2 | 0 |
| fallback | fallback | 503 | 503 | 3 | 3 | 0 |
| fallback_floor | fallback | 800 | 800 | 0 | 0 | 0 |
| epsilon_zero | fast | 1035 | 2048 | 7 | 3 | 0 |
| stage_zero | fallback | 503 | 503 | 3 | 3 | 0 |
| shared_fallback | fallback | 4 | 4 | 4 | 4 | 3 |
| empty | fast | 0 | 0 | 0 | 0 | 0 |
| slots_zero | bypass | 19 | 19 | 0 | 0 | 0 |
| extra_unused_slots | fast | 3 | unsupported | 0 | unsupported | 0 |
| one_rank | bypass | 5 | 5 | 0 | 0 | 0 |
| multiple_slots | fallback | 206 | 206 | 6 | 6 | 0 |
| float32_boundary | fast | 1 | 2 | 3 | 1 | 0 |
| zero_main | fast | 1 | 1 | 1 | 1 | 0 |
| positive_main | fast | 2 | 2 | 0 | 0 | 0 |
| no_locality | fast | 5 | 4 | 2 | 2 | 1 |
| margin_counterexample | fast | 1 | 1 | 1 | 1 | 1 |
| main_last_order | fast | 1 | 1 | 1 | 1 | 1 |
| g33 | fast | 4 | 132 | 32 | 0 | 0 |
| g64 | fast | 4 | 256 | 63 | 0 | 0 |
| g65 | fast | 4 | 260 | 64 | 0 | 0 |
| g72 | fast | 4 | 288 | 71 | 0 | 0 |
| e512 | fast | 4 | 256 | 63 | 0 | 0 |

The strict comparison uses the same input parameters; its legacy locality policy is True. The `extra_unused_slots` case is public-compatible but exceeds the legacy slots<=E input bound, so the strict side is explicitly unsupported rather than silently changed.

## Classification

- **Completely matching placement and source quota:** 22/26 typical scenarios. Comparison includes every physical ID/slot, logical expert, quota, final rank load, replica count, search threshold where defined, path, probes and dynamic-floor trace. Token IDs still use the documented CPU ordinal convention.
- **Integer rounding correction:** 4/26 (`shared_fallback`, `no_locality`, `margin_counterexample`, `main_last_order`). Raw source rows conserve assignments but physical columns drift. Only minimum necessary source-preserving moves are applied. X, U, expert choices and local fills remain unchanged. Raw stdout, raw Q, corrected Q, moved counts and exact move ledgers are saved. Random cases trigger correction in 12/60 inputs.
- **Substantial placement differences from the pinned source:** zero among tested compatible inputs. Differences between strict and compatible modes are intentional and shown in the table, not counted as upstream mismatches.
- **Not aligned or not supported:** GPU atomic token arrival order and GPU runtime behavior; multiple EP domains; noncontiguous/nonuniform main placement or nonuniform slots. Unsupported layout/protocol inputs fail explicitly. No silent strict-mode fallback exists.

## Acceptance details

- Extreme Hot with beta=1.01, epsilon=0.01 and configured minimum 1024 now has **7 replicas and max 1046**, including the public quota-870 replica. Strict mode remains 3 replicas/max 2048. Default beta when omitted is public config 1.0; the named fixture explicitly retains beta=1.01.
- Public dynamic floor directly replaces the configured floor. Static fallback still uses the configured minimum. The original C++ float/ceilf expressions run unchanged; a decimal boundary test (`beta=1.00000001`, same epsilon) yields threshold 1, where an exact rational implementation would incorrectly round up.
- G=33/64 tests reach physical ranks 32/63; G=65/72 reach 64/71, exercising shared-state/high-bit occupancy and slow quota decomposition with more than 8 instances. E=512, two used slots per rank, and an allowed slots>E input are covered. A G=65 fixture explicitly reaches static-floor fallback.
- G=1 or zero slots bypass search. Raw threshold is null because upstream does not define it. CPU chosen threshold is actual max load; lower-bound diagnostics are not claimed to be upstream search results.
- Stable CPU input order supplies per-(source,expert) ordinals to public sparse cumulative-quota mapping. Main-then-export instance order is preserved, including when the main rank sorts after replicas. Dense/interleaved reroute is explicitly unsupported.

## Adaptation and validation independence

The production engine reuses mechanically extracted public helpers, fast/fallback control and physical quota materialization. CPU barriers implement CUDA lane collectives; the G>64 shared q read adds one barrier before lane 0 writes slack to preserve warp read-before-write semantics under independent CPU scheduling. Source decisions are unchanged. Hash manifests record all extraction and adaptation details. The nine accepted goldens come from the previous committed evidence, not this new implementation. Analytical large-rank witnesses, token-level reconstruction, independent allocation enumeration and repair-distance enumeration add checks independent of the shared engine. Separately rerunning the same extracted executable is described only as integration validation.

The raw [1,0],[1,0] remote-source counterexample with U=[1,1] is corrected to [0,1],[1,0]. Exactly one assignment moves; zero would leave the column deficit. In general the moved count equals the sum of positive raw column excesses, which is the lower bound; the checker verifies the ledger and L1 distance. Unexpected row failure or fast/slow disagreement raises an error. No fake token or quota is introduced.

## Regressions and artifacts

NoBalancing and Chunk Relay full regressions passed in `/workspace/upstream-compatible-network-regression`, including 16 normal and 16 optimized NoBalancing tests. This branch does not change those sources or their original evidence. `evidence/compatible-regression/` contains logs, run ledger, tool versions and SHA-256 inventory of raw traces.

For every typical case, `evidence/compatible/<case>/` contains the shared input, both mode outputs (or explicit strict unsupported status), comparison summary and direct-source stdout. The compatible output embeds exact replication/decomposition stdin/stdout, original physical plan, raw Q and repair ledger. `evidence/compatible/results.json` contains random inputs, full load metrics and exhaustive results. `tests/upstream-goldens.json` freezes accepted old evidence. Build and normal/-O test logs are in `evidence/`.

Reproduce with `bash planner/quota/run.sh`; run either mode via the CLI examples in README. Observed `cpu_wall_ns` includes host execution/startup and possible first compilation; no simulated planning latency is claimed. GPU validation remains unavailable. No ns3 integration, Dispatch/Combine/compute modification, weights, relay, packing or Phase 2 was performed.
