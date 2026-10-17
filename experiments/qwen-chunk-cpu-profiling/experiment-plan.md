# Qwen256 Chunk Relay CPU diagnosis

Diagnosis only, based on accepted application tree `0efaad701fc10655f045d15785949b0d198722a7` (local commit `6f837d47d8f96508ed53f3602d887f95397c4fae`, accepted remote `2a83d257ba13268937e605395ec6f70566dd8ef8`). Native tree `c27d1faef570e6da9900a71aa0a37180a58dfba8`, commit `2fde39d02920e639f5b200d0c5262a517326deb8`.

## Claim and alternatives

Find the measured CPU cost responsible for the accepted Chunk Streaming Relay 300-second timeout, independently of preparation/preflight costs. Candidate explanations include initialization dependency scans, online Audit scans, payload validation/copying, WQE/TA/packet processing, and event machinery. Static loop complexity is not a CPU percentage. Sampling and measured timers must distinguish them.

## Fixed controls

Reuse exact accepted Qwen256 inputs: EP64, E128, top-k8, H2048/I768, fixed Zipf1.1 seed20261016, pair Jetty, TA1024, chunk4096, 100Gbps/20ns. Preserve routing, planner, compute/network model, relay dependencies/barriers, submission order, full validation and summary logs. Same native Release `-O3 -DNDEBUG -g`; standalone application `-O3 -g`. No optimizations or native source edits.

Compare existing uninstrumented binary with CPU sampled binary (identical executable) and a separate generated diagnostic-only application. Independent Python profiles distinguish Preparation and Preflight from simulator Init/Run/Postflight. Run all expensive processes serially. Existing historical stage measurements are labeled, not silently treated as new paired controls.

## Evidence and stopping condition

At most300 seconds per simulator/stage; preserve partial samples and snapshots, never insist on completion. Unchanged process-tree RSS6GiB, address-space7GiB, minimum host available1.5GiB, minimum free disk8GiB, minimum `/tmp` free2GiB. User CPU-clock perf permissions are tested without security changes. 19Hz DWARF user stack sampling,8KiB stack;128MiB raw profile budget. No lost-record observation is not a completeness guarantee.

Retain Top20 self/inclusive sample records, observed callstacks, explicit denominator/unknown/truncation, source locations, independent timers/counters, phase/event rates and full small-case exact-time output parity. Timers are inclusive nested measured CPU, never summed across overlaps. Partial Chunk profiles cannot establish completed simulated latency, terminal audit cost, or final event count.

Commit only scripts, compact measurement/equivalence evidence, CSV/SVG figures, report and SHA256 manifest. Large perf/script/stack files stay local. No push from runtime worker.
