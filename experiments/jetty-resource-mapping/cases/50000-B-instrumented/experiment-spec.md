# 50000-B-instrumented

{
  "case_id": "50000-B-instrumented",
  "block_id": "AB",
  "role": "treatment",
  "case_dir": "${RAW}/50000-B-instrumented",
  "changed_variable": "native reverse index only",
  "fixed_controls": [
    "EP64/E128/k8",
    "exact original inputs",
    "network/compute/WQE/TA/payload semantics",
    "600s/6GiB RSS/7GiB AS/8GiB disk guards"
  ],
  "prediction": "Lower host CPU/wall growth in treatments, subject to correctness and guard gates",
  "reason": "Remove repeated Jetty scans; pair resource reuse additionally removes per-WQE resource creation",
  "falsification_signal": "Parity/invariant failure, guards, or unchanged/worse host cost",
  "metric_checks": [
    "wait4 CPU",
    "monotonic wall",
    "RSS",
    "strict verifier",
    "398-file parity",
    "exact instrumented counters",
    "opt-in inclusive/exclusive thread CPU timers",
    "same-arm timing 398-file parity"
  ],
  "expected_artifacts": [
    "attempt.json",
    "stages/ns3/resource.json",
    "stages/verify/resource.json",
    "run/summary.json",
    "run/simulator-metrics.json",
    "timing.tsv"
  ],
  "parallel_group": "exclusive-host",
  "checkpoint_ids": [
    "prior-scale-correctness-and-guards"
  ],
  "status": "optional-conditional"
}

Optional separately instrumented run. Requires successful same-arm uninstrumented timing reference. Retain separate frozen ELF and all failed attempts.
