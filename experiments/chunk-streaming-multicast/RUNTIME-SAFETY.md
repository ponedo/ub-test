# Runtime safety and limits of the evidence

## APP-only, nonblocking transport choice

The original CS graph, task order, readiness, immediate native `SubmitWqe`, and relay-buffer read at Ready are preserved. The fixed key includes source rank/physical identity, expert, global offset, exact length, graph role and canonical dependencies. Membership never changes or shrinks. Each original task belongs to one indexed descriptor; there is no quadratic search across groups during dequeue.

At an already-selected native head, any member proxy may emit one shared envelope only when **all** fixed member heads match their exact task, relative offset, length and payload, are natively eligible now, and the actual envelope fits current egress and CBFC credit. Otherwise the selected eligible native head proceeds immediately as ordinary unicast. An unready member disables a merge, not that selected dequeue. There is no alignment wait, admission queue, reservation, new barrier, leader or scheduling adjustment to manufacture merges.

Eligibility uses the TP's actual wire priority, not the WQE/segment's different default priority. Side-effect-free size/pull choice and inherited commit-time revalidation prevent advertising a small native frame then consuming heads into a stale larger envelope. Merged native dequeues occur synchronously without an intervening simulator event. Native ACK, response, CNP and retry priority remain intact; retries always use native unicast.

## Data, progress and lifecycle

The unchanged WRITE-v2 codec carries shared **actual payload bytes** and exact native child headers. Tags restore correlation metadata; no tag table supplies or reconstructs payload. The switch emits ordinary native WRITE packets, and target validation checks bytes received into real relay buffers before target-driven readiness.

Envelope sequence and wire counters advance only on actual envelopes. The lazy offset-aware wrapper uses actual relative offsets, allowing native-prefix/envelope-suffix and envelope/native/envelope patterns. Each member's separate ordered first-send coverage advances for original unicast and envelope pulls, never retries. Native full logical SSN is retained for offset lookup; a 16-bit wire SSN is only checked against its low bits. It is not used as the logical lookup key.

A group completes only after all native child callbacks. A codec retires only after all original member bytes were sent, all child completions occurred, and V2 pending associations are empty. Persistent pair Jetty/TP/proxy objects survive WQE callbacks until final safe native drain, including reverse work. Group completion is not transport teardown.

## Bounded accounting and hard safety limits

The N256 graph has 23,079 original weight tasks and 13,844 immutable candidate descriptors: 4,608 Stage-I, 9,216 Stage-II, and 20 full-expert fallback groups. There are 9,233 multi-target candidates and 4,611 singletons. A candidate is not a promise to multicast.

Limits are 65,536 weight tasks/groups, 131,072 descriptor/member/dependency entries and bounded pending associations/members, fanout at most 63, and 6 GiB RSS. Exceeding a limit aborts rather than relaxing it or silently dropping accounting. Codecs are allocated only for real envelopes. The legacy MC 128-group cap and legacy 1,024-group observer are unchanged; the hybrid uses separate bounded aggregation rather than enlarging those defaults or using a cap as an admission throttle.

Summary records distinguish logical work from actual source envelopes, reconstructed branches, native fallback, retry work, and per-hop fallback reasons. Fallback counts are committed pulls, not repeated eligibility queries. First-send bytes, all-member completions, codec/association peaks and terminal drain reconcile separately. The `native_retry_*` counters cover installed hybrid source proxies, not every reverse retry in the network; reverse ACK recovery requires its separate physical witness.

Small declared Events fixtures have a combined 131,072-row hard trace bound. Exceeding it fails the witness instead of treating truncated logs as proof. Native dequeue timestamps are not physical transmission timestamps; streaming and both-hop claims use actual source/switch/target physical events. Formal runs use compact Summary accounting, not an unbounded packet log.

## What passed, and what is not established

The accepted Phase-B evidence demonstrates both-hop envelopes, fanout 2/3/4, mixed native/envelope progress, physical chunk streaming, exact all-parent readiness, tails and nondivisible shards, more than 1,024 lifetime groups, native TA-window pressure, stale-grant rejection, targeted Stage-I/II data loss, TPACK/TAACK loss, duplicate handling, exact negative checks, safe cleanup and twelve old-mode comparison pairs. The historical F03 TPACK result is explicitly posthoc-revalidated from unchanged outputs, not a rerun or an invisible oracle replacement. A separate additive fresh-run entry point applies the same reviewed, fixture-bound cumulative-ACK proof during fresh F03 verification; it does not alter the runtime or retroactively rewrite the historical result.

The formal campaign establishes one deterministic N256 five-strategy comparison only. It does not establish crossover thresholds, scalability, statistical variability, convergence, or general superiority. Of 9,233 multi-target candidates, 694 groups emitted at least one envelope; unicast fallback remains substantial. Both relay hops emitted real envelopes, but the perfect-all-merge lower bound is not achieved or assumed.

Additional boundaries:

- Coalescing supports the accepted 78-byte native WRITE header. Other layouts take `unsupported_header` native fallback; generic variable-header merging is not claimed, despite the unchanged V2 codec's broader format capability. Accepted packet/wire formulas use this 78-byte model.
- Native TA wire-SSN wrap was not exercised by the approximately 1,058-TA pressure fixture. Static/unit low-bit checks are not a live transport-wrap proof.
- `reorder_ns` reorders target completion callbacks, not native packets in the network.
- Persistent loss or retry exhaustion may trigger native assertions, not graceful recovered cleanup. Source-envelope loss, lost CBFC credit, Selective/CC and multi-switch reliability are not covered.
- The F03 receipt covers observed original PSNs 0–11 without wrap and terminal native drain. It does not provide a per-ACK instantaneous UNA-transition timestamp. Synthetic modular-arithmetic tests are not runtime evidence.
- Original failed attempts remain preserved. The initial B03 failure exposed an APP eligibility bug (segment priority versus TP wire priority); the approved minimal fix did not change WQE scheduling, native code or protocol parameters.
- Exact formal reproduction needs authorized private inputs and frozen Planner artifacts. Public code and synthetic fixtures alone do not recreate the private trace.
