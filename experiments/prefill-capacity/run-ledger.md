# Capacity run ledger

Durable exact commands/resources: [evidence/run-ledger.json](evidence/run-ledger.json).

| Case | Status | Reason |
|---|---|---|
| no-balancing-50000 | success |  |
| no-balancing-100000 | failed | wall_guard |
| no-balancing-200000 | not_attempted | Sequential expansion stopped after no-balancing-100000 ns3: wall_guard |
| no-balancing-500000 | not_attempted | Sequential expansion stopped after no-balancing-100000 ns3: wall_guard |
| no-balancing-1000000 | not_attempted | 20-bit wire Jetty ID preflight rejects approximately 2M global task IDs; original T cap also exceeded; no remapping or protocol change authorized |
| ultraep-50000 | success |  |
| ultraep-100000 | not_selected | Representative treatment rule selects first/largest fully verified NoBalance scale only; no full strategy matrix |
| ultraep-200000 | not_selected | Representative treatment rule selects first/largest fully verified NoBalance scale only; no full strategy matrix |
| ultraep-500000 | not_selected | Representative treatment rule selects first/largest fully verified NoBalance scale only; no full strategy matrix |
| ultraep-1000000 | not_attempted | 20-bit wire Jetty ID preflight rejects approximately 2M global task IDs; original T cap also exceeded; no remapping or protocol change authorized |
