// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "../ub-lightweight-multicast-adapter/adapter.h"
#include "ns3/ub-write-v2.h"
namespace writev2 {
using namespace ns3;
class SharedSource : public lightweight::SharedSource {
public:
    struct Metadata {
        UbFlowTag flow; UbTransactionCorrelationTag correlation; UbExplicitPayloadTag explicitPayload;
        std::vector<uint8_t> header; // integrity comparison only, never used to build a packet
    };
    struct Record { Time expires; uint32_t next{}; std::vector<Metadata> members; };
    std::map<std::pair<uint32_t,uint32_t>,Record> pending;
    uint64_t capacity{}, peakRecords{}, restored{};
    uint32_t lastOperation{}; bool hasOperation{false};
    std::function<void(Ptr<Packet>)> nativeObserver;
    static TypeId GetTypeId() { static TypeId t=TypeId("ns3::WriteV2SharedSource")
        .SetParent<lightweight::SharedSource>().AddConstructor<SharedSource>(); return t; }
    void Install(Ptr<UbPort> p,const std::vector<Child>& children) {
        lightweight::SharedSource::Install(p,children);
        for(auto& c:children) { UintegerValue w; c.tp->GetAttribute("DefaultMaxInflightPacketSize",w);
            NS_ABORT_MSG_IF(!w.Get(),"v2 requires finite native send window"); capacity=std::max(capacity,w.Get()); }
    }
    uint32_t GetNextPacketSize() override {
        if(auto t=Control()) return t->GetNextPacketSize();
        if(active.empty() || sentBytes>=totalBytes) return 0;
        uint32_t len=std::min(segmentBytes,totalBytes-sentBytes), bytes=24+2*active.size()+len;
        for(auto& c:active) { auto n=c.tp->GetNextPacketSize();
            // If a child is not ready, the allocator will consult IsLimited before dequeue.
            if(n<len+78) return 0;
            bytes+=n-len-4;
        }
        return bytes;
    }
    Ptr<Packet> GetNextPacket() override {
        if(auto t=Control()) { auto p=t->GetNextPacket(); Refresh(); return p; }
        NS_ABORT_MSG_IF(IsLimited(),"v2 child not eligible");
        NS_ABORT_MSG_IF(pending.size()>=capacity || sequence==UINT32_MAX,"v2 association capacity/sequence");
        if(sequence==0) { NS_ABORT_MSG_IF(hasOperation && group<=lastOperation,"v2 operation reused/nonmonotonic"); lastOperation=group; hasOperation=true; }
        const uint32_t expected=GetNextPacketSize(),len=std::min(segmentBytes,totalBytes-sentBytes);
        UbWriteV2 v; v.operation=group; v.sequence=sequence;
        Record record{Simulator::Now()+MilliSeconds(10),0,{}};
        UbDatalinkPacketHeader outer;
        for(auto& c:active) {
            auto p=c.tp->GetNextPacket(); NS_ABORT_MSG_IF(!p,"v2 native child dequeue");
            UbTransportChannel::ReceivedDataPacketContext ctx;
            NS_ABORT_MSG_IF(!c.tp->ParseReceivedDataPacketForTest(p->Copy(),ctx) ||
                ctx.flowTag.GetFlowId()!=MemberTask(c.rank) || ctx.payloadBytes!=len ||
                ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE) ||
                ctx.ipv4Header.GetDestination()!=NodeIdToIp(c.rank,0),"v2 child identity/type/range");
            if(nativeObserver) nativeObserver(p);
            auto copy=p->Copy(); UbDatalinkPacketHeader dl; copy->RemoveHeader(dl);
            if(v.headers.empty()) outer=dl;
            NS_ABORT_MSG_IF(dl.GetPacketVL()!=outer.GetPacketVL() || dl.GetRoutingType()!=outer.GetRoutingType(),"v2 incompatible link headers");
            std::vector<uint8_t> raw(copy->GetSize()); copy->CopyData(raw.data(),raw.size());
            std::vector<uint8_t> payload(raw.end()-len,raw.end());
            if(v.headers.empty()) v.payload=payload;
            else NS_ABORT_MSG_IF(v.payload!=payload,"v2 payload differs");
            v.headers.emplace_back(raw.begin(),raw.end()-len);
            Metadata m; m.header=v.headers.back();
            NS_ABORT_MSG_IF(!p->PeekPacketTag(m.flow) || !p->PeekPacketTag(m.correlation) ||
                            !p->PeekPacketTag(m.explicitPayload),"v2 missing native metadata");
            record.members.push_back(std::move(m));
        }
        auto wire=v.Encode();
        NS_ABORT_MSG_IF(!pending.emplace(std::make_pair(group,sequence),std::move(record)).second,"duplicate v2 association");
        peakRecords=std::max(peakRecords,uint64_t(pending.size()));
        auto p=Create<Packet>(wire.data(),wire.size()); outer.SetCredit(false); outer.SetACK(false); outer.SetConfig(15); p->AddHeader(outer);
        NS_ABORT_MSG_IF(p->GetSize()!=expected,"v2 predicted size");
        ++sequence; ++envelopes; sentBytes+=len; payloadSent+=len; wireDataBytes+=p->GetSize();
        chargedHeaderBytes+=p->GetSize()-len; Refresh(); return p;
    }
    void Restore(uint32_t operation,uint32_t seq,uint32_t member,Ptr<Packet> p) {
        auto it=pending.find({operation,seq});
        NS_ABORT_MSG_IF(it==pending.end(),"unknown/consumed v2 association"); auto& r=it->second;
        NS_ABORT_MSG_IF(Simulator::Now()>r.expires || member!=r.next || member>=r.members.size(),"expired/duplicate v2 member");
        auto& m=r.members[member]; auto copy=p->Copy(); UbDatalinkPacketHeader dl; copy->RemoveHeader(dl);
        NS_ABORT_MSG_IF(copy->GetSize()<m.header.size(),"v2 header truncated at association");
        std::vector<uint8_t> header(m.header.size()); copy->CopyData(header.data(),header.size());
        NS_ABORT_MSG_IF(header!=m.header,"v2 actual protocol identity/header differs");
        p->AddPacketTag(m.flow); p->AddPacketTag(m.correlation); p->AddPacketTag(m.explicitPayload);
        ++restored; if(++r.next==r.members.size()) pending.erase(it);
    }
    void CheckDrained() const { NS_ABORT_MSG_IF(!pending.empty(),"v2 association leak"); }
};
}
