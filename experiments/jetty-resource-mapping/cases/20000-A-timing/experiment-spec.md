# 20000-A-timing

Declared case: {
  "case_id": "20000-A-timing",
  "block_id": "AB",
  "role": "control",
  "case_dir": "${RAW}/20000-A-timing",
  "changed_variable": "original native per-WQE control",
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
    "run/simulator-metrics.json"
  ],
  "parallel_group": "exclusive-host",
  "checkpoint_ids": [
    "prior-scale-correctness-and-guards"
  ],
  "status": "planned"
}

Execution is pending. Exact argv is in command-manifest.yaml. The authoritative attempt and append-only lifecycle ledger are under the explicit raw root. Conditional cases require lead approval and all named gates.
