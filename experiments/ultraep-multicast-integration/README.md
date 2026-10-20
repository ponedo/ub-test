# UltraEP Multicast WRITE v2 integration

Adds `multicast-v2` (strategy 4) to the accepted pair-Jetty UltraEP executor. This directory is an experimental executor and reproducible comparison, not a new UB reliable transport protocol. The original executor and Planner files are unchanged.

## Components

- `layer.cc`: existing executor with strategy selection and read-only evidence hooks.
- `pair-multicast-v2.h`: one dequeue proxy per existing native pair TP. Per-expert v2 codecs share actual payload bytes; controls, transaction responses, singleton writes and native GBN retries remain ordinary unicast.
- `integration.inc`: native pair binding, receiver-ready evidence, packet classification, resource checks and bounded fault tests.
- `patches/peek-original-head.patch`: read-only original segment observation, no speculative dequeue or PSN mutation.
- `patches/allocator-revalidation.patch`: opt-in RR grant revalidation for these new proxies, before dequeue/credit consumption. Attribute presence is cached per static TypeId, while positive types still read the getter on every commit; no queue objects are retained. Existing queues do not opt in; DWRR is not supported by the new paired adapter.
- `adapter.py`: reuses the accepted Planner's fixed result and Direct graph, changing only the transport strategy. Singleton destinations use native unicast.
- `pair-stress.cc`: hand-built native adapter hardening, separate from Planner/end-to-end performance evidence.
- `stage-a.py`, `stage-b.py`, `regress.py`, `verify.py`: guarded validation, fixed real comparison and independent aggregate checks.
- `collect.py`: allowlist export without raw routing, per-token private data or payload.
- `plot.py`: descriptive plots for this single experiment, not a scaling claim.

## Admission and lifecycle

Original grouped first-send heads must align. Native Jetty backpressure can reorder different WQEs, so initial submission order alone is insufficient. The adapter atomically reserves each group's unordered endpoint-pair set before admitting its child WQEs. It releases reservations after all original bytes are dequeued, and schedules later admission after the current dequeue returns. Pair-disjoint groups can first-send concurrently; shared-pair groups cannot. Their native completion/retransmission lifetimes can overlap.

This is an explicit first-send admission restriction, not an ACK table, retry timer or reliability state machine. Opposite-direction grouped first sends are excluded on the same pair, keeping transaction responses from mutually blocking behind grouped originals. Responses and retries bypass the group barrier. Group contexts are not reused or destroyed on WQE completion; final checks require native TP quiescence, empty association maps, idle Jetties, drained queues and conserved credits.

The existing Dispatch gate is preserved: all replica targets must have verified their complete weight bytes, and Token Reroute must have finished. Native sender completion is recorded separately and may occur later than receiver-ready. Output completion and final network/resource drain are also separate observations.

## Reproduction

Use a disposable native tree reconstructed for project commit `93033c1c946542e90a94303560346f39dc0be828`, before the two patches in this directory. The exact 109-file parent identity is in `accepted-native-source-sha256.json`. See the preceding retransmission experiment's README/reproduction instructions for fixed native base and earlier patches.

Run:

```sh
bash experiments/ultraep-multicast-integration/reproduce.sh \
  /absolute/native-tree /absolute/fresh-private-output \
  /private/layer_37.json /private/source-manifest.json /private/expert-counts.csv.gz
python3 experiments/ultraep-multicast-integration/plot.py \
  /absolute/fresh-private-output/compact-results
```

The real input is intentionally not distributed here. Exact hashes and historical reconstruction checks are documented in `INPUTS-AND-BUDGET.md`. The script stops on input/build/Stage-A/capacity/fairness/validation failures. It does not silently substitute synthetic routing, resume partial cases or widen the experiment.

The default reproduction is sequential. In the recorded run, the user requested bounded overlap of the final Chunk/v2 cases; `parallel-last-case.py` and `merge-parallel-results.py` preserve separate receipts and identical executable bytes and prevent duplicate admission. The operator must verify both driver exits before passing `--drivers-exited`; this flag is an explicit operator assertion, not a PID liveness check. Both exits were confirmed in this run before merging. Each simulator retains 3600-second per-process-stage wall limits, 6 GiB process-tree RSS, 7 GiB address space, at least 8 GiB working-disk space, 2 GiB temporary space and 1.5 GiB available host memory. Every strategy retains the same 8 GiB logical payload and 1,000,000 weight-task limits. The real comparison is only L37 / 2048 tokens / EP64; no 4096-token or 94-layer expansion.

## Modeling limits

Tag-free v2 wire bytes carry payload and variable native headers. Simulation-only associations restore metadata, never payload, and remain bounded. Source coalescing, switch parsing, fanout lookup and reconstruction have no separately calibrated hardware execution cost. Native link/queue/credit timing is still modeled. The routing trace and model dimensions are real inputs; payload bytes are deterministic validation patterns, not a loaded Qwen checkpoint, and compute is a latency model rather than executed GEMM. Idealized FP8 weights omit scale/padding metadata; compute throughput is assumed, not hardware-measured. Planner and reroute modeled durations preserve the existing executor's fixed assumptions; actual preparation/host CPU times must not be confused with them.

See `REPORT.md` for measured results, failed coverage attempts, regression scope and known limitations.

An interrupted resource-admission decision is not silently resumed. `resume-stage-b.py` supports the specifically recorded projection-only stop: it preserves the original ledger, verifies the frozen final binary/native/input identities and the successful NoBal receipts, and runs only the still-unrun treatments under the same3600s guards. It refuses protocol/validation failures or a changed native library. It never substitutes the earlier diagnostic run.
