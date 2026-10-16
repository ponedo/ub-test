# Completed run ledger

All 12 planned cases completed; all guards and strict verification PASS; per-scale full run/ hashes equal. No 100K case. Exact commands/timestamps/resources: evidence/run-ledger.json.

|case|ns3 wall s|verifier wall s|result|
|---|---:|---:|---|
|5000-baseline|4.512|1.508|success|
|5000-perf|4.515|1.508|success|
|5000-timed|5.015|1.508|success|
|10000-baseline|14.549|3.515|success|
|10000-perf|14.052|3.011|success|
|10000-timed|14.546|3.013|success|
|20000-baseline|50.672|8.536|success|
|20000-perf|50.187|8.531|success|
|20000-timed|55.190|8.532|success|
|50000-baseline|313.117|53.709|success|
|50000-perf|309.160|51.705|success|
|50000-timed|328.660|52.705|success|

Checkpoints: 5K,10K,20K,50K passed; automatic continuation followed authorized plan. All predictions were registered before first run; lifecycle dominance was not supported, while superlinear lookup-path cost was supported (see conclusions.md). The build-time class-name error was fixed before simulations and retained as build-attempt1.txt. No runtime retry or skipped case.

Original regression chain plus timer-clone relay suite and normal/-O negative tests completed; see evidence/regression-guard and raw archives.
