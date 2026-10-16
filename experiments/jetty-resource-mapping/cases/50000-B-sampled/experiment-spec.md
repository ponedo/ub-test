# 50000-B-sampled

Declared case: {
  "case_id": "50000-B-sampled",
  "block_id": "AB",
  "role": "treatment",
  "case_dir": "${RAW}/50000-B-sampled",
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
    "398-file parity"
  ],
  "expected_artifacts": [
    "attempt.json",
    "stages/ns3/resource.json",
    "stages/verify/resource.json",
    "run/summary.json",
    "run/simulator-metrics.json",
    "perf.data"
  ],
  "parallel_group": "exclusive-host",
  "checkpoint_ids": [
    "prior-scale-correctness-and-guards"
  ],
  "status": "planned"
}

Execution is pending. Exact argv is in command-manifest.yaml. The authoritative attempt and append-only lifecycle ledger are under the explicit raw root. Conditional cases require lead approval and all named gates.
