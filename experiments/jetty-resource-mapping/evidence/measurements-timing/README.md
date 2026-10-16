# PARTIAL measured snapshot

Generated: 2026-10-16T16:27:01.804227+00:00

Selected curve scales: 5000, 10000, 20000, 50000. See resources.csv for all declared cases and explicit not_run/running/failed states.

- No benchmarks launched. Reads only saved small metadata and timing TSV files.
- Byte parity uses recorded per-file SHA256 from completed guarded runs; raw payloads/events were not rehashed during this concurrent-safe summary.
- C not run is missing evidence, not a zero-cost result.
- Single-trial measurements are descriptive; no significance claim.
- Jetty create calls measured only in instrumented runs; no resource count inferred from WQE count.
- Curves include successful selected sizes only. Entire declared matrix, failures, and running attempts remain in CSV/JSON.

Artifacts: resources.csv, counters-and-timers.csv, parity.csv, curves-partial.svg, summary.json. Exact invocation and source hashes are in summary.json. This snapshot never overwrites earlier evidence.
