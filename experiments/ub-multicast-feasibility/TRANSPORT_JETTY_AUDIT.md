# ns-3-ub transport / transaction multicast feasibility audit

Read-only source inspection on 2026-10-18. No source modification, build, simulation, or test run. All source line references below refer to the recovered accepted-patch tree identified in `evidence/provenance.json`; paths are relative to that tree. Conclusions concern this simulator implementation, not a claim about the full UB specification or hardware.

## Provenance and scope

The initially expected `ns3ub-cost-audit` checkout is clean HEAD d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b, without the accepted completion patches. `real-batch-native` has the same HEAD plus working-tree changes reconstructed from accepted patches. Recovery record `qwen-real-batch-scaling/experiments/qwen-real-batch-scaling/results/build-provenance.json` pins native_target_source 2fde39d02920e639f5b200d0c5262a517326deb8 and reconstruction `tpn-jetty-index.patch`, `combined-native.patch`. Actual SHA256 matches the record:

- src/unified-bus/model/protocol/ub-function.cc a1de4e3dc60381bddc05fb467e55894ac8e2ce313ad72d3273ccf1f59692a86f
- src/unified-bus/model/protocol/ub-function.h fb809b9c6474f56e531545479df4f867c53e1e8735b6a0ab86d242b034abcec4
- src/unified-bus/model/protocol/ub-transaction.cc 9681014f1b571db9cce5e1584cef185966de9394118749a5bae9744296a32c6a
- src/unified-bus/model/ub-datatype.h e992fe3ee2e84c0bb6c7be61c752ff8953f0918d54290f2db5957f1ed567d254

Do not cite d6aa9e2 source line numbers as if they contained the current patched WQE completion behavior. The tree additionally has modified ub-transaction.h and tests; the full source-file manifest is retained privately on the cloud host and excluded from public artifacts. The outer project baseline and native working-tree hashes are recorded separately in evidence/provenance.json.

## Finding in one sentence

Switch packet replication alone is not one-to-many reliable WQE support: endpoint demultiplexing, TA/TP sequence windows, transaction identity, completion, and lifecycle cleanup are single-peer/single-segment-state contracts. An application-level group operation aggregating independent unicast children is the smallest reliable semantic baseline; it does not save network traffic.

## Submission, Jetty binding, segmentation

- `src/unified-bus/model/protocol/ub-function.cc`, UbFunction::SubmitWqe 155–241: looks up one Jetty, checks accepting state and CanAcceptWqe, validates transaction rule, resolves one RTP transport reference, rejects duplicate (Jetty,WQE), opens one lifecycle WQE, admits, PushWqe, AddWqe and schedules segments. No target-list argument.
- Same file UbJetty::CanAcceptWqe 1058–1072: requires WQE src == Jetty src; if HasBoundDest(), also requires WQE dest == Jetty dest. An unbound Jetty skips destination equality. This is evidence against saying every Jetty is necessarily single-peer, but not evidence of one WQE reaching multiple peers.
- `ub-function.h` 320–333, 427–447: one m_src, one m_dest (UINT32_MAX denotes unbound), one global TA sndNxt/sndUna and bitmap. No per-target completion bitmap here.
- `ub-function.cc` segment generation 1287–1378: one segment copies one WQE src/dest, optional src/dst entity, ports, IPs; writes Jetty number, next TA SSN, request identity, payload/response requirement and transaction rule. Explicit payload uses fragments; that is payload sharing, not fanout.
- PushWqe 1386–1424: resets actual-last-admitted SSN, assigns Jetty/MSN and reserved SSN count; initializes request origin; queues one WQE. Commit admission 1192–1236 validates next SSN, commits actual SSN and increments global TA next. Distinguish reserved count from actual admission order.
- `ub-transaction.cc` JettyBindTp 305–427: binds either one direct TP or one TP group, with optional multipath. TryAdmitRtpSegment 1218–1325 chooses ONE admissible member and breaks at 1301; TP-group membership is not a broadcast-all loop. This remains true even without proving every member must share one remote node.
- `ub-transaction.h` OperationRecord 618–645: operations keyed (jettyNum,wqeId), map<uint32_t,SegmentRecord> keyed TA SSN; record has one segment object, one resolved TP identity, one transport lease. No recipient dimension.

## Wire and receiver identity

- `src/unified-bus/model/protocol/ub-transport.cc` BuildRtpDataPacket 1043–1067: creates packet/fragment, flow task tag, optional transaction correlation tag. Packet copying preserves these identities unless explicitly rewritten.
- `src/unified-bus/model/ub-switch.cc` SinkTpDataPacket 819–881: first requires destination IP in local /24 subnet (825), otherwise returns false to forwarding; obtains src/dst TPN and resolves endpoint with source IP,destination IP,priority (839–848). RETIRED_EXACT is ignored; unresolved/mismatched key aborts (855–861). Both ACK and data use this endpoint gate.
- `src/unified-bus/model/ub-transport-channel-manager.cc` ResolveInboundTp 238–299: existing dstTPN must match the endpoint's expected remote TPN, source IP, local destination IP, and priority (264–272). Missing endpoint must resolve against a reserved connection, then materialize it. No wildcard group destination is established by these functions.
- `ub-transport.cc` TrackInboundTaPacket 1168–1223: TA reassembly keyed (srcTpn,logicalTpMsn); unwrapping TA uses (srcTpn,initiatorRcId). Reconstructed request src/dest come from the TP's m_dest/m_src, not an arbitrary list in packet. Correlation mismatch among packets for same inbound TA aborts. Target TP lifecycle identity is attached.
- `ub-transport.h` 698–746: one dstTPN, one IP pair, one sndNxt/sndUna, one receive PSN window and one retrans controller per TP. Inbound buffers keyed PSN and per-source MSN maps are not an all-target sender acknowledgment structure.

## ACK is not transaction Response

- `ub-transport.cc` RecvDataPacket 2353–2391 builds/enqueues transport ACK, then delivers complete TA units to transaction (CompleteInboundTaUnits 2334–2346). Therefore TP delivery progress does not inherently prove target execution success.
- BuildTransportResponsePacket 2066–2113 swaps IP direction and uses local m_tpn / bound m_dstTpn, echoes TA SSN/initiator id and correlation. It builds cumulative/selective transport acknowledgment, not group aggregation.
- AdvanceSenderAckFromPlainTpack 1689–1714 unwraps incoming PSN within THIS TP's sender window, advances a single sndUna, and releases retransmission progress. CompleteAckedWqeSegments 1732–1763 treats all segment PSNs below this frontier as ACKed. There is no B/C/D vote count.
- ShouldCompleteOnTpAck 1343–1360 returns false for response segments and for requests whose cached normalized rule requires a transaction response. Requests without such requirement may complete on TP ACK. Avoid blanket claims that every WQE completion always requires a transaction Response.
- `ub-transaction.cc` ExecuteInboundTransaction 1969–2007 and RunInboundTransaction 2011–2043 apply target delay once, invoke target executor/default scheduled success, guard callback against repeated calls, and build response. BuildTransactionResponse 2057–2100 returns null for unsuccessful outcome/protocol status (2062–2064), reverses src/dest, retains request identity/correlation. This audited path does not send a negative response for target execution failure.
- ProcessInboundTaResponse 2114–2177 resolves (originJetty,taskId), then requestTassn; for RTP checks reverse src/dest (2131–2134), exact operation/segment correlation (2136–2141), expected response opcode, role, atomic task id when applicable, and payload size. Then completes the segment.
- RecordSegmentSuccess 1859–1918 also checks exact correlation, exact resolved TP identity and active resource; releases leases and erases the segment record. ProcessWqeSegmentComplete 1921–1950 maps responses to origin Jetty/request SSN, calls RecordSegmentSuccess, then marks Jetty SSN. Duplicate response cannot be counted as another target: the segment record is already gone.

## Current patched WQE completion, exact predicate

`ub-function.cc` UbJetty::IsWqeCompleted 1629–1641 returns:

wqe->IsSentCompleted() && wqe->m_lastAdmittedTaSsn.has_value() && *wqe->m_lastAdmittedTaSsn < m_taSsnSndUna

This fixes concurrent/interleaved WQE SSN admission: reserved start+count is not a valid completion boundary. It preserves prefix completion, so all admitted Jetty SSNs through the WQE's ACTUAL last segment must have advanced below sndUna. It intentionally may wait behind earlier/interleaved SSN holes. It is not a count-of-targets test.

ProcessWqeSegmentComplete 1446–1505 rejects stale/future SSNs, marks the bitmap, advances the contiguous prefix and checks WQEs. CheckAndRemoveCompletedWqe 1518–1548 passes success through transaction WqeFinish. ApplyWqeTerminal 1567–1593 removes the WQE and emits general outcome callback; success-only observer/FinishCallback execute only for COMPLETED.

## Loss, timeout, cancellation, failure limitations

- `ub-transport.cc` HandleRepeatedDataPacket 2171–2201 responds to repeated PSN with current transport ACK/SACK and returns before transaction dispatch. This guards replay within the TP receive window; it does not establish durable idempotence across operation/TP reuse or explicit application retry under a fresh identity.
- ReTxTimeout 2394–2402 calls retrans OnTimeout and congestion rollback/transmit. `src/unified-bus/model/protocol/ub-retrans.cc` OnTimeout 1201–1225 decrements attempts, changes RTO, ASSERTS attemptsLeft>0, schedules timer and returns GBN/selective retry. No graceful FAILED WQE callback is present here. The macro is controlled by NS3_ASSERT_ENABLE (`src/core/model/assert.h:39,82–104`), not directly by NDEBUG. Do not infer safe bounded failure from an optimization/debug label. Underflow/reschedule concerns need future tests; not tested here.
- No transaction-level timeout occurrence was found by searching ub-transaction.cc. Absence of a timeout word alone is not proof that all external watchdogs are absent. A target executor failure currently yields null response; sender behavior after wire ACK without transaction response needs an explicit deadline/error contract for a reliable PoC.
- `ub-transaction.cc` FinishWqe 2647 onward cancels dispatch, detaches RTP queue, advances cleanup SSNs, checks exact TP generation, attempts unsent cancellation and retains some started work. CompleteWqeOperationForDrain 2889–2909 rejects external COMPLETED outcome, terminalizes and rechecks prefix completion after cleanup. Simulation-stop cleanup 2913–2949 forcibly removes exact retained segments and releases leases/resources.
- `ub-transport.cc` TryCancelUnsentWqeSegment 2449–2514 validates correlation/TP generation; already ACK-cleaned work returns TRANSPORT_CLEANED. Started sends retire retrans descriptors but remain RETAINED. Truly unsent suffix-compatible work is removed and later PSN/MSN allocation adjusted. ForceRemoveRetainedWqeSegment 2518–2554 is separate, retires descriptors, erases and cancels timer/retained state when empty. Do not reuse force-remove as a general network rollback without defining consequences.
- `ub-transaction.h`618–645 and lifecycle leases therefore need per-child ownership under a group, including late responses, cancel, endpoint teardown, and group epoch reuse. Cancel cannot undo target-side execution already performed.

## What naive A→B packet copying to B/C/D actually means

1. Unchanged destination IP and TPN: C/D normally do not sink locally; if forced into a local sink, connection mismatch can abort. Whether a topology happens to place nodes in one subnet changes the first gate, not the endpoint identity contract.
2. Rewrite only IP: TPN/remote association still wrong or unreserved. Correctly rewrite/register complete child endpoints: now ACKs return on distinct TP contexts for which the original sender has not admitted child state.
3. Bypass/rewrite responses to one common sender endpoint: first accepted cumulative ACK can release common packet state; later equal PSNs look duplicate/stale. That is false all-target completion, and congestion/loss feedback coalesces incorrectly.
4. At TA level extra targets fail reverse-address check. If that check is removed, first valid response consumes the sole (Jetty,taskId,SSN) record; later responses cannot count toward an absent target bitmap. Shared correlation cannot distinguish successful B from failed C; synthesizing new identities without sender records also fails validation.
5. Packet::Copy is legitimate for network fanout experiments, but preservation of payload bytes and count of sink packets does not prove exactly-once target execution, reliable recipient coverage, or group WQE completion.

## Minimal designs (proposals, not existing implementation)

A. Network-only PoC: explicit opt-in multicast envelope/tag or group route, switch replication, leaf/network sinks and counters. Exclude native WQE/TA/TP success claims. Keep normal unicast path untouched. Validate each intended recipient and zero unintended recipients, loop prevention, per-egress queue/backpressure/credit accounting, drops, edge bytes and packet copies. Network-specific files belong to the switch/network audit; transport core need not be falsely bent into multicast.

B. Reliable semantic baseline: an external GroupOperation freezes unique target list + epoch; submit one ordinary child WQE per target over existing valid unicast Jetty/TP binding. Aggregate actual typed child terminal outcomes into a per-target map and emit parent success exactly once iff every required child succeeds; expose failed target set and partial success. This requires no GroupJetty abstraction and leaves native unicast mechanics intact. A helper + tests + application integration may suffice for success-only baseline (rough design estimate 3–6 files); reliable target death needs a bounded failure/cleanup extension because existing retry exhaustion is not a dependable failure callback. This baseline transmits N unicast payloads; do not claim multicast network savings.

C. True shared-payload reliable multicast: explicit group operation id/epoch and recipient identity, stable membership snapshot, per-recipient TP/TA progress or well-defined equivalent, independent ACK/response association, target-selective retransmission, bounded timeout/failure transition and cancellation/lifecycle ownership. Parent completion must wait for all successful target Responses where rules require them; never first ACK. Preserve unchanged unicast path behind an opt-in type/API. Begin with idempotent write-like distribution only; read/atomics require additional result aggregation/exactly-once semantics and should be excluded initially. Existing unicast child contexts can serve as reliability legs, but a multicast wire/shared-send representation must explicitly reconcile per-child PSNs/MSNs and endpoint headers; simply introducing GroupJetty does not solve that.

Likely core surface for C: ub-datatype.h (group/member identity); ub-function.h/.cc (submission/optional wrapper, not necessarily change existing Jetty); ub-transaction.h/.cc (group/member correlation and completion/lifecycle); ub-transport.h/.cc (per-target wire progress); ub-retrans.h/.cc (target-specific retry/failure); ub-transport-channel-manager.h/.cc (group-aware demux if required); ub-switch.h/.cc and network/header/tag files (replication/routing); tests/build declarations. Estimate 10–18 production/header files plus 4–8 tests/config files depending on separation; high risk, not a measured effort quote. Network-only and reliable-PoC estimates must remain separate.

## Future acceptance gates (not run)

- Unicast parity: patched interleaved WQE actual-last-SSN completion; cleanup closes prefix hole; generation-stale responses rejected; ordinary TP ACK vs required target response unchanged.
- 1 target equals unicast; 3 targets all succeed; same payload byte-for-byte; parent completion follows slowest required target; single callback.
- Drop C data/ACK/Response independently; B/D remain completed and are not reexecuted/retransmitted unnecessarily; retry targets only C. Delay/reorder/duplicate responses, out-of-window PSNs and stale prior epoch responses.
- Target C death/executor failure produces bounded non-success with explicit failed/partial sets, no success and no hung lifecycle resources. Test assertion-enabled and release behavior.
- Cancellation before send, during partial send and after one target executes; late responses; endpoint/group destruction and recreation; no lease/timer/buffer leak; cannot promise rollback of executed effects.
- Receive-side idempotency for retries under same group/member/segment identity, including response loss. Fresh child resubmission after timeout must not silently apply atomics twice.
- Explicitly assert network savings only from measured shared-tree edge bytes; unicast aggregation baseline is semantics only.
