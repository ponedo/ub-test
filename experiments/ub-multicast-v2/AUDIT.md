# Native WRITE source audit (before v2 edits)

Reference project: 1b35acbdc83226b90f39aeb5aad935425dec3a04. Native source: GitCode open-usim/ns-3-ub d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b plus accepted-unicast-baseline.patch, network-replication.patch, lightweight-adapter.patch (in that order). All 108 entries in ../ub-multicast-fanout-header/native-source-sha256.json matched after reconstruction. Initial audit-environment reconstruction commit: 42067a3. Final original dot host reconstruction is b8375b51a094d3b1217b697989e1ab979f609e64 with the same 108 verified source hashes. No simulator was run for this audit. Native paths below are relative to that reconstructed tree.

## Native bytes

`model/protocol/ub-transport.cc::GetNextPacket` (856) serves CNP, ACK and retransmission before new data. `SendNewDataPacket`/`BuildRtpDataPacket` (1043) use a native segment descriptor and advance native send state; the adapter must call this only after each child's `IsLimited` is false. `GetDataPacketHeaderBytes` (955) predicts the same rule-driven header plan.

Wire order for plain IPv4 RTP WRITE, without optional transaction fields:

| Component | Bytes | Construction |
|---|---:|---|
| UbDatalinkPacketHeader | 4 | BuildRtpDataPacket → UbDataLink::AddPacketHeader |
| UbIpBasedNetworkHeader | 6 | BuildRtpDataPacket, sender congestion hook |
| Ipv4Header | 20 | UbPort::AddIpv4Header |
| UdpHeader | 8 | UbPort::AddUdpHeader |
| UbTransportHeader | 16 | BuildRtpDataPacket, individual TPN/PSN/MSN |
| UbTransactionHeader BTAH | 8 | BuildRtpDataPacket, individual initiator/SSN |
| UbMAExtTah MAETAH | 16 | reverse traversal of UbTaHeaderPlan |
| Total | 78 | Native header excluding link = 74 |

Serialized lengths are defined in ub-header.h/.cc (DL 454, network 613, TP 1051, TA 1524, MA 2484), not sizeof(C++ object). IPv4 length is read from its serialized IHL. Transaction extensions are controlled by ub-transaction-rules.cc and ub-ta-codec.cc: plain WRITE permits optional UDETAH (4 bytes), so 78 is not a universal prefix. Other opcodes have other plans; BEETAH can be 8/16/32/64/128 bytes (transport parser seeds its size from MAETAH). They are outside this WRITE-only task. ACK/Response uses ATAH, not the WRITE request layout.

`UbSwitch::ResolveURMAOutput` (1099) invokes `GetURMARoutingKey`, then existing GetOutPort/GetOutPortForEndpoint (destination's low byte selects explicit-port behavior); it also preserves forced shortest-path updates. v2 must call this on each reconstructed native packet. Destination rank bitmap is not a substitute for routing. Receiver SinkTpDataPacket and ResolveInboundTp validate IPs, TPNs and priority.

## Tags: actual consumers

| Tag | Size (ns-3 serialization only) | Consumers and effect | Decision |
|---|---:|---|---|
| UbFlowTag | 8 | BuildRtpDataPacket creates taskId/wqeSize. ParseReceivedDataPacket reads it; BufferReceivedDataPacket (2242) puts flowId into inbound taskId; TrackInboundTaPacket (1190) puts it into the segment. ProcessInboundTaResponse (transaction.cc 2114) finds outstanding operation by originJetty/taskId. ACK/SACK/NAK tracing (transport.cc 1603/1653/1811/2058) also consumes it. ub-fault.cc::SetFault (664) selects task-specific faults. Atomic response parsing uses it to resolve request rule (1967; outside WRITE). | Not merely tracing. Preserve original task identity. No demonstrated receiver-local mapping from native WRITE wire fields to taskId; do not delete. |
| UbTransactionCorrelationTag | 42 | BuildRtpDataPacket attaches operation+segment resource identity (including generations). ParseReceivedDataPacket (2036) reads; TrackInboundTaPacket (1212) rejects inconsistent correlations and sets segment identity. BuildTransportResponsePacket (2073) copies it. Transaction response construction retains it; ProcessInboundTaResponse (2136) and RecordSegmentSuccess require exact operation/segment identities. | Required for native RTP lifecycle/response acceptance. No proven safe inference from SSN/TPN alone, especially generation reuse. Restore exact original simulator metadata. |
| UbExplicitPayloadTag | 1 | BuildRtpDataPacket marks actual supplied bytes. ParseReceivedDataPacket (2027) copies the remaining received payload only when marker exists, removes marker from that payload, then reassembly propagates explicit bytes into target execution. CTP has analogous consumers (ctp.cc 1524) but is excluded. | Required to expose actual WRITE bytes to native execution; removing it can silently turn explicit bytes into a size-only transaction. Restore marker, never payload from metadata. |

Outside RTP, LDST ParseRemoteRequest reads FlowTag into remote request flowId (ub-ldst-api.cc 373), and ACK receive uses it for tracing (532). CTP rejects TAACK without FlowTag (1365), uses it to construct response task identity (1421), and requires it for atomic operand sizing (1467); its explicit-payload marker is consumed at 1524. v2 does not intercept those paths. The audit searched the entire unified-bus source tree for all three class names; declarations, registration and tests were distinguished from execution consumers. No tag can safely be classified as log-only for this RTP WRITE path. None of their 51 bytes belongs to native wire accounting.

## Existing sharing and credit seams

SharedSource::IsLimited checks all active child emptiness/window eligibility; GetNextPacket repeats the barrier, calls native dequeue once per child, checks WRITE/task/payload and exact byte equality. v1 stores all native prefixes plus serialized tags in its wire envelope. Its optional oracle modes also store prefixes; v2 must not use that oracle to replace native wire headers.

Switch HandleNetworkPacket currently detects a PacketTag, copies a full envelope into every VOQ and retains one parent. NotifySwitchDequeue asserts branch size equals parent size. QueueManager MoveProcessingToNetworkBranches/PopNetworkBranch uses one byte count for both ingress and output associations. Allocator passes the dequeued branch to OnIngressReleased; CBFC rounds that packet's size to credit cells. Thus changing only branch bytes would return the wrong upstream credit. Required local refactor: retain input reservation size, track per-output native sizes, and return credit using the original input packet exactly once on final release. Existing unicast and v1 defaults must preserve their prior behavior.

The association mechanism may retain only original tags and an integrity binding to the actual native header, with finite capacity, single consumption, expiry checks and teardown drain assertions. Payload always comes from the envelope; native receiver and ACK/Response remain unchanged. This simulator metadata service is not modeled hardware group state and is not a UB standard mechanism.
