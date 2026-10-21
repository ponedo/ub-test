# Execution ledger

UTC2026-10-21. Parent accepted commit3c2275eafea79426a441c819c8b65268492ff08e. Independent branch experiments/cloudmatrix-bandwidth-dot-20261021.

- Native configure/full build: PASS; full build653.38s. This does not claim all native test-runner suites executed.
- Accepted executors and test-only link probe: PASS.
- Small stage:32paired cases+3fault smokes PASS;16old100latency/output-hash comparisons exact.
- Model unit oracle:16positive+6negative PASS.
- Guard control tests: initial timeout descendant-cleanup bug found and corrected before simulations;4finalcleanup+8optimization rejection tests PASS.
- Baseline reuse:4exact input/config/assignment/semanticPlanner hash matches,3406source+13binary/library identities frozen.
- No true simulation guard termination or correctness failure.
- Negative result retained: increasing bandwidth reduces durations, but does not make replication win; MC versusChunk ordering reverses. No protocol/model changes or extra196GB/s runs were used to chase a favorable result.

| Strategy | Start UTC | Wall seconds | Result |
|---|---|---:|---|
| no-balancing | 2026-10-21T02:28:51.278003+00:00 | 70.206470 | PASS: simulator,postflight,independent network,independent compute |
| direct | 2026-10-21T02:28:52.266582+00:00 | 378.127825 | PASS: simulator,postflight,independent network,independent compute |
| chunk-streaming | 2026-10-21T02:30:03.510044+00:00 | 688.265853 | PASS: simulator,postflight,independent network,independent compute |
| multicast-v2 | 2026-10-21T02:35:14.726475+00:00 | 484.440358 | PASS: simulator,postflight,independent network,independent compute |

Exact reproduction commands: command-manifest.yaml,commands.sh,reproduce.sh. Actual resource intervals/concurrent peers: results/resources.csv and results/host-pressure-summary.json. Raw routing/per-token/pair-state remain private.

Publication and remote verification are recorded separately in REMOTE-VERIFICATION.json after completion.

Public evidence was narrowed to aggregate metrics, requested critical Expert readiness, and resource totals. Detailed per-node/per-expert state and admission logs remain in the private verified run directory; they are not included in the delivery branch.
