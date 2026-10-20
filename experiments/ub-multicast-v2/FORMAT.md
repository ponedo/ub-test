# Experimental WRITE v2 format and ownership

This is a simulator research extension, not a Huawei/UB-standard multicast protocol.

Outer UbDatalinkPacketHeader: 4 bytes, VL/routing retained, experimental Config=0xF. Detection uses this actual serialized field; the switch then validates magic/type and version. Native unicast branches use Config=PACKET_IPV4=3. No selection PacketTag is required on source envelopes. Credit piggyback belongs to one hop and is consumed before rebuilding branch link headers.

All integers below are unsigned network byte order. Offsets are relative to the byte after the outer Link Header:

| Offset | Width | Field |
|---:|---:|---|
| 0 | 4 | magic/type 0x55425732 (`UBW2`, distinct from old oracle modes) |
| 4 | 1 | version 2 |
| 5 | 1 | flags, must be 0 |
| 6 | 2 | member count, 1..64 |
| 8 | 4 | operation ID |
| 12 | 4 | sequence within operation |
| 16 | 4 | shared payload length, 1..4096 per packet |
| 20 | 2×N | contiguous native header lengths |
| 20+2×N | sum(lengths) | each complete native header excluding Link Header |
| after headers | payload length | actual shared payload |

Fixed extra header remains exactly 20 bytes. No rank/bitmap or per-target Link Header is repeated. Destination, TPN, PSN, SSN, TA extensions, addresses and lengths are retained in actual native header bytes. The native IPv4 builder emits 20-byte IPv4 headers; options and non-WRITE opcodes are rejected. Plain WRITE native prefix after removing Link is 74 bytes, or 78 with UDETAH. The decoder accepts mixed native lengths according to the native WRITE header plan, and rejects malformed total length, truncation, duplicate destination IP, wrong version/type/flags and inconsistent native IP/payload length.

For N plain-WRITE targets and P payload bytes: source v2=24+76N+P, each downstream native packet=78+P. Full v1 for N>1 remains 32+137N+P on both source and each downstream leg. These formulas exclude separately transmitted control traffic, which tests record as physical packet events.

## Internal simulator state (zero wire bytes, not zero cost)

The source queue registers a resolver with one switch ingress. It retains original Flow/Correlation/ExplicitPayload Tag objects and an exact native-header integrity copy. It never retains or supplies payload for reconstruction. Restoring tags compares the actually received native header to the original integrity binding; the switch additionally verifies the resolver changed no serialized packet bytes. No native header is reconstructed from the association table.

Registry capacity is the maximum installed native child's finite send-window packet count, each record has at most64 members, each member uses a supported native header and three tags. Operation IDs must strictly increase between operations (a scalar high-water mark); sequences cannot wrap. Each `(operation,sequence,member)` is consumed once, in packet-member order, and the record is removed at the switch after its last member. Unknown, replayed, out-of-order-member, wrong-header and >10ms-old associations fail explicitly. The 10ms expiry is a simulation fail-fast bound, not a new reliable-transport timer. No timeout ACK or success is generated. The successful fixture requires the table empty before teardown. Loss/recovery is outside this no-loss experiment; retained state is bounded and a non-drained run fails.

The actual tag serialization budget is51B/member, but the in-memory objects, integrity header copies, map nodes, callback binding, allocator references and lifecycle handling cost more. No hardware lookup storage, latency, group programming, SRAM allocation or ASIC replication throughput is modeled. This association service is not free hardware group state and is not advertised as a hardware solution.

## Buffer and credit ownership

The original received envelope owns one input reservation. Native output descriptors retain separately reconstructed headers and the received payload. QueueManager tracks one physical parent reservation and per-output logical byte counts. A branch moves through the existing VOQ/arbiter and finite egress only when native capacity and downstream CBFC permit. Its original replication-management tag is removed before physical transmission, so receiver processing is ordinary native WRITE.

When the last branch leaves the VOQ, QueueManager releases inputBytes once. Allocator calls OnIngressReleased with the original input Packet, so upstream rounded credit equals input bytes, not the size of the last native branch and not fanout times input size. Each egress independently consumes/returns its native packet cells. Both existing RR and DWRR allocator call sites propagate this input-release context. Plain unicast and v1 use unchanged default equal-size paths. Targets sharing a physical output, reflected routes, non-CBFC, retransmission, congestion control, and multiple switches are deliberately excluded.
