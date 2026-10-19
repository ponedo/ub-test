// SPDX-License-Identifier: GPL-2.0-only
// Small codec/Oracle checks. Negative scenarios intentionally abort and must be
// run as separate processes; none modifies or bypasses native protocol logic.
#include "../ub-lightweight-multicast-adapter/adapter.h"
#include <iostream>
#include <string>

using namespace ns3;
using namespace lightweight;

namespace {
constexpr uint32_t kGroup = 101;
constexpr uint32_t kLength = 64;
constexpr uint64_t kMask = (uint64_t{1} << 1) | (uint64_t{1} << 2);

void Require(bool condition, const char* why)
{
    NS_ABORT_MSG_IF(!condition, why);
}

std::vector<uint8_t> Bytes(Ptr<Packet> packet)
{
    std::vector<uint8_t> bytes(packet->GetSize());
    packet->CopyData(bytes.data(), bytes.size());
    return bytes;
}

std::vector<uint8_t> NativeTags(Ptr<Packet> packet)
{
    std::vector<uint8_t> bytes;
    PutTag<UbFlowTag>(bytes, packet);
    PutTag<UbTransactionCorrelationTag>(bytes, packet);
    PutTag<UbExplicitPayloadTag>(bytes, packet);
    return bytes;
}

Ptr<Packet> NativePacket(uint32_t rank, const std::vector<uint8_t>& payload)
{
    auto packet = Create<Packet>(payload.data(), payload.size());
    packet->AddPacketTag(UbFlowTag(1000 + rank, kLength));
    UbTransactionCorrelationIdentity identity;
    identity.operation.ownerNodeId = 0;
    identity.operation.localId = 1000 + rank;
    identity.operation.generation = 3;
    identity.segment.ownerNodeId = 0;
    identity.segment.localId = 2000 + rank;
    identity.segment.generation = 4;
    UbTransactionCorrelationTag correlation;
    correlation.SetIdentity(identity);
    packet->AddPacketTag(correlation);
    packet->AddPacketTag(UbExplicitPayloadTag{});
    UbMAExtTah ma;
    ma.SetVirtualAddress(rank * 1048576);
    ma.SetTokenId(rank);
    ma.SetLength(kLength);
    packet->AddHeader(ma);
    UbTransactionHeader ta;
    ta.SetUbTransactionOpcode(UbTransactionOpcode::WRITE);
    ta.SetIniTaSsn(5 + rank);
    ta.SetIniRcId(200 + rank);
    packet->AddHeader(ta);
    UbTransportHeader tp;
    tp.SetSrcTpn(10 + rank);
    tp.SetDestTpn(20 + rank);
    tp.SetPsn(30 + rank);
    tp.SetTpMsn(40 + rank);
    tp.SetTPOpcode(1);
    tp.SetLastPacket(true);
    tp.SetAckRequest(1);
    packet->AddHeader(tp);
    UdpHeader udp;
    packet->AddHeader(udp);
    Ipv4Header ip;
    ip.SetSource(Ipv4Address("10.0.0.1"));
    ip.SetDestination(Ipv4Address(rank == 1 ? "10.0.0.2" : "10.0.0.3"));
    ip.SetPayloadSize(packet->GetSize());
    packet->AddHeader(ip);
    UbIpBasedNetworkHeader network;
    packet->AddHeader(network);
    UbDatalinkPacketHeader dl;
    dl.SetPacketVL(7);
    packet->AddHeader(dl);
    Require(packet->GetSize() == kLength + 78, "test native WRITE size");
    return packet;
}

struct Fixture
{
    Ptr<SharedSource> queue = CreateObject<SharedSource>();
    std::map<uint32_t, Ptr<Packet>> originals;
    std::vector<uint8_t> wire;

    explicit Fixture(HeaderMode mode)
    {
        queue->headerMode = mode;
        queue->group = kGroup;
        queue->totalBytes = queue->segmentBytes = queue->sentBytes = kLength;
        queue->oracleEnvelopeLimit = 2;
        std::vector<uint8_t> payload(kLength);
        for (uint32_t i = 0; i < kLength; ++i)
        {
            payload[i] = static_cast<uint8_t>(i * 37 + 11);
        }
        SharedSource::OracleEnvelope record{
            mode, 0, kLength, kMask, kMask,
            PayloadChecksum(payload.data(), payload.size()), {}};
        Put(wire, EnvelopeMagic(mode));
        Put(wire, kGroup);
        Put(wire, 0);
        Put(wire, kLength);
        Put(wire, 2);
        Put(wire, static_cast<uint32_t>(kMask >> 32));
        Put(wire, static_cast<uint32_t>(kMask));
        for (uint32_t rank : {1u, 2u})
        {
            auto packet = NativePacket(rank, payload);
            originals.emplace(rank, packet);
            auto raw = Bytes(packet);
            std::vector<uint8_t> metadata(raw.begin(), raw.begin() + 78);
            auto tags = NativeTags(packet);
            metadata.insert(metadata.end(), tags.begin(), tags.end());
            record.members.emplace(rank, SharedSource::OracleMember{
                20 + rank, 30 + rank, 5 + rank, metadata});
            if (mode == HeaderMode::FULL)
            {
                Put(wire, rank);
                Put(wire, 78);
                wire.insert(wire.end(), metadata.begin(), metadata.end());
            }
            else if (mode == HeaderMode::COMPACT_ORACLE)
            {
                Put(wire, rank);
                Put(wire, 20 + rank);
                Put(wire, 30 + rank);
                Put(wire, 5 + rank);
            }
        }
        wire.insert(wire.end(), payload.begin(), payload.end());
        Require(wire.size() + 4 == kLength + ChargedHeaderBytes(mode, 2),
                "test charged byte budget");
        if (mode != HeaderMode::FULL)
        {
            queue->pendingOracle.emplace(std::make_pair(kGroup, 0), std::move(record));
            queue->oracleNativeMetadataBytes = 2 * 129;
        }
    }

    Ptr<Packet> Receive(uint32_t rank = 1, uint32_t group = kGroup, uint32_t seq = 0)
    {
        return queue->ReconstructReceived(
            rank, group, seq, Create<Packet>(wire.data(), wire.size()));
    }
};
} // namespace

int main(int argc, char** argv)
{
    const std::string scenario = argc > 1 ? argv[1] : "positive";
    const std::string modeName = argc > 2 ? argv[2] : "compact-oracle";
    Require(modeName == "full" || modeName == "compact-oracle" ||
                modeName == "ideal-oracle", "unknown test header mode");
    const auto mode = modeName == "full" ? HeaderMode::FULL :
                      modeName == "ideal-oracle" ? HeaderMode::IDEAL_ORACLE :
                                                    HeaderMode::COMPACT_ORACLE;
    Fixture f(mode);
    if (scenario == "positive")
    {
        for (uint32_t rank : {1u, 2u})
        {
            auto packet = f.Receive(rank);
            Require(Bytes(packet) == Bytes(f.originals.at(rank)),
                    "native prefix or actual payload changed");
            Require(NativeTags(packet) == NativeTags(f.originals.at(rank)),
                    "native correlation identity changed");
            if (mode != HeaderMode::FULL && rank == 1)
            {
                Require(f.queue->GetOraclePendingCount() == 1 &&
                            f.queue->oracleNativeMetadataBytes == 258,
                        "oracle released before all receivers consumed");
            }
        }
        f.queue->CheckOracleDrained();
        for (uint32_t fanout : {1u, 2u, 3u, 4u, 8u})
        {
            Require(ChargedHeaderBytes(mode, fanout) ==
                        (fanout == 1 ? 78u : 32u +
                            (mode == HeaderMode::FULL ? 137u * fanout :
                             mode == HeaderMode::COMPACT_ORACLE ? 16u * fanout : 0u)),
                    "header-budget or singleton mismatch");
        }
        std::cout << "PASS " << HeaderModeName(mode)
                  << " native bytes/tags, received payload, all-member drain, budgets\n";
        return 0;
    }

    Require(mode != HeaderMode::FULL, "negative fixtures require an oracle mode");
    auto flip = [&](size_t at) { Require(at < f.wire.size(), "bad test offset"); f.wire[at] ^= 1; };
    if (scenario == "wrong-group") { flip(7); }
    else if (scenario == "wrong-sequence") { flip(11); }
    else if (scenario == "wrong-length") { flip(15); }
    else if (scenario == "wrong-count") { flip(19); }
    else if (scenario == "wrong-bitmap") { flip(27); }
    else if (scenario == "wrong-mode") { flip(3); }
    else if (scenario == "wrong-member" || scenario == "wrong-tp" ||
             scenario == "wrong-psn" || scenario == "wrong-ssn")
    {
        Require(mode == HeaderMode::COMPACT_ORACLE, "compact record required");
        flip(scenario == "wrong-member" ? 31 : scenario == "wrong-tp" ? 35 :
             scenario == "wrong-psn" ? 39 : 43);
    }
    else if (scenario == "payload-mismatch") { flip(f.wire.size() - 1); }
    else if (scenario == "truncated") { f.wire.resize(3); }
    else if (scenario == "trailing") { f.wire.push_back(0); }
    else if (scenario == "missing-context") { f.queue->pendingOracle.clear(); }
    else if (scenario == "wrong-range") { f.queue->pendingOracle.at({kGroup, 0}).offset = 1; }
    else if (scenario == "duplicate") { f.Receive(); }
    else if (scenario == "undrained") { f.queue->CheckOracleDrained(); }
    else if (scenario == "wrong-receiver") { f.Receive(3); }
    else if (scenario == "wrong-callback-group") { f.Receive(1, kGroup + 1); }
    else if (scenario == "wrong-callback-sequence") { f.Receive(1, kGroup, 1); }
    else { Require(false, "unknown negative scenario"); }
    f.Receive();
    std::cerr << "FAIL: negative scenario was accepted: " << scenario << '\n';
    return 2;
}
