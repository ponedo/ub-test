# Chunk Streaming + opportunistic per-hop multicast

## Scope and acceptance boundary

This is a new, isolated **application-layer** strategy at base `3a33cc6a249667fc46bf02ac0fed4e1127d7c1ab`. The accepted `token-screen-native` tree, loaded libraries, accepted screening executable, accepted inputs/results, and all old experiment source files are immutable controls. No Planner, compute, allocation, topology, bandwidth, native packet/window/credit/retry protocol, original chunk partition, or dispatch-gate change is permitted. The new executable links the already-built accepted native libraries; there is deliberately no native-build fallback.

The displayed strategy is `chunk-streaming-multicast`. The input graph remains original CS **kind 2**, selected independently of `--weight-transport=cs-mc`. The default `--weight-transport=original` leaves original graph values 0–4 and their old paths unchanged. NoBal is a harness result label for the accepted direct-kind main-only execution, not a new graph kind. Existing direct, CS and MC emitters are reused, not edited.

## Graph and immutable partition

`adapter.emit` calls the accepted relay emitter with `chunk-streaming`. It changes only strategy identity and separate transport metadata in `config.json`. `from_cs_control` copies the six graph-bearing files byte-for-byte and decorates only configuration. `preflight.compare_cs_bytes` requires exact bytes, original order and newline representation for:

- `input.txt`, including graph kind and original physical ordinal order;
- `graph-input.txt` and `weight-edges.csv`, including graph role/scope and chunk tails;
- `transfers.csv`, including task IDs, source/target physical IDs and ordered dependencies;
- `plan.json` and `assignments.csv`.

The unchanged accepted graph oracle and independent preflight reconstruct the graph. A temporary read-only view maps the new configuration label to CS solely for the unchanged checker, without rewriting any candidate or control input. The candidate checker additionally reconstructs all-main GroupChunk prerequisites and rejects missing sibling-relay prerequisites, duplicate physical/task/target IDs, cross-expert provenance, invalid integer ranges and altered full-expert fallback. Canonical executed graph bytes/FNV must agree with CS.

Fixed operation key: `(source rank, source physical ID, expert, global offset, exact byte length, graph role, exact ordered dependency IDs)`. Operation IDs start at 1 in first occurrence of the unchanged weight-task order. Membership is fixed for the entire run; runtime never chooses a subset. Every weight task occurs exactly once, including singletons and whole-expert fallback. Roles are `stage1`, `stage2`, and `direct-fallback`; transfer runtime stage 2 alone does not distinguish graph hops.

The accepted N256 graph contains 23,079 weight tasks and 13,844 operation candidates: 4,608 Stage I, 9,216 Stage II, and 20 whole-expert fallback groups. There are 9,233 multi-target and 4,611 singleton candidates. The 13,824 relay groups preserve 4 KiB ranges; fallback groups retain their original 18 MiB whole-expert edges. The sum of candidate group payloads is **23 × 18 MiB, only a perfect-merge lower bound**. Actual envelope coverage and unicast miss bytes are measured; they are not asserted equal to that bound.

## Immediate native submission and nonblocking AllReady

The original CS `Send` call, relay-buffer read, native `SubmitWqe`, task order and readiness time are unchanged. For each native source-port grant, the selected native head may be coalesced only when **all fixed members are eligible now**:

1. Fanout is at least two; all members have an original native REQUEST/WRITE head.
2. Every current head belongs to its exact original child task, source/expert/range/role/dependency group.
3. Task-relative offsets and valid payload lengths match; native priority traffic, retry work, a missing head, a different task or native limitation makes merging ineligible.
4. The candidate eligibility path supports the accepted 78-byte native WRITE header; other header layouts use native fallback. The unchanged V2 wire codec remains variable-header-capable, but generic variable-header merging is not claimed exercised here. Native headers and actual payloads are compatible; data under an identical semantic key is compared and corruption fails correctness rather than being concealed as fallback.
5. The actual larger envelope fits current egress and CBFC credit. Configured cell geometry is read from the native port; an envelope-only space/credit miss cannot block a selected native packet that fits.

When any condition fails, the selected original native packet is dequeued immediately as unicast through its unchanged native path. There is no wait, partial collection, reservation, pair ownership, special leader, barrier, queue reordering or subset merge. `IsLimited` follows the selected native TP rather than another member. This is why AllReady introduces no new group-head dependency cycle: an unready sibling can disable a merge but cannot disable a selected native-eligible dequeue. Native window/credit/network stalls still exist and are not claimed solved.

`Size` and `Pull` use a coherent fresh choice and preserve native commit-time revalidation. After a successful envelope decision, all original native dequeues occur synchronously in one simulator callback; no event interleaves between them. A stale grant must not return a larger envelope after advertising native packet size. Refresh every affected proxy after merged pulls, the selected proxy after native pulls, and the relevant pairs on receive/admission. Proxies remain discoverable while native unacked work/retries remain.

## Exact CS readiness remains target-driven

Stage II waits for **all** same-expert, same-offset-and-length main-origin edges, including other relays' incoming edges. Own-source coverage is additionally required. It does not wait for another chunk, another expert, full-expert reception, downstream fanout, sender WQE/group completion, or a reservation release.

Native target data is copied and verified before TargetComplete. EdgeReady derives from exact target completion coverage. A dependent send happens at the same simulation timestamp as its final original parent EdgeReady; native submit equals that logical-ready timestamp. The Stage II payload is read from the actual received relay buffer. Replica WeightReady requires full weight coverage. Dispatch remains `max(weights_end, reroute_end)`.

`hybrid-groups.csv` records original readiness, immediate native submit, first/last native dequeue, original byte coverage, receiver-ready, child sender completion and all-child completion. Native dequeue is **not** physical TxStart. A streaming claim additionally needs the bounded physical witness: exact relay target-ready/GroupChunk-ready ≤ downstream physical TX < relay full-expert WeightReady, plus physical branch/RX evidence. Both Stage I and Stage II real envelopes are required for a two-hop multicast claim. A correct no-envelope run is possible but does not satisfy that coverage claim.

## Codec, accounting and lifecycle

The existing native V2 wire format is unchanged: an envelope carries exact native child headers and shared payload; the switch reconstructs ordinary native WRITE packets. Native PSN, SSN, WQE, per-target ACK/response, GBN/window and retry state remain native. Retries bypass coalescing and do not advance original first-send counters.

A lazy hybrid-only offset-aware codec is created only for an actual envelope. Its monotonically increasing envelope sequence counts real envelopes, not chunks or native packets. Sequence × segment is not a byte offset. Envelope-covered intervals may have unicast gaps, including native-prefix/envelope-suffix and envelope/native/envelope patterns. Do not use inherited whole-expert `sentBytes` or `MemberComplete` as logical readiness/coverage. The manager tracks each original member's ordered first-send byte coverage separately for native and merged pulls.

Association records exist only for actual envelopes and carry restored tags plus integrity-only native header information. They are keyed by unique operation ID and sequence, consumed once, and preserve the accepted finite timeout. A codec retires only after all original member bytes, native child sender completions and pending associations are drained. Operation IDs are not reused. Group completion does not authorize destroying persistent pair/TP/proxy state; final safe native drain is checked separately in both directions.

Finite descriptors are capped at 65,536 weight tasks/groups and 131,072 descriptor/member/dependency entries, with fanout at most 63. Codecs and associations are lazy and live-state counted; no replacement global throughput window or arbitrary enlarged old 128/1,024 lifetime cap is introduced. The hybrid observer uses separate bounded aggregate role/reason storage, never the legacy group-query observer. Legacy observer defaults/limits remain unchanged. No per-chunk Jetty/TP or per-pair full-expert payload duplication is allowed.

For a group of fanout `f`, native packet count `p = ceil(bytes/segment)`, actual envelopes `e`, actual envelope payload `b`, native fallback packets `u` and payload `v`, the verifier requires:

- `e*f + u = p*f` and `b*f + v = bytes*f`;
- envelope wire = `b + e*(24+76*f)`;
- downstream reconstructed branch wire = `b*f + e*f*78`;
- original unicast fallback wire = `v + u*78`;
- restored associations = `e*f`.

Actual Pull-level fallback reason counters reconcile with native fallback totals by graph role; repeated eligibility queries are not packets. Physical endpoint envelope/native bytes and switch native weight bytes reconcile with these totals, with retry/loss tests checked separately. TPACK and TAACK totals are full-layer work counters, not additive wall-time attribution.

## Output and resource boundary

Default Summary output is bounded: `hybrid-groups.csv`, `hybrid-stats.csv`, `hybrid-fallback.csv`, `hybrid-summary.json`, `hybrid-lifecycle.json`. Small predeclared Phase B rows may add bounded Events/physical/offset witnesses; a truncated ring is not complete proof. Outputs include actual per-hop merge coverage, fallback reasons/miss bytes, peak live codecs/associations/capacity, persistent pair resources and terminal safe state.

All build/test/simulation process trees are sequential under the accepted guard: RSS ≤6 GiB, RLIMIT_AS 7 GiB, wall ≤4,800 seconds per stage, host reserve ≥1 GiB, case filesystem free ≥8 GiB and `/tmp` free ≥2 GiB. Admission reserves the full 6 GiB plus 1 GiB host reserve and rejects a competing simulator. Durable host heartbeat and cleanup only concern owned process sessions. No limit escalation, silent retry or automatic resumption is allowed.

## Formal fairness and reuse

Formal data is only N256, serialized layer 37, five strategies in fixed order: NoBal, Direct, CS, MC, CS+MC. Balanced modes share exact cached plan/assignments and routing. NoBal uses accepted main-only baseline construction without a solver, zero replicas and zero planning/reroute; it is intentionally not forced onto balanced assignments. Its zero WeightDuration is not a weight-speedup denominator.

Before formal admission: Phase B full correctness/fault coverage, 12 original-mode paired exact regressions, frozen five inputs/commands, native/source pins and independent review must pass. Parent approval binds the exact manifests and evidence hashes. Strict reuse of the accepted CS/MC results is preferred if input/runtime/native closure, untouched old code paths, exact regressions and equally complete passive observers are proven; otherwise the machine-readable reuse decision must explain the necessary one-time affected control rerun. All five result rows distinguish NEW/REUSED and host measurements. Faster is a hypothesis, not a pass criterion. Do not alter scheduling after observing an unfavorable result.

## Audit source map

Paths below are relative to the immutable accepted `experiments/` unless marked Native. These audit references explain unchanged contracts; new implementation line numbers may move during review.

- `direct-weight-forward/weight-distribution.h:46–118`: accepted relay selection, order, fallback, shard partition, Stage I/II ranges; `:72–75` full-expert fallback; `:101–116` tails and emission ordering.
- `multi-npu-relay/adapter.py:8–37`: exact ordered indexed GroupChunk dependencies; emitter below reuses existing plan/assignments and graph tool.
- `multicast-controlled-ablation/layer.cc:180–232`: CS graph selection and original all-main GroupChunk dependencies; `:324–345` native target execution/copy/completion; `:356–379` original immediate Send and native WQE submission; `:407–430` EdgeReady/full WeightReady; `:449–461` dispatch/planning gates.
- `pair-jetty/online-validation.inc:36–62,77–119`: exact send timestamp, target coverage, relay provenance, full replica and GroupChunk readiness, final bytes.
- `ultraep-multicast-integration/preflight.py:29–84,161–173,204–210`: canonical graph/FNV and independent dependency reconstruction.
- `ub-multicast-v2/adapter-v2.h:25–85`, `ub-lightweight-multicast-adapter/adapter.h:60`: why the inherited emission cursor/completion semantics cannot represent mixed native/envelope progress unchanged.
- Native `src/unified-bus/model/ub-write-v2.h:14–18,53–71`: unchanged operation/sequence/exact-native-header codec.
- Native `src/unified-bus/model/ub-switch-allocator.cc:734–765`: native commit revalidation and actual-size FC/egress checks.
- Native `src/unified-bus/model/ub-port.h:62`, `protocol/ub-cbfc.h:30`, `ub-port.cc:282–291`: egress capacity, native credits and configured cell geometry.
- Native `src/unified-bus/model/protocol/ub-transport.cc:2905–2909`: original TA admission refresh/port trigger.

## Explicit unsupported/failure boundaries

Persistent loss/retry exhaustion, source-envelope loss, lost CBFC credits, native Selective/CC behavior and multi-switch reliability are not claimed covered. Target callback reorder is not native packet out-of-order. A fault test must prove its actual intended path was exercised; a zero forward retry count does not establish reverse TAACK recovery. Expected-rejection rows must match their exact invariant violation and nonzero exit, with no false success artifact. Resource or correctness failure stops further admission and retains completed coverage and NOT_RUN rows.
