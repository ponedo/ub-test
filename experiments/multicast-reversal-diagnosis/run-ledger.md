# Run ledger

Final status: PASS (2026-10-21 UTC), v3 passive diagnostic observer.

## Regression gate

All 211 simulator invocations passed: 96 roofline accepted/OFF/ON runs,
64 parent/legacy compatibility runs, 18 native-fault runs, 12 expected-negative
correctness checks and 21 invalid-CLI checks. Focused duplicate-packet-UID FIFO,
independent-queue, grant-outcome and fail-closed observer unit checks passed;
independent compute-model units also passed. Accepted/OFF/ON event timestamps and
order were identical. Full online summaries matched except verification_wall_ns.

## Formal runs

Exactly two accepted-input real cases at 3136 Gbps completed:

- Chunk: PASS; whole-case wall 852.582 s, simulator wall 848.663 s;
  peak RSS 3,754,704 KiB.
- Multicast: PASS; whole-case wall 609.818 s, simulator wall 607.455 s;
  peak RSS 3,869,304 KiB.

Both matched the accepted full summaries, payload/output results and private
per-expert compute/readiness evidence exactly. All seven observer counters were
zero: queue_observations_open, queue_unmatched, queue_order_errors,
queue_depth_errors, grant_outcomes_unmatched, grant_start_overwrites and
grant_starts_open. No resource guard triggered. The adaptive coordinator admitted
cases sequentially because of its conservative memory forecast; no limit changed.

Accepted controls remained: 4800 s whole-case wall, 6 GiB process-tree RSS,
7 GiB address space, 1 GiB minimum free host memory, 8 GiB free output disk,
2 GiB free temporary disk, at most two concurrent cases and an additional
128 MiB diagnostic memory reserve per process.

## Observer repair and artifact integrity

v2 simulation results preserved accepted parity, but its packet-UID-keyed queue
observer could conflate concurrent queue entries. Those diagnostic metrics are
invalid and are archived, not used as final evidence. v3 replaced that observer
with FIFO-safe occurrence accounting and added exact grant-outcome accounting;
all gates and both formal cases were rerun successfully.

Accepted source/binary identities, diagnostic runtime source/binary identities,
input identities and baseline evidence were verified before and after execution.
The final nine-file native patch passed forward/reverse application checks with
exact accepted and diagnostic hashes. Detailed real outputs remain private.
See validation-resource-summary.json and validation-resource-summary.csv for
sanitized aggregate evidence. Documentation, plots and reproduction helpers
added after postflight are deliverable additions, not executed runtime changes
or evidence of an additional simulation run.
