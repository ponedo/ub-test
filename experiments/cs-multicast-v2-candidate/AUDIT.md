# CS+Multicast v2 Candidate: source and event audit

Fixed v1: `e3efc29e901024cea6343196f6ab33958e3b02cd`. All v1 source, reports and measurements remain unchanged. Native paths refer to the exact inherited six-patch tree described by [v1 native provenance](../chunk-streaming-multicast/NATIVE-PATCH.md), not a pristine upstream checkout. Line references below name that fixed baseline, not the edited candidate.

## Answers to the five audit questions

1. `member_absent` means the required original head is unavailable now. It can be not yet admitted/generated, or already consumed; retained B05 proves the latter. The counter alone cannot distinguish them.
2. `member_priority` combines CNP, transport ACK and enabled GBN retry. Transaction TAACK is not universally a priority-queue message: an ordinary RESPONSE behind a WRITE obeys native head order.
3. `member_task_mismatch` means the first unsent native task differs from the fixed group member. Chunk skew and interleaved native WQE/TA admission can cause it; the old aggregate does not identify which mismatching task.
4. No missed fully commit-eligible selected group was found. Other groups may be graph-ready without their expected native segments being at every head. Borrowing a different group's grant or extracting a non-head segment would violate this exploration's constraints.
5. The bounded opportunity is to avoid creating new divergence before native heads align, not to repair consumed bytes or reorder existing heads. A speculative one-shot APP hold may help or may waste time; lower latency must be measured independently of merge coverage.

## Candidate safety interpretation

The single candidate is a fixed 5 ns per-original-head APP eligibility veto for Stage I/II chunks only. Whole-expert graph fallback is unchanged. It may arm during a native queue scan before that queue is selected. This changes realized inter-TP grant timing and can indirectly affect admission/queued-response latency, but does not change native RR policy, slot order, native same-TP packet order, or the 5 ns allocation service. Local CNP/ACK/GBN retain native precedence.

A peer with priority work may have unknown underlying CC eligibility. The implementation must not probe CC through a state-mutating accessor or claim the peer is ready. Such a speculative hold is safe only because it reserves/consumes nothing, expires once, and every actual send still uses native eligibility/size/credit checks. A newly observed native limitation releases/spends the hold rather than extending it. Deadline release bounds only additional APP inhibition, not total native queueing latency.

The historical examples below are retained small synthetic observations. B07 used a historical non-4096 chunk and is audit context only, not a new v1/v2 comparison. All new paired tests use chunk=4096.

## Detailed adapter audit

Read-only audit, 2026-10-21. No simulation, build, accepted-source edit, graph change, native arbitration change, or parameter sweep was performed. Baseline: accepted e3efc29e901024cea6343196f6ab33958e3b02cd, now frozen v1. Evidence below is existing SMALL synthetic B05 (8 ranks) and B07 (4 ranks), not real256 or a larger scaling run.

## Executive finding

The three reasons are **first failed current-head predicates at an actual original native pull**, not diagnoses of how that state arose. In particular, `member_absent` does not mean “not generated.” B05 proves a consumed counterpart: task 128 finishes its original bytes before task 129 reports absent. B07 proves priority-induced divergence followed by a task mismatch, but its compact event file cannot identify the mismatching head task.

There is no code path that fails to merge an exactly aligned, full-membership, eligible selected group after all checks pass. The adapter considers only the group of the selected TP's first unsent original segment. Other groups may be logically ready, or even have an eligible head set on disjoint TPs, without being searched by that pull. That is not evidence that the selected group's heads were skipped. Same-TP non-head matches must not be extracted as a Candidate shortcut.

## Source locators

In this document:
- A = `../chunk-streaming-multicast/`
- N = `ns-3-ub/src/unified-bus/model/`
- D = `../direct-weight-forward/weight-distribution.h`
- E = `retained-small-v1-evidence/`

Line numbers refer to these exact local files. Publication A includes its sibling codec through the dependency repository; no source in either tree was changed.

## Choose, Pull, and Proxy

`A/hybrid-multicast.h:82-110`, Manager::Choose:
1. Start with selected TP's native next-packet size. Selected CNP/ACK/pending enabled GBN work returns immediately with group zero (83). Thus an ACK-only selected pull is not a counted `member_priority` fallback.
2. Peek selected first unsent original segment; require REQUEST and a task mapped to a hybrid group (84-86). Bind the exact selected member/source/TP. Derive the task-local offset from full logical SSN and assert it equals committed original coverage, `firstBytes` (87-88).
3. Singleton exits before checking other members (89).
4. Iterate immutable group membership in recorded order: priority, empty, native limit, null original peek, REQUEST kind, exact task, offset, WRITE/length/payload, then native header/priority checks (91-104). The reason records only the first failure encountered, not every blocker or its duration.
5. Check live codec association capacity, actual envelope egress room, actual CBFC cells (107-109). Only then return merge (110). Payload equality is asserted, never guessed.

`Choose` has no reservation or queue mutation; `Size` calls it (118), and `Pull` calls it again synchronously at actual commit (119-120). Pure here means no traffic/sequence/coverage mutation: native diagnostic reads may emit diagnostic observations. A hypothetical merge discovered in a size/eligibility query is not a recorded merged packet.

`Pull` (122-131) either emits the codec envelope and advances every member's original coverage, or invokes **selected native TP GetNextPacket**, validates actual packet task/WRITE/range/wire SSN, and advances only that member. Fallback counters are incremented only for actual group-bearing first sends at 128. Retries follow native handling and are separately counted (121,127). `OffsetCodec::EmitAt` (14-19) permits gaps already sent by native unicast, forbids backward envelope offsets, and changes only codec emission cursor, not logical coverage.

`Proxy` is a per-source/destination persistent native pair wrapper, not a group scheduler. Installation unregisters native queue ownership then registers one wrapper per pair in destination order (136-139). `Refresh` copies native head time and refreshes allocator summary (44); no alignment wait is implemented. `IsEmpty` retains liveness for outstanding unacked work (40), while `IsLimited` excludes native-empty/native-limited work (147). These are deliberately different predicates. Receiving packets goes through the native switch then refreshes the relevant proxy (143).

`RevalidateOnCommit` is always true (37-38). The existing RR adapter contract in `N/ub-switch-allocator.cc:729-748` revalidates emptiness/limit/flow control; stale grants are discarded and a fresh native allocation episode is paid. Actual size is rechecked for egress capacity before pop (753-765). Candidate must retain this contract; neither stale cached group choice nor a differently sized substitute can be committed based on an old frame-size check.

## Exact meanings of the requested reasons

### member_absent

Set at `A/hybrid-multicast.h:93` if a member's native TP reports empty, or at 95 if its original-segment peek is null. Priority is checked first and native limitation precedes the null-peek test. This means the required original head is not available at this instant, not that the WQE has never been submitted, that no TA descriptor exists, or that the receiver lacks bytes.

`N/protocol/ub-transport.cc:2937-2952,3022-3039` defines native empty from pending transmit work, not from sender-completion status. A TP may retain sent-but-unacked descriptors while having no original transmit work. `N/protocol/ub-transport.h:404-412` skips null/sent-completed segments and returns the first unsent segment; it does not wait for sender ACK completion before moving on.

Possible causes must be separated: not submitted due to graph readiness; submitted but preparation/admission has not produced an original head; all relevant original bytes already consumed; other retained reliability state without original work. Only an event/descriptor timeline can disambiguate these. WQE submission alone does not prove native segment generation: `N/protocol/ub-transaction.cc:914-943` prepares a segment and schedules a separate admission event; 978-1000 admits, triggers native transmit, then schedules subsequent work. Do not change that native production schedule to manufacture alignment.

### member_priority

At `A/hybrid-multicast.h:78,92`, a member has nonempty CNP queue, nonempty ACK queue, or retransmission enabled plus pending GBN retransmission. It is **not specifically an ACK diagnosis** and does not identify which member or priority subtype in the compact CSV. Native GetNextPacket serves CNP, ACK, retransmission, then new data in that order (`N/protocol/ub-transport.cc:900-938`). A candidate cannot skip these obligations to consume original data. Native `IsLimited` permits CNP and ACK service (3044-3072); that permission must not be mistaken for permission to send a hidden original WRITE.

### member_task_mismatch

At `A/hybrid-multicast.h:97`, the member is not priority-blocked, not empty or native-limited, and has a REQUEST original head, but its task ID differs from the fixed member task. This is a head-order mismatch, not evidence that the expected task is absent everywhere, logically unready, generated late, or already complete. The expected task could be behind another task, not yet generated, or have already advanced beyond the requested range. The recorded reason alone cannot choose among those causes.

`N/protocol/ub-transport.cc:670-702` and `.h:404-412` make the same first-unsent selection. Looking further into the vector and extracting a matching expected task would change same-TP native ordering. A group-aware Candidate must not do that.

## Retained SMALL event examples

### B05: priority then consumed-counterpart absent

`E/B05/candidate/hybrid-events.csv:2,5` records group 1 envelopes at 206000 and 403000 ps, offsets 0 and 1024, each 1024 bytes, fanout 2. Lines 8 and 11 record task 128 native originals at offsets 2048 and 3072 at 691000 and 978280 ps with `member_priority`. Lines 14 and 17 record task 129 originals at the same offsets at 1257680 and 1522120 ps with `member_absent`.

`E/B05/candidate/hybrid-groups.csv:2-3` identifies the two group-1 tasks, both submitted at 201000 ps, total 4096 bytes. Task 128 first-send completion is 978280 ps; task 129's is 1522120 ps. Therefore when task 129 gets absent, its counterpart's relevant original bytes **already went out**. These are not “wait a little longer for generation” opportunities. Re-emitting task 128 as a fresh original would duplicate logical traffic and corrupt progression. A prior intervention might have prevented divergence, but this trace alone does not prove it would have improved latency or preserved ACK service.

The corresponding retained `cs-mc-private/phase-b-reproduce-validation/runs/B05/candidate/hybrid-events.csv` was byte-compared and is identical. This is two retained copies of evidence, not an independent new run performed for this audit.

### B07: priority followed by task mismatch, not proof of generation skew

`E/B07/candidate/hybrid-events.csv:211` records group 47 task 131 offset 0 (333 bytes), `member_priority`, at 7500240 ps. Line 212 records partner task 130 offset 0 with `member_task_mismatch` at 7603840 ps. `hybrid-groups.csv:68-69` shows both tasks submitted at 6280840 ps, same group/source/range, total 2000 bytes. Task 131's matching original range was already consumed before task 130 tried to merge it.

The exact wrong head task is not present in this compact trace, so do not invent it. Neighboring line 213 is a valid group 48 envelope at 7608840 ps; lines 214-217 contain further priority/task-mismatch fallbacks for groups 49/50. These observations demonstrate local divergence and subsequent successful merging elsewhere, not a universal scheduler defect or global root-cause distribution.

## GroupChunk graph timing is non-negotiable

`D:101-116` builds chunk-major main-to-relay edges, then relay-specific ranges/leaves. Streaming relay edges use `GroupChunk`. `A/layer.cc:213-243` binds every main-to-relay task for the same expert, global offset and bytes as a relay child's dependency, not only that relay's own incoming edge. Indexed and scan paths preserve task order. `Send` asserts all dependency target-ready flags (372-377); `Ready` calls a child only after every dependency is ready (424-437). Sender ACK completion is not the readiness gate.

B05 is a useful explicit example. `events.csv:9` has task 129 receiver-ready at 1826600 ps. The other main edge, task 128, becomes receiver-ready only at 21282720 ps (`events.csv:17`). GroupChunk readiness and sends for tasks 134,135,140,141 all occur at 21282720 ps (`events.csv:18-26`). Task 128 sender completion is later, 21342640 ps (`hybrid-groups.csv:2`). Thus readiness is the maximum of parent receiver-ready times, neither the early relay's individual readiness nor all sender ACKs. Before that maximum, a missing child segment is mandatory graph gating, not an adapter loss to optimize away.

The immutable hybrid grouping key contains source, source physical, expert, offset, bytes, role and dependencies (`A/hybrid-integration.inc:6-14`). Equal bytes or equal expert alone does not establish common group eligibility. Same logical-ready timestamp still does not prove same native-head admission time.

## Safe opportunity boundary and missing evidence

Three distinct meanings of “eligible” must not be conflated:
1. Graph-ready: all GroupChunk dependencies satisfied and WQEs submitted.
2. Native-original ready: exact expected task/range is first unsent on each fixed member TP, with no higher-priority native work and no native limitation.
3. Commit-ready: all above plus payload/header equivalence, codec association space, egress bytes and credit for the actual envelope.

For (3), if any group member is the selected proxy, Choose deterministically merges. If (3) describes a different group on disjoint TPs, Choose does not search it. Selecting that different group in place of the native grant would alter arbitration and is outside this Candidate scope. If expected members sit behind another same-TP head, the group is only (1), not (2), regardless of its submission time.

Unavoidable at the instant of decision: singletons; pre-readiness child absence; priority/GBN obligations; native limits; already-consumed counterpart; wrong task/kind/offset at a protected head; incompatible headers/payload lengths; no envelope capacity/credit. “Unavoidable now” does not prove historically unavoidable under every legal adapter design.

Potential safe investigation, not a claimed result: bounded adapter-local coordination that preserves every TP's first-unsent order, does not postpone ACK/CNP/retry service, never generates traffic early, never borrows a different native grant, preserves the CS graph and revalidates actual commit eligibility. Any waiting policy must demonstrate finite release/native progress and control-service liveness. The retained examples do **not** establish that such coordination improves performance; no implementation or wait budget is recommended as validated by this audit.

Required SMALL-only observational evidence before calling something a missed safe merge: exact selected queue and grant/commit time; group/member/task/full logical SSN/local offset; each member's first-unsent task/offset and submitted/produced/consumed state; separate CNP/ACK/GBN/limit predicates; exact candidate envelope size, egress/credit and association capacity; plus subsequent successful original consumption and receiver-ready/ACK progression. Distinguish observations at selection from commit. Existing `hybrid-events.csv` logs actual committed pulls (`A/hybrid-integration.inc:24-27`), not all hypothetical eligible sets, failed size queries, blocker member identities, or absent-production history. Aggregate fallback counters cannot supply those missing facts.


## Detailed native audit

## Scope and verdict

Read-only source audit, 2026-10-21. No source edits, builds, simulations, full realTrace experiments, largerToken runs, or strategy matrix runs were performed. This report alone is not runtime certification or permission to expand the experiment. Accepted `e3efc29e901024cea6343196f6ab33958e3b02cd` remains immutable v1.

**Conditional feasibility, not unconditional safety approval.** A finite, one-shot APP eligibility hold on the current original WRITE head can preserve native same-TP original order, immediate APP SubmitWqe, existing reliability machinery, native allocator implementation/slot ordering, and CNP/transport-ACK/GBN precedence. It necessarily changes which queues are eligible and therefore can change the realized inter-TP grant sequence. If “no allocator order changes” requires an identical realized grant sequence, no nonzero useful hold satisfies it. Likewise, a queued transaction TAACK behind a held WRITE cannot bypass that WRITE without changing native same-TP order. Its additional head-of-line delay is unavoidable, even though the hold itself can be bounded.

Do not implement a generic “wait until siblings ready” barrier. The bounded design must fail open to the exact native head, including when full-membership merge never becomes possible. This only bounds added APP inhibition, not end-to-end send/completion latency under native CC, credit, contention, retransmission, or admission backpressure.

## Sources and identity

- Candidate APP: `../chunk-streaming-multicast/hybrid-multicast.h` (abbreviated **H** below), plus `layer.cc` (**L**).
- Dependency old adapter: `../multicast-controlled-ablation/pair-multicast-v2.h` (**P**).
- Actual native root: `ns-3-ub`; native transport `.cc` (**T**) and `.h` (**TH**) refer to `src/unified-bus/model/protocol/ub-transport.*`; transaction **TA** refers to `.../ub-transaction.cc`; function **F** refers to `.../ub-function.cc`; allocator **A** refers to `src/unified-bus/model/ub-switch-allocator.cc`.
- Native working tree HEAD read as `b8375b51a094d3b1217b697989e1ab979f609e64`. HEAD is not asserted to describe all working-tree modifications.
- Published H and `../chunk-streaming-multicast/hybrid-multicast.h` have identical SHA256 `1ac168266209776b7afe8e974457332a5dbc28f7ad32fab37f61976bc650ffa7`.
- This audit uses the pinned source and retained synthetic evidence.

## Native queue order, ACK distinction, and admission

1. **IsEmpty is transmit-work emptiness, not reliability quiescence.** T:2937–2952 delegates to HasPendingTransmitWork (3022–3039): CNP, transport ACK, pending GBN/selective retry, then unsent PSN work. Fully sent but unacknowledged segments may remain while this is empty. TH:406–412 PeekOriginalSegmentForAdapter returns the first non-null, not-sent-complete segment, without dequeuing or advancing PSN. T:669–705 BuildNextDataSendContext uses this same first-unfinished vector order. TH:358–374 PushWqeSegment appends, not inserts by APP group.
2. **Native priority is CNP → transport ACK → retry → original data.** T:881–938 GetNextPacket and 1059–1101 GetNextPacketSize agree. T:3042–3104 IsLimited immediately exempts CNP/transport ACK from native data window limits; GBN has its own CC check; originals then face inflight/CC checks at 3138–3169. Hybrid install rejects non-GBN enabled retransmission modes (H:138), so a new gate must not silently broaden this supported mode.
3. **TAACK is not synonymous with m_ackQ.** T:2219–2266 builds a transport response carrying a TAACK header, enqueued in m_ackQ at 2270–2289. Separately, TA:2057–2100 builds a transaction RESPONSE segment whose opcode can be TAACK, and TA:2103–2111 enqueues it through EnqueueRemoteRtpWqeSegment. TA:1439–1504 appends that remote work into the same TP-keyed native RTP transmit admission queue. It is not a privileged m_ackQ item. A RESPONSE at the native original head must never be coalescing-held; a RESPONSE behind a held WRITE cannot be extracted/promoted. Preserve this distinction in all claims and diagnostics.
4. **SubmitWqe acceptance is not TP readiness.** L:372–396 Send checks CS dependencies and immediately calls hybrid.Submitted and native SubmitWqe at 393, then refreshes proxy. F:155–240 SubmitWqe validates, pushes into Jetty, and triggers native scheduling. TA:710–757 retains native protocol dispatch delay; TA:1400–1435 queues local WQEs; TA:1250–1345 admits only after transport capacity preflight and commits Jetty cursor after TP admission. T:2682–2714 assigns TP MSN/PSN and appends the segment only on acceptance. T:2848–2868 distinguishes shallow active-send depth, retained segment capacity, and inflight packet limit. A hold consumes existing head capacity and can indirectly delay admission of later work. Do not call immediate submission simultaneous head availability.
5. **Feedback ownership stays native.** T:789–813 advances sent bytes/PSN, starts retransmission timer, and wakes admission on first-send completion. T:1833–1874 removes ACKed retained segments and wakes blocked work. T:1418–1435 explicitly prevents transport ACK from completing requests that require validated transaction responses. An APP hold must not fabricate completion, advance offsets before dequeue, retire descriptors, modify ACK/PSN state, or alter reliability/window configuration.

## Actual hybrid versus old PairV2Proxy

Old P:37–43 reserves undirected pairs and delays submission until group admission. P:68–83 AllReady and Limited select only the first member as leader and suppress original progress until all members are ready. This is genuinely collective eligibility gating. It is not the current candidate.

Actual H:40 keeps a proxy visible while native retained unacknowledged segments exist; H:147 otherwise limits it by its own native IsEmpty/IsLimited (apart from an explicit fault-injection timer). H:78–110 Choose first protects native priority, then requires exact full membership: native eligibility, REQUEST/task, offset, payload length/content, supported native header, codec association capacity, egress bytes, and CBFC cells. Failure returns a native-sized nonmerge choice. H:119–131 Pull either consumes the full matching native set through the codec or immediately calls selected tp->GetNextPacket. H:124 and 129 refresh proxies. There is no leader ownership, group reservation, submission barrier, or subset merge in this actual hybrid path. Old AllReady observation counts cannot be presented as actual hybrid waiting time.

H:136–139 preserves one registered RR slot per native pair in increasing target order. H:143 forwards receives to native switch processing before refreshing the associated proxy. H:133 records submission only; it does not schedule or defer SubmitWqe.

## Allocator commit and wakeup boundary

- A:507–557 FindNextEligibleIngressQueue checks IsEmpty, IsLimited, then flow control; it selects by existing native slot order. A:842–885 SelectNextIngressQueue advances RR cursor to the selected slot plus one.
- A:355–385 TriggerAllocator selects the active ingress at wake and schedules allocation; A:200–215 pays the normal AllocationTime. Keep the existing 5 ns setting unchanged.
- A:729–748 uses the proxy RevalidateOnCommit attribute to recheck empty/limited/flow-control. An invalid grant is cleared and a fresh normal allocation is triggered, rather than pulling an ineligible head. H:37–38 enables this contract.
- A:753–778 recomputes packet size, checks egress fit, pulls and enqueues synchronously. H:118–120 recomputes Choose for Size and Pull. Do not cache an envelope eligibility decision across events or return a fictitious size to force selection.
- A:827–832 only reruns an owned episode when runAgain and nonempty summary agree. A timed-out gate therefore needs an explicit wake, not merely setting a boolean: refresh summary and call port->TriggerTransmit. Native ACK enqueue triggers transmit (T:2318); sender ACK progress has its own wakes (T:1853–1874). Hold deadline must remain independent of receiving those events.

## Minimum safe candidate contract

These are requirements for a separate small prototype, not assertions that an implementation already satisfies them:

1. Keep L:393 and all native scheduling, admission, ordering, allocator slot registration, AllocationTime, tree, planner, chunks, windows, network, and reliability configuration unchanged.
2. Gate only an exact eligible current original REQUEST/WRITE belonging to a supported multi-member hybrid group. Key hold state to native TP identity plus task and full logical segment/range identity, not wire16 SSN alone. Never hold a singleton, unrelated/native fallback task, RESPONSE, already-sent work, or unsupported header/size.
3. Before any hold check, honor native CNP/transport-ACK/GBN priority and native IsLimited. Never force-send a limited retry or data head. Priority service must not reset/extend a hold deadline on the original head.
4. Fix a small absolute deadline once for that head. No repeated rearming, dependency-based extension, group barrier, reservation, waiting for ACK/TAACK, or indefinite all-members-ready wait. Bounded timer/storage counts and stale-event identity checks are required. Clear stale head state on head advancement and clean up timers on teardown.
5. At deadline, permanently remove APP inhibition for that head and expose normal native fallback. Native full-member matching may still merge if genuinely valid at commit. Do not promise actual wire service exactly at deadline. If offset mismatch means native heads cannot align by waiting, fail open immediately rather than burning the whole budget.
6. A ready full-member match may release early, but it must never bypass another member's earlier original. All actual consumption remains native GetNextPacket through the accepted codec/fallback paths; no vector scans to select later matching tasks, no PSN swapping, no pre-pulls.
7. Use existing commit revalidation and unchanged pure Size/Choose/Pull consistency. Timer-state changes belong in clearly owned APP events; do not make metric observers mutate readiness or restart timers on repeated queries.
8. Explicit expiry refresh/wakeup is mandatory even when every held member is idle and no network event occurs. A newly queued native priority packet must bypass hold immediately through the existing native wake and commit path.
9. Do not repurpose H:147 blockedUntil verbatim: that fault injector checks the time block before checking any native priority, so it can suppress ACK/CNP/GBN. It is a stale-grant test, not a safe coalescing design.

## Exact impossibility and stop conditions

- **Cannot restore alignment by violating same-TP order.** If one TP head is group B while another has group A before B, waiting cannot make the blocked earlier head disappear. A→B / B→A head dependence is broken only by timeout/native fallback, not by promotion, reservations, or forced merge.
- **Cannot promise unchanged ACK timing.** Priority transport ACK/CNP retain precedence, but shared-port contention and a TAACK RESPONSE behind held original work can still be delayed. Eliminating that delay by extracting a later RESPONSE changes native order and is outside scope.
- **Cannot promise identical allocator outcomes.** Skipping a held native-eligible slot changes effective selection. Unchanged allocator code and slot-order rule is a narrower, defensible claim; identical grant order is not.
- **Cannot prove performance gain from source audit.** A bounded hold may only add delay and native admission pressure. Static feasibility is not evidence of restored coalescing, lower latency, or better throughput.
- If the required interpretation disallows these timing/eligibility effects, stop with no prototype. If an implementation cannot guarantee one-shot expiry, priority bypass, exact-head identity and explicit wakeup without native modifications, stop instead of forcing a solution.

## Evidence status and permitted next gate

No small event trace was needed for these source-level distinctions, and none was invented. Prior fault-injection logic establishes an available revalidation mechanism in source, not a new observed pass. A future authorized small test would need bounded evidence for head identity/order, native-priority arrival during hold, TAACK-behind-WRITE distinction, expiry with no other wake, stale grant rejection, native-limited sibling, impossible cross-group head alignment, and clean drain. It must preserve payload/PSN correctness and use only tiny synthetic inputs; this report authorizes no execution. All forbidden large experiments remain unrun.

## Clarified bounded proposal and verified native wake path

The intended scope is unchanged native arbitration policy/cursor/slot order, not an identical realized grant trace. Under that interpretation, **a one-shot 5 ns APP-only eligibility hold is statically feasible without native modifications or direct ingress selection**, subject to the contract above. Restrict entry to a full fixed group whose per-member first-send offsets are still aligned, and whose merge failure is transient member absence or priority. Do not hold on wrong task/kind/offset, CC/window-limited member, size/header, association capacity, egress, or credit mismatch. An aligned accounting offset alone does not establish the peer's pending native head identity; if a different native head is visible, fall back immediately. No claim of measured safety or benefit follows before the bounded prototype checks.

Verified wake mechanics, not merely a suggested timer:

- `ns-3-ub/src/unified-bus/model/ub-port.cc:1068–1102` TriggerTransmit preserves link-down/output-blocked behavior; if BUSY with empty egress, it requests normal allocator prefetch; if idle with empty egress, it requests normal allocation; otherwise it dequeues already-enqueued work.
- `ub-port.cc:592–595` requests allocation when the egress queue becomes empty during normal transmission. Thus a deadline wake while egress is nonempty does not require selecting an ingress directly.
- A:389–391 ScheduleTriggerAllocator directly invokes TriggerAllocator. A:373–385 coalesces wakes during an active episode through m_runAgain, otherwise performs normal native PickNextIngressQueue and ScheduleAllocation. A:827–832 consumes the rerun flag after the current episode if nonempty ingress remains.
- Expiry must mark the exact head permanently spent/released before calling H:44 Refresh and port->TriggerTransmit. Refresh updates the registered proxy's summary; touching only the unregistered native TP summary is insufficient. The same-time ordering between expiry and an allocation callback is serialized by the simulator; if callback runs first and rejects, it follows A:734–748 revalidation; expiry then wakes normally. No zero-time callback loop or fresh hold for the same head is needed.

This design bounds the extra APP veto to one native 5 ns quantum. The ordinary allocation delay remains payable after wake, and no bound on total transmission latency is asserted. A held queue may be skipped by native RR, which is the expected effect of changed eligibility, not permission to edit RR policy, seed, cursor, priority, or registered order.
