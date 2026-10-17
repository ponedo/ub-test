# Relay dependency indexes

Four equivalent lookup optimizations, preserving original ordered membership and all validation checks. See `REPORT.md` for completed measurements and limits and `experiment-plan.md` for frozen scope/guards.

## Independent switches

- Preparation: `RELAY_DEPENDENCY_MODE=scan|indexed` (or adapter `dependency_mode` argument).
- Independent Python preflight: `--dependency-mode scan|indexed`.
- C++ Read: `--dependencyMode=scan|index`.
- Online immutable membership: `--onlineMembershipMode=scan|index`.

All default to indexed lookup. No input/model/Planner/native changes. A scan choice reproduces old candidate membership and order; output schemas are unchanged. Index keys derive directly from the old filters: main-origin group `(expert, offset, bytes)` and receiver physical ID. Append-only ordered vectors retain edge/task order. Distinct experts, offsets and lengths cannot collide.

## Reproduce on original host

Use the accepted baseline sibling `qwen-chunk-profile`, unchanged native sibling `wqe-completion-native`, and exact original inputs in `qwen-model-size-raw`. Do not run expensive commands concurrently. All stage runners import the unchanged `wqe-completion-fix/guard.py`, with wall300s, treeRSS6GiB, address space7GiB, free disk8GiB and other original guards.

```sh
H=relay-dependency-index/experiments/relay-dependency-index
python3 "$H/build.py"
python3 "$H/check-parity.py" --name unique-fresh-parity
python3 "$H/run-qwen.py" --name unique-index-index
python3 "$H/run-qwen.py" --name unique-index-scan --online-mode scan
python3 "$H/run-qwen.py" --name unique-scan-index --dependency-mode scan
python3 "$H/run-qwen.py" --name unique-scan-scan --dependency-mode scan --online-mode scan
```

Output destinations must be fresh. Original inputs are read-only. Generated diagnostic profiling is separate from production; see instrumentation notes. Compact exact-output proofs are committed; large logs, payload and profiles remain host-local with SHA256 manifests.

## Evidence map

- `python-timings.csv`, `python-statements.csv`, `python-profile-top.csv`: separate fresh preparation and independent preflight profiles.
- `cpp-read-timings.csv`, `cpp-read-profile.json`: complete same-binary standalone Read scan/index, export excluded from Read CPU.
- `runtime-results.csv`, `runtime-evidence/`: actual production/timed completed results and explicitly partial scan control.
- `four-contributions.csv`, `dependency-index-cpu.svg`: four complete target-scope CPU comparisons; partial whole-process status remains explicit.
- `runtime-self-cpu.csv`, `runtime-self-cpu.svg`: disjoint self scopes, not summed inclusive timers.
- `parity-final.json`, `parity-instrumented.json`, `regression-results.json`, `INDEPENDENT_REVIEW.md`: correctness and original-suite coverage/limits.
- `DELIVERY_MANIFEST.json`, `local-raw-manifest.json`: compact delivery and retained host-local raw hashes.

The final controlled online scan process stopped during FinalAudit at the unchanged wall guard. Its targeted online checks had completed, but it has no successful whole-run validation or LayerLatency point. Use the complete-scope comparison described in REPORT.md; never interpret a cutoff ratio as full-run speedup.
