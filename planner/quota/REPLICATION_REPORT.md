# Replication differential report

Pinned source: [Dots-Infra/UltraEP 94cab099b44fffa99a82fea99e7c12d89cf65e4f](https://github.com/Dots-Infra/UltraEP/blob/94cab099b44fffa99a82fea99e7c12d89cf65e4f/csrc/kernels/placement.cu). CPU semantic adaptation, not a GPU run. No planner decision code was changed for this follow-up.

Normal and `python -O` execution pass all 9 replication scenarios. The original 10 scenarios, 250 random cases, 80 exhaustive comparisons, 4 decomposition fixtures and negative tests also pass. The original nonmonotonic counterexample and 4 optimality gaps remain.

| Case | Upstream / ours threshold | Upstream / ours max load | Upstream / ours replicas | X / U equal | Upstream path |
|---|---|---|---|---|---|
| uniform | 18 / 16 | 16 / 16 | 0 / 0 | True / True | fast |
| skew | 20 / 20 | 20 / 20 | 2 / 2 | True / True | fast |
| extreme_hot | 1046 / 2048 | 1046 / 2048 | 7 / 3 | False / False | fast |
| floor_sensitive | 7 / 20 | 7 / 20 | 2 / 0 | False / False | fast |
| nondivisible | 10 / 9 | 10 / 9 | 2 / 2 | True / False | fast |
| fallback | 503 / 503 | 503 / 503 | 3 / 3 | True / True | fallback |
| fallback_floor | 800 / 800 | 800 / 800 | 0 / 0 | True / True | fallback |
| epsilon_zero | 1035 / 2048 | 1035 / 2048 | 7 / 3 | False / False | fast |
| stage_zero | 503 / 503 | 503 / 503 | 3 / 3 | True / True | fallback |

Both sides use beta=1.01, identical actual token selections, contiguous equal-size main placement, uniform one-slot redundant budgets and the same configured minimum quota. Our principal comparison selects `rounding=code`; `comparison.json` also reports the paper-bound variant. Main retention is positive for nonempty experts on both sides.

Observed explanations:

- Uniform: X/U are identical and no replica is needed. The upstream fast threshold is 18 after lower bound 17 and epsilon inflation; actual max remains 16. Our chosen threshold is the initial max 16. A threshold difference alone does not imply different placement.
- Skew: first fast threshold 19 fails; retry at 20 succeeds. Both implementations produce the same X/U and max 20.
- Extreme hot: upstream threshold 1046 (epsilon=0.01), seven replicas and max 1046; the final replica has quota 870, below the configured 1024. With epsilon=0, threshold becomes 1035 and the small replica is 947. Our strict-floor best effort keeps three replicas, max 2048, with no floor relaxation.
- Floor-sensitive: for expert loads [20,0,0,0] and configured floor 1024, upstream fast output uses quotas 7 and 6 on two replicas, main quota 7. Our planner creates no replica and retains max 20. The log records the original effective-floor replacement, not a max with 1024.
- Nondivisible: same placement X but different U; upstream max/threshold 10 after epsilon, ours 9 with code lower bound. Our paper-bound result is recorded separately.
- Fallback: eight experts of load 100 at rank 0, 24 empty experts, four ranks and one extra slot per rank. Fast thresholds 205,213,221 fail. The original static-floor precheck and multi-probe fallback execute, producing max/threshold 503 and three replicas, matching ours. With configured floor 1024, both retain max 800 and zero replicas. Stage 0 produces the same fallback X/U as stage 1.

The reference is independently rooted in extracted public source: original helper decisions, probe controller, physical slot assignment and quota materialization execute in generated C++. A host adapter supplies input arrays and equivalent sorting, and substitutes CPU barriers/shuffles for CUDA collectives. Three logging insertion sites expose oracle calls and dynamic floors without changing decisions. `replication-manifest.json` hashes the pinned source, extracted blocks and adapter; extraction fails if the source hash differs.

Each `evidence/replication/<case>/` holds shared input, reference stdin and raw stdout, upstream and our physical outputs, full X/U matrices, rank loads, replica counts, probe traces and dynamic-floor values. Parallel fallback logging order is nondeterministic; normalized JSON sorts oracle records while raw stdout preserves observation order. The tests verify conservation and all applicable placement constraints independently. They intentionally do not require upstream fast output to honor the configured floor because the pinned code replaces it.

Coverage boundary: a single EP domain, G<=8 register-state cases, kernel stages 0/1, float arithmetic as compiled from upstream. G>64, GPU collectives/runtime and end-to-end execution remain unvalidated. No packing, ns3 integration or weight distribution was added. The current planner still enforces the user floor, uses legal best effort, and makes no global-optimality/infeasibility claim.

Reproduce: `bash planner/quota/run.sh`. Requires Python 3.10+, g++ C++20 and pthreads; no GPU or network.
