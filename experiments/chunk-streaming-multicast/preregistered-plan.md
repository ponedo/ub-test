# Preregistered validation and N256 comparison

Status: implementation and static contracts only; this document is not run authorization and contains no new performance result. Base `3a33cc6a249667fc46bf02ac0fed4e1127d7c1ab`. No accepted source/input/result/native artifact may be edited.

## Hypothesis and claim boundary

Adding opportunistic, all-fixed-member per-hop native envelopes to the unchanged CS graph can reduce source weight traffic. A reduced LayerLatency or WeightDuration is a hypothesis, not a correctness criterion. Native unicast fallback is expected when full fixed membership is not simultaneously mergeable. Candidate merging supports the accepted 78-byte native WRITE header; unsupported header layouts fall back. The unchanged variable-header-capable codec is not evidence of generic-header merging coverage. Retain any available accepted codec variable-header unit regression without treating it as candidate merge coverage. AllReady must never wait or delay native SubmitWqe. No scheduler/window/allocator adjustment is allowed in response to results.

## Phase A and build admission

1. Bind the copied base tree, unchanged old application paths, exact CS control inputs/graph, and accepted loaded native library closure.
2. Freeze actual recursive APP compiler dependencies and APP-only compiler command. Build plan and explicit parent build approval must agree on SHA256.
3. Link only the accepted native build. No native rebuild, downloaded replacement, different native flags or source patch is an authorized fallback.
4. Guard this and all later owned process trees with the fixed resource limits in matrix.json. A stopped stage is not an implicit retry request.

## Phase B0: pure and oracle contracts

`test_hybrid_contracts.py` owns pure contract tests; `fixtures.py` owns frozen synthetic fixture declarations; `phase_b.py` owns bounded preparation/execution and exact regression gates. Adapter grouping alone is not sufficient graph proof. `preflight.py` separately validates the original graph oracle, stored exact bytes, CS dependency reconstruction and original parent ordering.

Required negative contracts: duplicate/missing task/member, duplicate destination/physical, invalid input IDs, wrong source/expert/range/role, noncanonical dependencies, dropping a sibling main-origin prerequisite, combining distinct ranges, chunking a whole-expert fallback, changed accepted CS bytes, and unsupported dimensions/capacity. Unit tests do not count as runtime native path coverage.

## Phase B1: frozen small full-Layer cases

The exact machine-readable rows and expected topology are in `fixtures.matrix()`. Freeze that output and input manifests before any simulator starts. Inputs may use the accepted Planner to produce a small correctness fixture; this is not permission to independently replan formal strategies. Reject a fixture before simulation if its intended topology is absent.

- Zero replicas and one-target native singleton.
- Accepted adaptive whole-expert fallback with actual fanout 3.
- Multiple 4 KiB ranges, Stage I fanout 2 and Stage II fanout 2, multiple relays.
- Slow sibling Stage I: own relay early readiness must not bypass original all-main GroupChunk.
- Multiple experts with overlapping work and reused directed native pairs.
- Forced relay tail: matrix/shard/chunk/native-TA nondivisibility, exact no-padding payload coverage.
- Reordered target-completion notifications, distinguished explicitly from native packet OOO.
- Fanout 4 native reconstruction.
- One fixed small-token lifetime/backpressure case exceeding 1,024 cumulative operations and 512 per-pair TAs, with the native TA window still exactly 512.
- Duplicate-ready idempotence and selected stale-grant invalidation.

Live mixed-offset cases must include first-native-then-envelope and envelope/native/envelope. If the frozen cases do not actually exercise them, mark coverage INCOMPLETE and stop; never label hypothetical alignment as PASS or alter runtime waiting policy to force a merge.

Streaming proof uses actual physical TX/RX and actual target completion, not Submit or dequeue alone: relay chunk-ready ≤ original GroupChunk-ready ≤ first downstream physical TX < relay full WeightReady. Show both graph hops using actual source envelopes and switch native reconstruction. Different experts/chunks must remain isolated under observed overlap.

## Phase B2: native recovery and rejection

Frozen bounded fault rows target Stage I WRITE tail loss, Stage II WRITE tail loss, TPACK loss, reverse TAACK/response loss and duplicate native delivery. Enable only the existing native GBN/static RTO/bounded attempt mode for these fault rows; formal no-loss runs retain default disabled retries. Fault delivery occurs after normal link/credit handling, not by losing credits or changing wire protocol.

For forward/reverse retries, retain exact task/TP/PSN/SSN/native payload identities and source TX → switch RX/TX → intended target RX. Native retries are ordinary unicast, not retry envelopes. A group may complete before a late native ACK cleanup; persistent pairs/proxies remain alive until the full native safe-state check succeeds. A forward-only retry counter cannot establish reverse-response recovery.

Expected rejection rows: corrupt weight bytes; corrupt actual relay buffer; early relay before target chunk; early GroupChunk with sibling parent pending; premature full WeightReady; premature edge TargetReady; early sender WQE completion; duplicate sender completion; duplicate forwarding. Match the specific invariant/error, nonzero exit and absence of success artifacts. Generic crash is not PASS. Benign duplicate-ready notification remains a successful idempotence case.

Every successful runtime row needs full payload/combine correctness, exactly-once native completion, exact TP/pair membership in both directions, native safe destruction state, no unacked/descriptors/timers/WQEs/associations/queued replication work, native packet/byte reconciliation and accepted CBFC equations. Pending batched credits may exist under the accepted consumed/returned/restored accounting. Observers must be complete; selected zeros or overwritten rings are not global evidence.

Mutation-test the independent verifier using a genuine valid output: wrong payload/range/expert/source, missing/duplicate member, early ready/completion, missing physical retry, false safe state and broken packet/credit totals must fail. This tests the verifier, not the runtime fault itself.

## Phase B3: unchanged old modes

Run NoBal, Direct, CS and accepted whole-expert MC on each frozen zero/two-hop/tail input, once with accepted executable and once with candidate: 12 paired comparisons (24 executions unless equivalent frozen accepted output identity is proven). Compare exact simulated latency, event timeline, byte/packet/combine/graph/count/load fields and deterministic CSV artifacts listed in `fixtures.PARITY_FIELDS` / `PARITY_FILES`. Exclude only host wall/CPU/RSS and verification-wall counters. Any old-path mismatch blocks Phase C. Do not modify controls to make them match.

Phase B PASS requires all frozen rows plus all 14 declared coverage categories. `phase-b.json` and `old-mode-regression.json` are separate bound gates. Missing/unsupported required evidence yields INCOMPLETE/STOPPED, not a reduced silent acceptance standard.

## Phase C: exact N256 five-strategy comparison

Only after Phase B and independent read-only review: prepare/freeze NoBal, Direct, CS, MC and CS+MC from the existing accepted N256 campaign. Do not run N512/N1024/N2048, token/weight/bandwidth/window scans or repeated timing search.

Fixed shared workload: serialized layer 37, 64 endpoints + one switch, 128 logical experts, top-k 8, 256 tokens/2,048 assignments, model 4,096/FF 1,536/three matrices, activation BF16, idealized FP8 18,874,368-byte weights, 1,024-byte TA, 4,096-byte relay chunk, native allocator 5 ns, link 3,136 Gbps/propagation 20 ns, Jetty TA window 512, original TP packet window 1,000/OOO ACK window 2,048, Roofline 100 decimal TFLOP/s and HBM 2,692 decimal GB/s.

Balanced Direct/CS/MC/CS+MC share exact cached natural plan/assignment bytes: 44 replicas, 21 replicated experts, max fanout 5. Semantic plan hash `5df5e9b331e487985f0b53a8e0485e9acc477bd71d756430029f8b7427bed06d`; routing-mapping hash `17c7c0a71bfd4062650f2d952f0fb9e451641d1c4680f28aecafe5060e71f959`. CS/CS+MC have exact ordered canonical graph hash `1aa978dde5e8f116ec308a24576ea754f17639af61d0dd611139074f956c236a` and executed FNV `716b18790ac6b969`.

NoBal intentionally uses the original router/main placement but main-only baseline assignments, no replicas and zero planning/reroute. Never claim all five have equal assignment files. All five must have equal full logical combine result. NoBal WeightDuration is zero/not applicable, not a speedup denominator.

## Strict accepted CS/MC reuse decision

Prefer minimal three new runs: NoBal, Direct and CS+MC. Reuse accepted CS/MC only if every condition is proven and recorded:

1. Accepted online, independent, compute, aggregate and pre/postflight gates pass, with all required outputs/commands/source/runtime hashes still pinned.
2. Newly prepared controls match all original input/config/graph/plan/assignment bytes and runtime options.
3. Exact loaded native closure is unchanged; candidate addition is isolated from old paths; original four-mode exact regressions pass.
4. Required observers are equally complete, passive and metric-comparable. Candidate executable hash differs by design but does not excuse native/old-path/observer drift.
5. Machine-readable decision contains specific reasons and inspectable bound evidence. If uncertain, declare reuse false and execute only the affected control once under the common final runtime, with the exact fairness reason.

Parent formal approval binds prepared manifest, Phase B, regression, independent review and reuse decision SHA256. It is separate from build and Phase B approval. Five rows always identify NEW/REUSED. No silent restart/rerun, no reuse of host measurements as if simultaneous, and no causal wall-time claim from overlapping residence/service sums.

## Results and stopping

Publish five strategy rows with LayerLatency, WeightDuration, stage/compute intervals, source payload/wire, downstream native weight wire, actual envelope/branch/singleton counts, full-layer TPACK/TAACK counts, WQE/TA/pair/group capacities, final safe state, wall/CPU/peak RSS, fallback reasons and actual two-hop/streaming evidence. Include Phase B coverage and unsupported boundaries. Negative performance is a valid result.

Stop on the first resource/correctness/provenance gate failure, retaining exact reason, completed evidence and NOT_RUN rows. Complete only after all five comparison rows and gates pass, or report the precise unsupported/failed gate. One deterministic run does not establish stability, a minimum token threshold or a crossover point.
