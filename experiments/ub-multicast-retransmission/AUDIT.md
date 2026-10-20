# Native retransmission source audit

Audited before edits at native b8375b51a094d3b1217b697989e1ab979f609e64, reconstructed from d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b plus the three accepted patches listed in ../ub-multicast-v2/README.md. v2 does not modify the transport/retransmission/transaction files cited here. All paths below start with src/unified-bus/. Line numbers refer to that fixed source (not future upstream main). Below, ub-transport.cc, ub-retrans.cc and ub-transaction.cc abbreviate model/protocol/<filename>.

## Implementation exists, but is off by default

model/protocol/ub-transport.cc:225–295 defines EnableRetrans=false, mode GBN, EnableFastRetrans=false. BaseRTO=25600ns, dynamic exponential timeout, factor1, maximum-attempt setting7. Consequently prior no-loss v2 results do not validate reliability. The old lightweight::SharedSource::Install also explicitly rejected an enabled retransmission child.

## Unconfirmed PSNs and replay data

- ub-transport.cc::SendNewDataPacket:809–817 constructs and retains a native descriptor; original sending alone advances segment progress and sndNxt in :774–795.
- ub-transport.cc::BuildGbnPacketDescriptor:696–741 retains logical PSN, packet offset, payload/progress/wire length, remote address/token, TA fields/SSN, TP MSN, first/last flags, correlation and explicit payload.
- ub-retrans.cc::UbRetransController::OnNewDataPacketSent:1354–1364 selects GBN or selective retention. GBN RetainDescriptor:30–35 uses logical PSN as key.
- UbGbnRetransStrategy::PrepareRetransmissionFromPsn:39–55 selects retained range [requested PSN, original sndNxt). TryGetNextRetransmissionPacket:79–92 calls native SendGbnRetransmission and advances cursor only after a packet is obtained.
- ub-transport.cc::SendGbnRetransmission/SendSelectiveRetransmission:821–837 use BuildRtpDataPacket:1043–1165. Same PSN/MSN (:1141–1142), TA identity, correlation and actual retained payload fragment. This is reconstruction, not cloning a cached serialized Packet: network congestion and DL/credit fields can differ. Do not require identical Packet UID or all wire bytes.

## ACK, window, and completion are different layers

- AdvanceSenderAckFromPlainTpack, ub-transport.cc:1690–1714, unwraps 24-bit ACK within logical [sndUna,sndNxt), advances sndUna=ACK+1 and acknowledges retained state. GBN AcknowledgePrefix, ub-retrans.cc:159–171, erases descriptors below new sndUna.
- IsInflightLimited/next-send gating, ub-transport.cc:635–650 and :2594–2599, uses sndNxt−sndUna. The nearby old comment saying unused is not evidence of absence; active callers exist.
- CompleteAckedWqeSegments:1732–1762 retires wire segments after cumulative ACK covers segment end. FinalizeTransportAckProgress:1790–1841 restarts timeout only when sndUna advances.
- ShouldCompleteOnTpAck:1343–1360 defers response-required request success. Incoming TA response must pass outstanding operation/segment, endpoint, correlation, opcode/role and payload checks in ub-transaction.cc::ProcessInboundTaResponse:2114–2177. Data reaching B is NOT proof A's WQE completed.

## Timeout, NAK, SACK

- ub-retrans.cc::StartTimerIfNeeded:1146–1164 starts only with enabled retained work. ScheduleTimeout:1108–1142 schedules native ReTxTimeout; RestartTimer:1167–1183 resets RTO/budget after ACK progress.
- OnTimeout:1201–1225 decrements budget, updates RTO, asserts remaining attempts >0, reschedules, invokes strategy. GBN timeout:245–257 starts replay at sndUna.
- Exhaustion is NS_ASSERT, not a graceful failed-WQE transition. With setting7 the seventh no-progress timeout asserts before that timeout's strategy call. Assertions must be enabled. Release-without-assertions behavior is not claimed safe.
- Optional fast GBN receive gap/NAK:216–241, sender selection:200–212 and :1250–1271. Selective state:301–368; SACK:607–673; selective timeout:588–603. Selective validation is outside this experiment.
- With fast GBN disabled, native receive-window code can buffer out-of-order data (transport.cc:2231–2261), so textbook GBN assumptions are not substituted for actual source behavior. Our principal PSN11 last-segment loss isolates one outstanding segment rather than claiming GBN is selective recovery.

## Physical transmit path and flow control

- ub-transport.cc::ReTxTimeout:2394–2401 calls native congestion rollback then TriggerTransportTransmit:504–508, which refreshes its allocator summary and triggers the source port.
- GetNextPacket:856–888 prioritizes CNP, ACK, native retry, then original data. A congestion-blocked retry does not fall through to new data.
- ub-switch-allocator.cc:675–700 checks real egress capacity, calls ingress GetNextPacket, EnqueueToEgress, then OnEgressEnqueued. Native replay therefore uses the ordinary physical port/queue/link path.
- ub-cbfc.cc:105–145 checks per-VL credit; :160–177 consumes/restores credit; allocator checks IsFcLimited at :478/:1069. Backpressure is not a dropped packet and never proves a retransmission occurred. CBFC does not maintain TP unacked PSNs or RTO. :148–156 prevents double-return for recovered forwarding buffers; it is not transport loss recovery.

## DATA loss versus ACK versus TA response

- Lost request DATA retains native descriptor and receives no progress until replay.
- Lost TPACK may cause original DATA replay; ub-transport.cc::HandleRepeatedDataPacket:2171–2201 regenerates ACK/SACK, and RecvDataPacket:2369–2370 returns before repeated TA execution. Same-PSN replay is deduplicated; arbitrary new-numbered application retries are not covered.
- TAACK is a transaction response carried as RTP DATA, not a TPACK. ub-transaction.cc:2093–2111 creates RESPONSE WQE segment and EnqueueRemoteRtpWqeSegment; reverse TP can independently retain/retransmit it. Both directions must have retransmission enabled.
- examples/ub-case-runner.cc:171–198 explicitly treats drop with disabled retransmission as unsupported and recommends enabling it or eliminating the loss.

## Minimal integration boundary

The new adapter only exposes existing native pending GBN retries individually and keeps wrapper scheduling discoverable while native unconfirmed work remains. It has no new ACK table, payload retry cache, retry timer, or failure/success state machine. Native timers still create replay work and trigger the port. First-send v2 encoding and metadata restoration are inherited unchanged. The test-only default-null sink callback runs after actual link delivery, normal CBFC return and endpoint validation and before native TP processing. Dropped transport deliveries model post-link loss after switch decapsulation, not corruption of CBFC/link frames. Duplicate injection repeats TP delivery of one actually received frame, not a second physical frame. These limitations must remain visible in conclusions.
