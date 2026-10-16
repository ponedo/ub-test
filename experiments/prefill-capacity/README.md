# Bounded EP64 prefill capacity validation

Based on `555f2a591d7537b35fb507078dd686a50fb3400e`, with native ns-3-ub pinned to `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`. This measures real host capacity of the accepted scaled SwiGLU/UB application using synthetic gate traces. It does not reproduce real Qwen model bytes or constitute a speedup sweep.

- [Actual report and resource curves](evidence/REPORT.md)
- [Every scale/status and phase measurements](evidence/capacity.csv)
- [Declared controls, predictions and protection policy](experiment-plan.md)
- [Native IDs, allocation and verifier audit](SAFETY-AUDIT.md)
- [Exact stage commands and outcomes](evidence/run-ledger.json)
- [Byte-exact small-case parity](evidence/parity-instrumented.json)
- [Regression evidence](evidence/regressions/), [checks](evidence/checks.json)

Reproduce on the same prepared environment:

```bash
bash experiments/prefill-capacity/run.sh
```

The pinned ns3 checkout/build dependencies must already exist at `/workspace/ns-3-ub` and `/workspace/build-tools`; plotting uses `/workspace/prefill-profile-venv` from the preceding profiling module. The command uses a fresh timestamped raw directory under `/workspace`, preserves previous generated evidence there, rebuilds accepted and instrumented executors, replays small parity, validates original/wire guards, runs the delivered 50K→100K bounded control sequence and selected representative treatment, then all accepted regressions, reports and checks. It replaces this module's generated evidence. `CAPACITY_RAW` may name a fresh absolute directory; occupied directories are refused.

The delivered host stopped expansion at the recorded failure. This reproduction script does **not** automatically change source admission limits on a faster/different host: if both control scales succeed there, larger scales remain explicitly unattempted pending the separately audited cap extension. The full requested matrix remains visible. Source changes, treatment selection and stop policy are not invented after results to manufacture a success.

For the original delivery the same stages were executed individually, with the exact commands retained in resource records. Raw case data are under `/workspace/prefill-capacity-raw/<case>/`; each attempted case is also provided as a lossless `.tar.gz` of synthetic input/output/logs and stage records. `runs/<case>/raw-artifacts.json` gives original file hashes. Regression scripts additionally preserve old-milestone raw evidence at paths recorded by their logs/manifests. No original profiling dataset corpus is copied into this module.

The optional executor `--capacityMetrics=path` writes post-Run counters; default operation is unchanged. No A/T/payload cap was raised, and no protocol field, WQE submission time, TA segment size, relay dependency, planner algorithm or verifier structure was changed. Absence of an OOM does not prove higher scales feasible. A timed-out ns3 process and a timed-out verifier are separate failure states; neither is full success.

Public resource-sample CSV copies normalize CRLF to LF for repository text checks. Values are unchanged; lossless raw archives and original-file manifests retain the original bytes.
