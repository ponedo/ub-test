# Validation report

Executed CPU suite in normal and optimized Python modes: 10 saved scenarios, 250 deterministic random cases (including top-k > 1), 80 independent exhaustive comparisons, 5 corrupted-output checks, 6 invalid inputs, 2 threshold-rounding modes, and 4 compiled fixed-source fixtures. All pass. An explicit `[true,false,true]` threshold witness regression verifies nonmonotonicity.

| Scenario | Initial max | Final max | Target | Target met | Replica slots used | CPU wall ms |
|---|---:|---:|---:|---|---:|---:|
| uniform | 16 | 16 | 17 | True | 0 | 0.287 |
| skew | 61 | 21 | 18 | False | 3 | 0.315 |
| extreme_hot | 8192 | 2048 | 1035 | False | 3 | 10.076 |
| slots_insufficient | 31 | 31 | 9 | False | 0 | 0.220 |
| empty | 0 | 0 | 0 | True | 0 | 0.111 |
| nondivisible | 17 | 10 | 10 | True | 1 | 0.170 |
| zero_main_allowed | 2 | 1 | 1 | True | 1 | 0.173 |
| positive_main | 2 | 2 | 1 | False | 0 | 0.078 |
| paper_floor | 20 | 20 | 6 | False | 0 | 0.128 |
| n64_adapter | 9 | 5 | 5 | True | 11 | 39.671 |

CPU times are single observed host measurements, not GPU performance, simulated planning latency, or a speedup benchmark. Full load vectors, slot usage, U, Q and every token assignment are in the saved outputs.

The independent enumerator found 4 optimality gaps in 80 small cases (seeds 17, 61, 67, 70). Each exact input and optimum is retained in `evidence/test-results.json`. For seed 67, the legal optimum is 2 but binary search returns 4: the greedy oracle succeeds at 2, fails at 3 because the required transfer is below the floor, and succeeds at 4. No failure is presented as a mathematical infeasibility result.

The extreme-hot case is also deliberately reported without hiding its limitation: 8192 assignments at one main become four loads of 2048, despite a legal eight-way split of 1024 fitting the slots and minimum quota. The target 1035 is missed by this fixed-floor greedy search. This is a legal best-effort witness, not a claim to reproduce upstream fast/dynamic-floor quality.

Three fixed-source decomposition fixtures match. The fourth demonstrates column-margin drift from independent upstream rounding; our output conserves both margins. See README and the exact matrices in test-results.json. CUDA/GPU end-to-end comparison remains unavailable.

Prior PoC and NoBalancing full regressions passed, including 16 normal and 16 optimized NoBalancing tests. `evidence/prior-regression/` contains console output, run ledger, tool versions and SHA-256 inventory of raw traces at `/workspace/quota-network-regression`. Existing tracked source and evidence had no changes before this module was staged. The pinned ns3 and tools commits are in the captured tool versions.

Reproduce CPU checks: `bash planner/quota/run.sh`. Reproduce prior regression in a separate output directory using the README command. No network-model behavior was changed.

Replication follow-up: the pinned solver itself now has 9 extracted-source CPU differential scenarios covering fast probes, epsilon, dynamic floor and fallback. See [REPLICATION_REPORT.md](REPLICATION_REPORT.md). GPU execution is still unavailable.
