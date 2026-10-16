# 10000-C-timing

Status: BLOCKED_NOT_IMPLEMENTED

Not implemented and not run: the original native concurrent multi-segment WQE completion bug blocks shared-Jetty capability. Pair mapping is excluded from this round; no C execution is scheduled or promised.

The following declaration preserves the original comparison intent only; it is not an executable work item or future commitment.

```json
{
  "case_id": "10000-C-timing",
  "block_id": "BC",
  "role": "treatment",
  "case_dir": "${RAW}/10000-C-timing",
  "changed_variable": "same native reverse index plus app pairJetty",
  "fixed_controls": [
    "EP64/E128/k8",
    "exact original inputs",
    "network/compute/WQE/TA/payload semantics",
    "600s/6GiB RSS/7GiB AS/8GiB disk guards"
  ],
  "prediction": "Historical untested hypothesis only: Lower host CPU/wall growth in treatments, subject to correctness and guard gates",
  "reason": "Remove repeated Jetty scans; pair resource reuse additionally removes per-WQE resource creation",
  "falsification_signal": "Parity/invariant failure, guards, or unchanged/worse host cost",
  "metric_checks": [
    "wait4 CPU",
    "monotonic wall",
    "RSS",
    "strict verifier",
    "logical WQE/TA/payload parity"
  ],
  "parallel_group": "exclusive-host",
  "checkpoint_ids": [
    "prior-scale-correctness-and-guards",
    "native-pair-multisegment-capability"
  ],
  "status": "BLOCKED_NOT_IMPLEMENTED",
  "implemented": false,
  "executed": false,
  "blocker": "Not implemented and not run: the original native concurrent multi-segment WQE completion bug blocks shared-Jetty capability. Pair mapping is excluded from this round; no C execution is scheduled or promised.",
  "historical_expected_artifacts": [
    "attempt.json",
    "stages/ns3/resource.json",
    "stages/verify/resource.json",
    "run/summary.json",
    "run/simulator-metrics.json"
  ],
  "expected_artifacts": []
}
```

No C application binary, C run, or C performance result is delivered. See REPORT.md and shared-jetty-probe.md for the measured blocker.
