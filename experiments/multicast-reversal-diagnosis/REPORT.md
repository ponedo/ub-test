# Why multicast-v2 loses the 3136 Gbps weight-phase comparison

Diagnostic-only delivery based on accepted commit 7041b595004dd02883478b288f3e7a48dbc625fb.
Final v3 runs, exact parity, bounded evidence and independent scientific review passed.
No controlled intervention or strategy optimization was performed.

Reproduction: [README](README.md). Resources and regressions:
[validated summary](validation-resource-summary.json), [resource CSV](validation-resource-summary.csv).
All durations below are simulated time unless explicitly labeled host execution time.

## 1. Findings

The extra 164.289264 µs has accumulated **by the final source dequeue**. The final
packet suffix does not explain the gap, and multicast uses less source
serialization service. The source that becomes terminal, node 3, spends more
elapsed time with allocation pending and has substantial uncovered idle. Its
last source-dequeue-to-receiver-ready path is actually 0.464 ns shorter than
either tied chunk final path. That roughly 53 ns suffix does not rule out earlier
downstream queue, CBFC, or feedback delays affecting later source eligibility.
Indeed, corrected FIFO measurements show **substantial earlier VOQ contention
on switch egress 59**: MC weight residence averages 267.050 ns, maximum 2.565 µs,
versus Chunk 8.830 ns and 48.285 ns. It can delay earlier traffic and feedback;
its overlapping packet-time sum is not additive to the 164.289264 µs gap.

The exact elapsed-resource accounting is established. A complete causal split
between ACK/control competition, null allocator callbacks, rejected selections,
and indirect WQE/TA admission or notification pacing is **not uniquely established**.
In particular, 91.534728 µs of uncovered source idle is not automatically an
AllReady wait. V3 directly identifies 34220 no-ingress callbacks and 789 rejected
callbacks on source 3 during the weight phase; neither count is an additional
wall-time component to add to the exact partition.

A representative cycle does identify a concrete admission mechanism through
audited reconstruction: the separate **512-TA Jetty window is full**, although
the TP's **1000-packet window is not full**. An earlier TAACK arrival immediately
admits more original work. This proves the bounded mechanism, not its share of
all 91.534728 µs of idle.

The exact accepted full LayerLatency also remains unchanged:

| Strategy | Full LayerLatency (ps) | Weight phase (ps) |
| --- | ---: | ---: |
| Chunk-Streaming | 732284971 | 552893591 |
| Multicast-v2 | 898435170 | 717182855 |

## 2. What was held fixed and what was checked

- Same accepted real workload, routing, Planner, roofline Compute, topology,
  3136 Gbps link rate, native network parameters, and strategy implementations.
- Separate diagnostic native/application copies; only passive observations.
  No scheduling/protocol intervention, extra predicate probes, injected ACKs,
  altered windows, changed link rate, or compute-model substitution.
- Small accepted/default-OFF/ON gates cover all four strategies at 100 and
  3136 Gbps, exact event timestamp/order parity, validation negatives, selected
  network fault smokes, and compatibility checks. Formal real runs comprise
  only Chunk-Streaming and multicast-v2 at 3136 Gbps.
- Both v3 formal cases passed the entire accepted online summary excluding only
  host verification wall time, and byte-identical ordered expert-compute,
  expert-ready, and replica-ready files. Source, input, executable, and native
  library identities are frozen and checked.
- Stage A PASS and both formal ledger cases PASS were checked before analysis.
  All seven queue/outcome integrity counters are zero in each run; no unmatched
  VOQ/egress ends remain. Whole-run allocation starts equal the sum of direct
  rejected, no-ingress and successful outcomes on every observed port.
  The checks establish exact accepted parity, not merely similar latency.

The native configuration is not an assumed modern network default. The accepted
application already binds transport CC off; CBFC remains enabled. Native RR
allocation service is 5 ns, and the observed final-packet explicit TX delay is
zero. The 3136 value is Gbit/s, not GB/s. Source references: [S1–S4].

## 3. True last-WeightReady dependencies

| Strategy | Actual terminal receiver dependency | Receiver-ready time (ps) |
| --- | --- | ---: |
| Chunk | Expert 73, task 69657, source 36 → target 17, physical 70 | 553094591 |
| Chunk, tied | Expert 100, task 69670, source 50 → target 27, physical 110 | 553094591 |
| Multicast | Expert 7, task 32814, source 3 → target 59, group 8 | 717383855 |

All three terminal transfers cover a full 18 MiB at offset zero and have no
relay dependencies themselves. Other chunk transfers do use relay dependencies;
this statement is deliberately limited to the actual terminal tasks. Target
coverage completion drives physical WeightReady, and the final physical
WeightReady drives weights_end. Sender completion is a different event. [S5]

For multicast group 8 the members are 5, 13, 52, and 59. Task 32814 sender
completion is at 776120728 ps, **58.736873 µs after WeightReady**. Charging this
later ACK/response cleanup to the weight critical path would be wrong.
**This does not make all ACKs irrelevant:** earlier TAACKs during the 18 MiB
transfer release the 512-TA admission window and can be critical. Only the final
sender-completion tail after receiver WeightReady is excluded from this path.

## 4. Exact critical-source accounting

Each source prefix begins at weights_start = 201000 ps and ends at that
critical source's last native weight dequeue. The selected source port is 0.
TX-busy union, allocator pending excluding TX, and uncovered idle are disjoint.
The suffix from final dequeue to target ready is added once.

| Component | Chunk terminal source 36 or 50 (µs) | MC terminal source 3 (µs) | MC − Chunk (µs) |
| --- | ---: | ---: | ---: |
| TX-busy union | 164.167221 | 74.894265 | −89.272956 |
| Allocation pending, excluding TX | 388.672779 | 550.700735 | +162.027956 |
| Uncovered idle | 0 | 91.534728 | +91.534728 |
| Final dequeue → receiver ready | 0.053591 | 0.053127 | −0.000464 |
| Total weight phase | 552.893591 | 717.182855 | **+164.289264** |

The two chunk ties independently give this same identity. The arithmetic
residual is exactly zero ps. That means elapsed time is resource-accounted;
it does **not** mean 100% of the causal mechanism is proven. The 91.534728 µs
idle cause remains partly unresolved. The +162.027956 µs allocation-only change
also includes changed overlap with TX. Multiplying rejected grants by 5 ns and
adding the result to that column would double-count overlapping service.

TX busy is not synonymous with pure serialization: it uses actual completion
occupancy, including applicable IFG/NOB. Pure serialization is reported
separately from explicit delay and busy duration. [S3–S4]

A second exact identity combines TX and allocation-only into their measured
union. V3 independently counts the callbacks, rather than inferring them from
an integral quotient. Chunk has 110579 phase-start callbacks minus 11 retained
starts at/after its last dequeue: **110568 prefix callbacks**. Multicast has
125128 minus nine: **125119 prefix callbacks**. Each observed service is 5000 ps;
no callback crosses either prefix cutoff. With one pending callback per port
and no pre-weight work, their nonoverlapping service sums equal the independently
measured unions, 552840000 and 625595000 ps. Hence:

**14551 extra scheduled callbacks × 5 ns + 91.534728 µs uncovered idle
− 0.000464 µs final suffix = 164.289264 µs.**

The same prefix callbacks can be classified by their actual outcomes, excluding
all retained outcomes strictly after the last dequeue, while retaining the
commit at the cutoff whose callback began before it:

| Prefix outcome | Chunk terminal source 36 or 50 | MC terminal source 3 | MC − Chunk service (µs) |
| --- | ---: | ---: | ---: |
| Successful commit | 110568 | 90115 | −102.265 |
| No ingress | 0 | 34215 | +171.075 |
| Revalidation rejected | 0 | 789 | +3.945 |
| Total callbacks | 110568 | 125119 | **+72.755** |

This uses observed counts, not starts-minus-commits inference. For MC, the
phase-end cohorts lose three post-cutoff commits and five no-ingress outcomes;
for each tied Chunk source, six commits and four no-ingress outcomes are after
the cutoff. No rejection is after the cutoff. The direct prefix outcome totals
independently equal the prefix start counts above. The service interval remains
5 ns, but the number and kind of scheduled callbacks differ substantially.

This is measured union accounting, not an intervention-derived speedup from
removing callbacks. TX is already inside the measured allocation union in these
prefixes; adding serialization again would double-count it.

## 5. Same physical resources, separately controlled

The preceding table follows the actual terminal source, which changes between
strategies. It must not be presented as a same-node controlled comparison.
The same-resource controls below compare source port 0 on nodes 3, 36, and 50
in both strategies, using each source's own last native weight dequeue.

| Physical source | Chunk last dequeue (ps) | MC last dequeue (ps) | MC − Chunk (µs) |
| --- | ---: | ---: | ---: |
| 3 | 368721000 | 717330728 | +348.609728 |
| 36 | 553041000 | 544089370 | −8.951630 |
| 50 | 553041000 | 544089370 | −8.951630 |

For the same source 3, the chunk prefix is 109.442613 µs TX + 259.077387 µs
allocation-only + zero idle. Multicast is 74.894265 + 550.700735 + 91.534728 µs.
Its same-source slowdown is therefore −34.548348 + 291.623348 + 91.534728 µs.

The bottleneck shifts to source 3. An equivalent global timing identity is:
348.609728 µs source-3 slowdown − 184.320000 µs of source 3's preexisting slack
behind chunk's terminal sources − 0.000464 µs suffix difference = 164.289264 µs.
This is another timing identity, not an additional causal explanation.

Whole-phase tables also retain the same physical switch egress ports 17, 27,
and 59 in both strategies. Corrected FIFO VOQ cohorts are:

| Egress / traffic | Chunk count / mean / maximum (ns) | MC count / mean / maximum (ns) |
| --- | ---: | ---: |
| 17 or 27 / weight | 18432 / 7.477575 / 9.845 | 18432 / 5.000000 / 5.000 |
| 17 or 27 / ACK-response | 18425 / 7.184162 / 9.845 | 18432 / 5.000000 / 5.000 |
| 59 / weight | 36864 / 8.830263 / 48.285 | 36864 / 267.049552 / 2564.612 |
| 59 / ACK-response | 36864 / 9.266739 / 50.938 | 36352 / 22.943904 / 1920.158 |

Thus earlier VOQ contention on egress 59 is substantial, unlike egresses 17/27.
The MC weight-residence sum there is 9844514699 ps across 36864 packets; it is
**not** 9.844515 ms of additive critical delay. These are full-residence cohorts
whose ends fall in the weight phase, not clipped occupancy. Egress-queue waits
are zero for both traffic classes on all three selected ports. VOQ residence
includes overlapping allocation service and can affect earlier feedback; the
short final forward suffix does not exonerate that earlier contention.

Beware post-completion idle: chunk source 3's last dequeue precedes global
WeightReady by 184.373591 µs; multicast sources 36/50 precede their global end
by 173.294485 µs. Those endpoint differences are not measured eligibility
waits and are not all idle, since physical TX can continue after dequeue.
Strategy workloads on the same port also differ; these resource controls are
not a controlled protocol intervention.

## 6. AllReady: exclusive primary observations, not continuous waits

The adapter preserves its original short-circuit order. At each actual query
only the first failing member/reason is recorded. Hidden later-member conditions
are not re-probed. Group 8 has the following complete query aggregates:

| Primary member / reason | Actual evaluations | Observation spans | Held-span sum (µs) | Maximum held span (µs) |
| --- | ---: | ---: | ---: | ---: |
| 13 / ACK priority | 18461 | 17920 | 89.600000 | 0.005000 |
| 13 / empty | 1 | 1 | 0.005000 | 0.005000 |
| 52 / ACK priority | 17920 | 17920 | 89.600000 | 0.005000 |
| 59 / ACK priority | 17976 | 17728 | 126.805000 | 0.010000 |
| 59 / empty | 3086 | 550 | 18.666576 | 2.780000 |
| All ready | 75058 | 10673 | 392.453152 | 10.351576 |

There were 18432 actual representative grants, first at 211000 ps and last at
717330728 ps. ACK-priority failures total 54357 evaluations; empty failures
total 3087. No inflight, CC, CNP, or retry primary failures were recorded for
this group. These observations support control/empty-head interference, but
their held durations are not continuous ACK or empty waits. They must not be
added as causal durations to the resource table, across groups, or across ports.

An observation may stay READY while no new query occurs. The next section
provides an actual example. Thus even perfectly exclusive observation labels
cannot fill the unknown causal portion of a measured idle interval. [S6]

## 7. ACKs, packet windows, Empty, and indirect admission

Source 3's whole-run native limited-query reasons are ACK 335321 and Eligible
877674, with no recorded Inflight or CC branch. This describes branches that
were actually evaluated, not a proof that every admission mechanism is absent.
CNP is also inactive in this accepted configuration because native transport CC
is already disabled. It remains distinct from CBFC link credits. [S1, S7]

A TP's sndNxt − sndUna is sequence-space outstanding work, not physical source
wire bytes. The saved sendWindowLimited flag can be stale; use the actual
TpLimited branch, not the flag, to identify tested packet-window blocking.
Queued ACK/CNP traffic bypassing the limiter does not make new data eligible.

### A publication-safe representative cycle

Only this short selected cycle is a candidate for the public timeline; the raw
65,536-event rings and full per-node/per-expert files stay private.

| Time (ps) | Selected observation |
| ---: | --- |
| 717265728–717280728 | Four members' latest completed reverse-response frontiers are each 17919. |
| 717295728 | Members 5,13,52 observed empty; sndNxt and admitted count 18431, sndUna 17920. A 5 ns allocation starts. |
| 717300728 | Member 59 has the same empty snapshot; prior allocation ends. |
| 717305728 | Member 5's next TA response advances reverse frontier 17919 → 17920; a WQE-segment enqueue follows at the same timestamp. |
| 717305728 | Admitted count advances 18431 → 18432; the next allocation has started at this timestamp. |

This **v3-retained** 5000 ps allocation gap is associated with actual empty and
TA-response observations. The 511 outstanding packet positions are below the
1000-packet cap: this is not an observed direct packet-window stall. It does
not prove zero ACK dependence. The packetless WQE-segment enqueue occurs after
the response-after event in recorded same-timestamp order. The allocation start
itself precedes that response-after event, so it must not be described as caused
by the later WQE enqueue.

`HasPendingTransmitWork` can be false when all **admitted** packet work has been
generated even though many packets remain unacknowledged. Retained WQE segment
capacity, shallow active-send capacity, TA/jetty admission, cleanup, and ordering
are independent gates. ACK and send completion can retry admission. The trace
does not identify the gate throughout all 91.534728 µs of source idle, but the
specific bounded cycle above can be narrowed further. [S8]

### Separate 512-TA Jetty window: reconstructed in this bounded cycle

The native Jetty has a **512 outstanding TA-segment** limit, distinct from the
1000 outstanding-packet TP limit. Its `IsLimited` compares TA SSN next minus
TA SSN unacknowledged; transaction continuation returns while that gate is full.
PairJettyManager changes segment size and callbacks, not this default. [S10]

For this selected cycle, all four members' latest successful reverse-data
receive counters are 17919, while admitted request packet count and sent count
are both 18431. The TA reconstruction is 18431 − 17919 = **512** outstanding
TA operations. Meanwhile TP transport ACKs have reached 17920, so the request
TP packet window reports only 511 outstanding positions. These are different
acknowledgments and different limits.

At 717305728 ps, source 3 receives member 5's next TA response: the reverse
receive counter advances 17919 → 17920. A new WQE-segment enqueue immediately
follows **at the same timestamp**, and admitted TP packet count advances
18431 → 18432. This proves a representative TA-response-driven Jetty admission
cycle through audited reconstruction, not the direct TP packet-window gate.

This is **not a direct sample of Jetty SSN fields**. The required invariants were
checked: TA segments are 1024 bytes and fit the 4096-byte native MTU; each WRITE
TA sends one request packet and requires one single-packet TAACK response;
TA/TP counters start at zero; these pairs have only their single forward weight
WQE and no reverse application weight request; dispatch/combine traffic is gated
until weights finish; reroute is a timer, not earlier traffic on those pairs;
no loss/retransmission is enabled in the formal case. Successful contiguous
responses complete the matching origin Jetty and retry continuation. No
unrelated pre-weight or reverse-request count is silently treated as a TA response.

Response ordering is also necessary; one packet per TA alone would not equate
a response count to the contiguous completed SSN frontier. Here the adapter
checks each member's TA offset against monotonically advancing group sent bytes.
Native receive delivers completed TA units in contiguous PSN order. The target
executor completes synchronously: native execution delay and application weight
completion/reorder/slow-relay delays are all zero. TAACKs are enqueued into the
single operation's response FIFO and consumed from its front. Reverse native
receive again processes contiguous PSNs; each correlated TAACK completes its
origin Jetty SSN. There is no formal cancellation or cleanup gap. These audited
ordering invariants justify equating the observed reverse frontier 17919 with
the contiguous completed TA frontier in this specific reconstruction. [S12]

Do not extrapolate this selected 5 ns allocation-gap cycle to classify every
picosecond of the global 91.534728 µs uncovered idle. Downstream queueing can
delay earlier responses and thereby affect source pacing even though the final
forward packet's suffix is short.

## 8. Allocation: actual callbacks versus successful grants

The 5 ns configured interval is real scheduled service. It is not the elapsed
waiting time of every packet and does not imply equal wall-time across strategies.
In the v3 weight-phase start cohort, source 3 has 125128 starts, with full
requested service sum 625640000 ps; either tied chunk source has 110579 starts
and 552895000 ps. The matching end-event outcomes are directly observed:

| Resource / strategy | Successful callbacks | No ingress | Revalidation rejected |
| --- | ---: | ---: | ---: |
| Source 3 / Chunk | 73728 | 22 | 0 |
| Source 3 / MC | 90118 | 34220 | 789 |
| Source 36 or 50 / Chunk | 110574 | 4 | 0 |
| Source 36 / MC | 73764 | 19438 | 0 |
| Source 50 / MC | 73764 | 19437 | 0 |

All measured outcome durations in this table are 5000 ps. Source 3 MC successful
callbacks comprise 18432 weight, 71683 ACK/response, and three other callbacks.
Its no-ingress service sum is 171100000 ps, and rejected service sum 3945000 ps.
The vast majority of its no-commit callbacks are therefore **no ingress**, not
stale selection rejection. By comparison, Chunk source 3's successful callbacks
split evenly between 36864 weight and 36864 ACK/response callbacks.

Start and end cohorts differ at phase boundaries: source 3 MC has 125128 starts
but 125127 observed phase-end outcomes; tied Chunk has 110579 vs 110578. This is
not a missing-event error. Whole-run start/outcome counts reconcile exactly on
every port, and all open/mismatch counters are zero.

Source code supports two different no-commit mechanisms:
1. A preselected coordinated proxy becomes ineligible on commit revalidation;
   the old selection is rejected and normal allocation is retried.
2. TriggerAllocator schedules a callback even when PickNextIngressQueue selected
   no queue. The callback can end without a packet and without stale rejection.

Direct v3 GrantRejected and GrantNoIngress events distinguish these existing
branches without extra eligibility probes. Their measured elapsed durations
are **not additional durations** to add to the disjoint resource partition.
NoIngress also occurs in ordinary chunk switch scheduling, for example 50021
callbacks on each of egresses 17/27; its mere existence is not multicast-specific.
The same-source differential is the meaningful control here. [S2–S3]

The accepted proxy explains how nonempty scheduler summaries can coexist with
no eligible native work: `Proxy::IsEmpty` returns true only if the underlying
TP is empty, there are no unacknowledged segments, and no pending group remains.
It therefore reports nonempty while pending-group or outstanding work remains,
even when the native TP has no admitted packet to send. Conversely, the adapter's
`Limited` returns limited immediately for a native-empty TP. Together with
unconditional callback scheduling after a null pick, this supports extra
no-ingress callbacks on notifications as a candidate mechanism. It is not a
claim of infinite polling or that every callback was null. Direct outcomes now
corroborate substantial no-ingress service, but do not identify a unique predicate
for every absent ingress or classify every uncovered idle interval. [S11]

## 9. Serialization savings and nonuniform bandwidth scaling

In the weight-phase service-start cohort, multicast source 3's stage-2 pure
serialization is 63.571968 µs versus 155.437056 µs at either tied chunk source.
ACK/response serialization is 11.325914 versus 8.733924 µs. This is supporting
service-demand evidence, not a standalone causal latency decomposition.

For the observed packet sizes, 1102 bytes take 88.16 ns at 100 Gbps and about
2.811 ns at 3136 Gbps; a 1352-byte envelope takes 108.16 ns and about 3.449 ns.
The 5 ns allocation service does not shrink with link rate. At high bandwidth,
allocation and eligibility timing become large relative to serialization, so
packet savings need not translate monotonically into receiver readiness.

This is source-supported dimensional explanation, not a new 100 Gbps real-case
diagnostic result. No new real 100 Gbps diagnostic, bandwidth sweep, or controlled
intervention was run to prove the crossover mechanism. Small 100 Gbps cases are
parity gates only. [S3–S4]

## 10. Last-packet path: measured, not estimated from averages

| Disjoint suffix component | Chunk, either tied path (ps) | MC path to 59 (ps) |
| --- | ---: | ---: |
| Native dequeue → source TX start | 0 | 0 |
| Source serialization | 2811 | 3449 |
| Source explicit delay | 0 | 0 |
| Source TX end → fabric RX | 20000 | 20000 |
| Fabric RX → branch TX | 7969 | 6867 |
| Branch serialization | 2811 | 2811 |
| Branch explicit delay | 0 | 0 |
| Branch TX end → target RX | 20000 | 20000 |
| Target RX → receiver ready | 0 | 0 |
| Total | 53591 | 53127 |

Final egress waits are zero in the retained packet instances. Actual callback
start-to-successful-commit intervals are all 5000 ps: Chunk sources 36/50
553036000→553041000; their fabric ports 17/27 553066780→553071780; MC source 3
717325728→717330728; fabric port 59 717356044→717361044. These physical-port
callback pairs are observed directly in v3, independently of UID reuse.

The analyzer separately leaves some **queue-selection** start intervals unknown;
callback start must not be relabeled as first queue-selection time. The transport
path, final VOQ residence and callback intervals are retained, but complete
queue-selection history is not claimed. VOQ residence overlaps allocation and
must not be added again to fabric RX→TX. [S3–S4, S9]

## 11. Observer defect, correction, and evidence limits

The first observer keyed VOQ starts by queue and packet UID. Native packet copies
and fragments reuse UIDs; simultaneous same-key pushes overwrote start times.
Complete small-case traces prove six matching collisions/unmatched pops in one
chunk fixture and one in a singleton fixture. The formal chunk records 12204
unmatched VOQ pops, including 10299 in the end-in-weight-phase cohort.

Those v2 VOQ residence aggregates are incomplete and must not support causal
claims. FIFO matching by enqueue occurrence, with UID/order/depth checks, was
validated by the corrected v3 rerun. Both runs have zero open FIFO records,
unmatched pops, order errors and depth errors; the three grant integrity
counters are also zero. The simulator's accepted outputs remained
exactly identical; the defect was in observation bookkeeping, not simulation
behavior. Direct activity partitions, TX service durations, and the carefully
selected final packet occurrence intervals do not rely on that map.

One v2 switch-port row, node 64 / port 41, was inserted at or after phase end
with a zero total despite nonzero stated bounds. It is excluded as unmeasured,
not manufactured into idle. V3 prevents this post-phase insertion.

Each tail is intentionally bounded at 65536 records and the weight-tail is frozen
at WeightReady. Overwritten early history is unavailable. UID alone is not a
unique wire-packet identifier; selection follows the final RX and its latest
preceding per-hop occurrence, including explicit envelope-parent/branch linkage.
There is no claim of complete run history.

**Remaining causal uncertainty:** the exact 91.534728 µs uncovered-idle total is
measured, but its complete cause-by-cause split is not. The selected Jetty512
cycle proves one mechanism; corrected VOQ cohorts show earlier destination59
contention, not a unique wall-time attribution through every response. No
intervention was performed. One may be proposed separately if a counterfactual
speedup is required; it is not needed merely to close the arithmetic table.

## 12. Source references and selected evidence

Line anchors refer to the diagnostic source snapshot. The reproducibility
manifest records the frozen v3 source and build identities; full detailed
evidence remains private.

- **[S1] Configuration:** `layer.cc:233–240,287,340`; accepted
  `bandwidth-work/experiments/qwen-roofline-compute/layer.cc:284` already disables
  transport CC. Native `ub-switch.cc:61–80,211–225` supplies CBFC and native RR.
- **[S2] Callback scheduling and outcomes:** native `ub-switch-allocator.cc:188–218,
  251–266,355–385,708–835`; v3 rejection observation at 737–744, no-ingress
  observation at 812–818. These observe existing branches without extra probes.
- **[S3] Eligibility and allocation:** native `ub-switch-allocator.cc:110–114,
  507 onward,842–892`; `ub-port.cc:1068–1105` permits allocation/TX overlap.
- **[S4] Egress and actual link timing:** native `ub-port.cc:94–134,526–552,
  829–903,944 onward,1108 onward`; `ub-ingress-queue.cc:148–211` provides FIFO
  push/pop. Do not substitute head-arrival bookkeeping for enqueue residence.
- **[S5] Weight dependency:** application `layer.cc:Ready/FinalWeight` around
  393–417; exact transfer graph and diagnostic-transfers contain dependency,
  offset, coverage, receiver-ready, and separate sender-complete boundaries.
- **[S6] Collective predicate:** `pair-multicast-v2.h:68–92`, plus diagnostic
  `Query/Close/Grant`; original first-failure and member ordering are preserved.
- **[S7] Window and ACK semantics:** native `protocol/ub-transport.cc:789 onward,
  881–940,1764–1790,1841–1865 onward,1924 onward,2863–2869,3042 onward`.
- **[S8] Empty/admission distinction:** native `protocol/ub-transport.cc:40,
  260–264,811–812,1806–1838,2712–2715,2826–2860,2917–2950,3022–3040`;
  `protocol/ub-transaction.cc:823–891`.
- **[S9] Envelope/branch boundaries:** native `ub-switch.cc:2122 onward,2240–2312`.
- **[S10] TA window and reconstructed cycle:** native
  `protocol/ub-function.cc:1025–1029,1201–1236,1446–1510`,
  `protocol/ub-function.h:292–300,345–347,434,445–446`,
  `protocol/ub-transaction.cc:823–841,1921–1950,2057–2100`;
  `protocol/ub-transport.cc:50–52,2512–2525,2644–2660`;
  `ub-datatype.h:40` (4096-byte MTU);
  application `../pair-jetty/pair-jetty-manager.h:18–36` and
  `layer.cc:437–449` (dispatch gate and timer-only reroute).
- **[S11] Proxy versus native emptiness:** `pair-multicast-v2.h:80–83,100–108`;
  native `ub-switch-allocator.cc:355–385,488 onward,827–835`.
- **[S12] Reconstruction ordering invariant:** adapter `pair-multicast-v2.h:77`
  offset alignment; native `protocol/ub-transport.cc:2403–2465,2512–2525`;
  target executor `layer.cc:312–332`; native
  `protocol/ub-transaction.cc:208–212,1485–1548,2009–2045,1921–1950`;
  `protocol/ub-function.cc:1446–1510`. Formal config sets weight completion,
  reorder, and slow-relay delays to zero.
- Detailed source audit: [source-audit.md](source-audit.md).
- Timing and resource accounting: [gap accounting](results/gap-accounting.csv),
  [callback union](results/prefix-callback-union.csv),
  [boundary-corrected callback outcomes](results/prefix-outcome-decomposition.csv),
  [same-resource partitions](results/same-resource-partitions.csv).
- Selected measured cohorts: [same-resource aggregates](results/same-resource-selected-aggregates.csv),
  [allocation outcomes](results/allocation-outcomes.csv),
  [AllReady group 8](results/allready-group8.csv).
- Bounded critical evidence: [three terminal transfers](results/weight-timeline.csv),
  [72 critical-path events](results/selected-critical-events.csv),
  [six final callback intervals](results/final-allocation-intervals.csv),
  [14-event Jetty512 cycle](results/selected-jetty-512-cycle.csv).
- Figures: [critical-source accounting](figures/critical-source-accounting.png)
  and [weight timeline](figures/weight-timeline.png).
- Both formal ledgers, complete validation records, ordered per-expert/per-replica
  parity evidence, full bounded native rings and private analysis remain private.
  Only the necessary aggregate and narrowly selected timeline evidence is included.
