# Experiment A: semantic-preservation gate

Decision: **UNSUPPORTED_SEMANTIC_PRESERVATION**. Stop A before a runtime patch or
formal workload run. The bounded scheduler witness confirms a packet-order
counterexample to the minimal suppression, not a performance result.

## Proposed minimum change and why it fails

The candidate change was: perform the one existing native selection in
`TriggerAllocator`; when its result is null, clear `m_running` and omit the
`ScheduleAllocation` callback. Retain 5 ns for every selected grant, ordinary
revalidation, RR cursors, native TP queues, and all native dequeue/commit logic.
No additional `IsEmpty`, `IsLimited`, or flow-control probe is made.

A null selection is not merely an inert event. It reserves a 5 ns running
interval. Native arrivals inside that interval only set `m_runAgain`; completion
then selects across the accumulated eligible candidates. Clearing running
immediately instead selects on the first arrival, before later contenders are
visible. Both orders can be legal RR orders locally, but they are not the same
native scheduling semantics required by this experiment.

The native-linked unit witness uses the accepted `PairV2Proxy`, real native
`UbTransportChannel` ACK queues, native CBFC, native RR selection, proxy
revalidation, and native dequeue/egress enqueue. Each valid grant still takes
5000 ps. The port is configured at 3136 Gbps. The source has one physical output,
with A then B registered as two TP slots. Initial RR scanning starts before A.

| Common stimulus | Original callback | Minimal suppression |
| --- | --- | --- |
| t=0: no queue is eligible | Reserve null episode until 5 ns | Clear running immediately |
| t=1 ns: B becomes eligible; trigger | Set run-again | Select B, due at 6 ns |
| t=2 ns: A becomes eligible; trigger | Set run-again | Set run-again |
| t=5 ns | Null completion; native RR now selects A | B still selected |
| First native queue dequeue | **A at 10 ns** | **B at 6 ns** |

This is a **cross-TP, shared-source-port arbitration order** reversal, not an
intra-TP FIFO reversal or a demonstrated reliability failure. We apply the
user's strict native Packet order/original scheduling semantics boundary. If
only per-TP FIFO were intended, that narrower requirement would need a new
scope decision and its own proof; this witness alone would not refute it.

The first-packet reversal alone falsifies the strict order-preservation gate. Subsequent common
artificial t=20 ns wake drains any remainder: the full unit outputs are
A@10 ns, B@25 ns versus B@6 ns, A@11 ns. The late wake is a unit-test stimulus,
not a network timing measurement. The 6/10/11/25 ns values must not be presented
as LayerLatency, a physical WRITE result, or a predicted ablation speedup.

The fixture supplies synthetic ACK-queue packets with a real VL7 datalink
header. It intentionally captures the egress send through a fault sink instead
of exercising a wire, receiver, or complete TA transaction. It therefore does
not test physical WRITE correctness, loss recovery, or TA completion. Those
claims are not needed to falsify the earlier packet-order requirement.

The treatment hook is private test code, not a patched native runtime. Only the
external test triggers use the shortened path. Native internal reruns remain
unchanged in both variants, which is enough to expose the initial-order
counterexample. Commit observation reads queue sizes, never eligibility
predicates. No formal A case was run.

## Source anchors

Paths below refer to the accepted diagnostic native source snapshot. The
nine-file hashes are verified against the accepted diagnosis package's
`native-diagnostic-manifest.json`; the allocator SHA-256 is
`c841f37a5a8fe80d44a432eb6b76ea88fd9f42fbb285e18db7ff9e2057defe5b`.
The accepted delivery is b149fdd4d40d72791a84b788443b0450c41f6180; its prior
experiment control base remains 7041b595004dd02883478b288f3e7a48dbc625fb.

- `src/unified-bus/model/ub-switch-allocator.cc:110–114`: default allocation
  service is 5 ns.
- `:355–385`: a running allocator coalesces wakes via `m_runAgain`; it calls
  `PickNextIngressQueue` once, then schedules allocation even for null.
- `:188–215` and `:251–266`: the pending event owns the scheduling-work count;
  the callback later releases that count and dispatches `AllocateNextPacket`.
- `:507–557`: native eligibility scan uses `IsEmpty`, `IsLimited`, then CBFC;
  it scans queues in registration order while determining the RR candidate.
- `:708–748`: an allocator-owned null episode does not spontaneously select at
  callback entry. Proxy grants are revalidated; rejected grants trigger a fresh
  normal allocation episode, not a free commit.
- `:812–833`: the no-ingress outcome still clears active state, may notify the
  port, evaluates `allocatorOwnedEpisode && m_runAgain && HasNonEmptyIngress`,
  then starts a new episode. Removing this callback removes a scheduling boundary.
- `:836–888`: RR `PickNextIngressQueue` delegates directly to
  `SelectNextIngressQueue`; a successful selection advances the RR cursor.
- `:299–310`, `:641–664`: pending scheduling work also participates in lifecycle
  retention and output suspension. These obligations are not proved preserved
  by simply clearing `m_running`.
- `src/unified-bus/model/ub-port.cc:592–596,1068–1102`: dequeue and new work can
  trigger prefetch while a port is already busy. A null selection cannot promise
  that the next 5 ns will remain empty.

Accepted application source:
[`pair-multicast-v2.h`](../../multicast-reversal-diagnosis/pair-multicast-v2.h)
(SHA-256 `447f7e296bab4af1d3f97482161d4f7e35f82bb89785bf63a64fc779951bd44c`).

- `:59–62`: one registered native RR slot per pair, ordered by target.
- `:65–83`: ACK/CNP/retry priority, first-unsent group matching, and sequential
  member readiness preserve the original short-circuit order.
- `:85–94`: native TP control/retry dequeue remains the ordinary path; group
  dequeue and receive paths refresh proxies after their native work.
- `:100–108`: proxy nonempty is broader than current transmissible data. An
  outstanding unacknowledged segment or pending group keeps it nonempty even
  when its current native TP head is empty. Thus a nonempty summary is not an
  eligible-candidate proof or a complete readiness/wakeup subscription.

## Predicate side effects and wakeups

Do not try to repair the ordering witness by adding speculative eligibility
checks, polling, or an extra readiness pass.

- `protocol/ub-transport.cc:3042–3183`: ACK/CNP bypass precedes data-window/CC
  checks. Limited paths write `m_sendWindowLimited` at 3077, 3109, 3139, 3156.
  `:1865–1875` later consults that saved flag to decide a transport wake on ACK
  progress. A probe can therefore affect later behavior, not just diagnostics.
- `protocol/ub-dcqcn.cc:263–280`: `IsCcLimited` initializes sender state and can
  schedule a pacing wakeup. Active DCQCN is not the accepted formal workload's
  setting, but it invalidates a general claim that these predicates are pure.
- `protocol/ub-cbfc.cc:109–145`: CBFC queries can increment a blocked-query counter
  and change credit-blocked observation state. They also call the queue's next
  packet-size method; repeated/reordered predicates are not passive observation.
- `ub-ingress-queue.cc:90–103`: `RefreshAllocatorSummary` itself calls virtual
  `IsEmpty`. The native summary counts nonempty queues, not eligible candidates.
- The inspected native `IsEmpty` path (`protocol/ub-transport.cc:2937–2953,
  3022–3040`) and GBN/read-only head inspection do not by themselves advance PSN
  or dequeue. That narrower fact does not make the complete eligibility path
  pure. In particular, proxy `IsLimited` can invoke several native predicates,
  and its existing invalidation test seam can schedule events (`:101–106`).

The witness already fails with accepted-style CBFC and ACK-only eligible heads,
without requiring active CC or retransmission. We do not infer that TP/TA or
reliability was violated by the witness; rather, the packet-order gate fails
before such equivalence can be established. There is no valid basis to launch
formal A and label any resulting latency change causally clean.

## What this conclusion does and does not establish

The tested minimal callback suppression is not semantics-preserving. Both
formal A rows must remain unmeasured with status
`UNSUPPORTED_SEMANTIC_PRESERVATION`, not PASS and not failed performance.

This is **not** a proof that every possible optimization is impossible. A more
complex implementation might retain a logical reservation deadline, original
wake coalescing, lifecycle ownership, notifications, and same-time event order.
That requires a separate scheduler design and equivalence proof. It is outside
this minimal controlled intervention and has not been implemented or tested.
Replaying the same effective reservation also does not establish any simulated
latency reduction. The measured 5 ns × no-ingress count remains an accounting
quantity, not a removable-delay prediction.
