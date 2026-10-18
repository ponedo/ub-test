// SPDX-License-Identifier: GPL-2.0-only
// Network-only test interface. Payload identities are PacketTags, not UB transactions.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/ub-switch.h"
#include "ns3/ub-port.h"
#include "ns3/ub-link.h"
#include "ns3/ub-cbfc.h"
#include "ns3/ub-controller.h"
#include "ns3/ub-tag.h"
#include "ns3/ub-queue-manager.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <vector>
#include <filesystem>
using namespace ns3;
struct Observer {
    uint32_t rank;
    bool requireObjectOrder{false};
    std::string directory;
    std::map<uint32_t,std::vector<uint8_t>> expected, received;
    std::map<uint32_t,uint32_t> next;
    std::map<uint32_t,uint64_t> completed, completedPs;
    uint64_t count{0}, bytes{0}, last{0};
    void Receive(uint32_t object, uint32_t sequence, Ptr<Packet> p) {
        NS_ABORT_MSG_IF(!expected.count(object), "Unexpected object/member");
        if(requireObjectOrder) for(auto& [id,bytes]:expected)
            NS_ABORT_MSG_IF(id<object && !completed.count(id), "Source stream object ordering violated");
        NS_ABORT_MSG_IF(sequence != next[object]++, "Duplicate, missing, or reordered network packet");
        std::vector<uint8_t> b(p->GetSize()); p->CopyData(b.data(), b.size());
        auto& r=received[object]; auto& e=expected.at(object);
        NS_ABORT_MSG_IF(r.size()+b.size()>e.size() ||
            !std::equal(b.begin(),b.end(),e.begin()+r.size()), "Payload differs from source");
        r.insert(r.end(),b.begin(),b.end()); ++count; bytes+=b.size(); last=Simulator::Now().GetNanoSeconds();
        if(r.size()==e.size()) { completed[object]=last; completedPs[object]=Simulator::Now().GetPicoSeconds(); }
    }
    void Finish(std::ofstream& out) {
        for(auto& [id,e]:expected) {
            NS_ABORT_MSG_IF(received[id]!=e || !completed.count(id), "Incomplete object");
            std::string f=directory+"/rank"+std::to_string(rank)+"-object"+std::to_string(id)+".bin";
            std::ofstream raw(f,std::ios::binary);raw.write((char*)received[id].data(),received[id].size());
            out<<rank<<","<<id<<","<<e.size()<<","<<next[id]<<","<<completed[id]<<","<<completedPs[id]<<"\n";
        }
    }
};
struct PortObserver {
    uint32_t rank, port;
    uint64_t dataTx{0}, dataRx{0}, wireTx{0}, wireRx{0}, packetsTx{0}, packetsRx{0}, peakEgress{0};
    uint64_t consumedExpected{0}, receivedCells{0};
    void Tx(Ptr<Packet> p, Time) {
        wireTx+=p->GetSize(); UbNetworkReplicationTag t;
        if(p->PeekPacketTag(t)) { dataTx+=p->GetSize(); ++packetsTx; consumedExpected+=(p->GetSize()+159)/160; }
    }
    void Rx(Ptr<Packet> p) {
        wireRx+=p->GetSize();UbNetworkReplicationTag t;
        if(p->PeekPacketTag(t)) { dataRx+=p->GetSize(); ++packetsRx; receivedCells+=(p->GetSize()+159)/160; }
    }
    void Enqueue(Ptr<const Packet>,uint32_t n) { peakEgress=std::max(peakEgress,uint64_t(n)); }
};
struct QueueObserver {
    uint64_t ingressPeak{0}, outPeak{0};
    void In(uint32_t,uint32_t,uint64_t n) { ingressPeak=std::max(ingressPeak,n); }
    void Out(uint32_t,uint64_t n) { outPeak=std::max(outPeak,n); }
};
int main(int argc,char**argv) {
    Time::SetResolution(Time::PS);
    std::string scenario="basic", directory="network-results";
    bool direct=false, dwrr=false;
    uint32_t basicBytes=64; std::string negative="";
    CommandLine cmd;cmd.AddValue("scenario","basic/multipart/dynamic/competition/pressure",scenario);
    cmd.AddValue("direct","Send one independent packet per destination",direct);
    cmd.AddValue("out","Private output directory",directory);
    cmd.AddValue("dwrr","Use native DWRR VL allocator",dwrr);
    cmd.AddValue("basicBytes","Basic-case payload bytes",basicBytes);
    cmd.AddValue("negative","Expected-failure probe: empty/reflected/unknown/oversize",negative);
    cmd.Parse(argc,argv);
    NS_ABORT_MSG_IF(scenario!="basic" && scenario!="multipart" && scenario!="dynamic" &&
        scenario!="competition" && scenario!="pressure", "Unknown scenario");
    std::filesystem::create_directories(directory);
    for(auto key:{"UB_TRACE_ENABLE","UB_TASK_TRACE_ENABLE","UB_PACKET_TRACE_ENABLE","UB_PORT_TRACE_ENABLE",
        "UB_PARSE_TRACE_ENABLE","UB_RECORD_PKT_TRACE","UB_FLOW_CONTROL_TRACE_ENABLE",
        "UB_CONGESTION_CONTROL_TRACE_ENABLE"}) GlobalValue::BindFailSafe(key,BooleanValue(false));
    const uint32_t reserve=scenario=="pressure" ? 2240 : 16384;
    const uint32_t egress=scenario=="pressure" ? 1040 : 4096;
    const int initial=reserve/160;
    Config::SetDefault("ns3::UbPort::UbDataRate",DataRateValue(DataRate("100Gbps")));
    Config::SetDefault("ns3::UbLink::Delay",TimeValue(NanoSeconds(20)));
    UbEgressQueue::GetTypeId(); // Native queue type is lazily registered.
    Config::SetDefault("ns3::UbEgressQueue::MaxEgressBytes",UintegerValue(egress));
    Config::SetDefault("ns3::UbPort::CbfcCtrlCrdRtrThldCell",IntegerValue(1));
    Config::SetDefault("ns3::UbSwitch::InPortProcessingDelay",TimeValue(NanoSeconds(10)));
    if(dwrr)Config::SetDefault("ns3::UbSwitch::VlScheduler",StringValue("DWRR"));
    NodeContainer nodes;nodes.Create(6); // ranks0..4, switch5; rank4 also contention source.
    std::vector<Ptr<UbSwitch>> sw(6);
    std::vector<std::vector<Ptr<UbPort>>> ports(6);
    std::vector<std::vector<PortObserver>> observations(6);
    std::vector<Observer> sinks(5);
    QueueObserver occupancy;
    for(uint32_t n=0;n<6;++n) {
        sw[n]=CreateObject<UbSwitch>();nodes.Get(n)->AggregateObject(sw[n]);
        sw[n]->SetNodeType(n==5?UB_SWITCH:UB_DEVICE);
        sw[n]->SetReservePerQueueBytes(reserve);sw[n]->SetSharedPoolBytes(0);sw[n]->SetHeadroomPerPortBytes(0);
        sw[n]->SetCbfcCredits(initial,0);sw[n]->SetCbfcCellGeometry(20,8);sw[n]->SetCbfcReturnCellGrain(1,1);
        uint32_t count=n==5?5:1; observations[n].resize(count);
        for(uint32_t j=0;j<count;++j) {
            auto p=CreateObject<UbPort>();p->SetAddress(Mac48Address::Allocate());nodes.Get(n)->AddDevice(p);
            ports[n].push_back(p);
        }
        sw[n]->Init();
        for(uint32_t j=0;j<count;++j) {
            auto& o=observations[n][j];o.rank=n;o.port=j;
            ports[n][j]->TraceConnectWithoutContext("TraComEventNotify",MakeCallback(&PortObserver::Tx,&o));
            ports[n][j]->TraceConnectWithoutContext("PktRcvNotify",MakeCallback(&PortObserver::Rx,&o));
            ports[n][j]->GetUbQueue()->TraceConnectWithoutContext("UbEnqueue",MakeCallback(&PortObserver::Enqueue,&o));
        }
        if(n<5) { sinks[n].rank=n;sinks[n].directory=directory;sinks[n].requireObjectOrder=scenario=="dynamic";
            sw[n]->EnableNetworkSink(n,MakeCallback(&Observer::Receive,&sinks[n])); }
    }
    for(uint32_t n=0;n<5;++n) {
        auto link=CreateObject<UbLink>();ports[n][0]->Attach(link);ports[5][n]->Attach(link);
    }
    sw[5]->EnableNetworkReplication({0,1,2,3,4});
    sw[5]->GetQueueManager()->TraceConnectWithoutContext("IngressQueueOccupancyBytes",MakeCallback(&QueueObserver::In,&occupancy));
    sw[5]->GetQueueManager()->TraceConnectWithoutContext("OutPortBufferBytes",MakeCallback(&QueueObserver::Out,&occupancy));
    struct Object {uint32_t id,source;uint64_t mask;std::vector<uint8_t> data;};
    std::vector<Object> objects;
    auto add=[&](uint32_t id,uint32_t source,uint64_t mask,uint32_t bytes) {
        Object obj{id,source,mask,{}}; std::mt19937 gen(20261018+id);
        obj.data.resize(bytes);for(auto& b:obj.data)b=gen()&255;
        for(uint32_t r=0;r<5;++r)if(mask&(1ULL<<r))sinks[r].expected[id]=obj.data;
        std::ofstream raw(directory+"/source-object"+std::to_string(id)+".bin",std::ios::binary);
        raw.write((char*)obj.data.data(),obj.data.size()); objects.push_back(std::move(obj));
    };
    if(scenario=="dynamic") {add(0,0,6,32768);add(1,0,12,32768);}
    else {
        add(0,0,14,scenario=="basic"?basicBytes:65536);
        if(scenario=="competition"||scenario=="pressure")add(1,4,2,131072);
    }
    if(!negative.empty()) {
        if(negative=="empty")objects[0].mask=0;
        else if(negative=="reflected")objects[0].mask=1;
        else if(negative=="unknown")objects[0].mask=1ULL<<63;
        else if(negative=="oversize") {
            sw[0]->SubmitNetworkPacket(0,Create<Packet>(4097),14,0,0);
        } else NS_ABORT_MSG("Unknown negative probe");
    }
    // Same arrival time in direct and replication; deterministic object/packet/destination order.
    Simulator::Schedule(NanoSeconds(100),[&] {
        for(auto& obj:objects)for(uint32_t offset=0,seq=0;offset<obj.data.size();offset+=1024,++seq) {
            uint32_t len=std::min(size_t(1024),obj.data.size()-offset);
            auto p=Create<Packet>(obj.data.data()+offset,len);
            if(direct) {
                for(uint32_t r=0;r<5;++r)if(obj.mask&(1ULL<<r))
                    NS_ABORT_MSG_IF(!sw[obj.source]->SubmitNetworkPacket(0,p,1ULL<<r,obj.id,seq),"Source queue full");
            } else NS_ABORT_MSG_IF(!sw[obj.source]->SubmitNetworkPacket(0,p,obj.mask,obj.id,seq),"Source queue full");
        }
    });
    // Simulation watchdog only; arrivals/completion always originate from native links.
    Simulator::Stop(MilliSeconds(10));Simulator::Run();
    std::ofstream target(directory+"/targets.csv");target<<"rank,object,payload_bytes,packets,complete_ns,complete_ps\n";
    for(auto& sink:sinks)sink.Finish(target);
    const auto& s=sw[5]->GetNetworkReplicationStats();
    NS_ABORT_MSG_IF(s.admitted!=s.released || s.branches!=s.branchDequeues || s.parentBytes ||
        s.branchBytes || s.descriptors || sw[5]->GetNetworkOutstandingParents(),"Replication resources leaked");
    NS_ABORT_MSG_IF(occupancy.ingressPeak>reserve,"Ingress capacity exceeded");
    std::ofstream portFile(directory+"/ports.csv");
    portFile<<"rank,port,data_tx_bytes,data_rx_bytes,wire_tx_bytes,wire_rx_bytes,data_tx_packets,data_rx_packets,egress_peak,credit_consumed,credit_returned,credit_restored,credit_free,credit_pending,blocked_queries\n";
    uint64_t totalBlocked=0;
    for(uint32_t n=0;n<6;++n)for(uint32_t j=0;j<ports[n].size();++j) {
        auto& o=observations[n][j];auto fc=DynamicCast<UbCbfc>(ports[n][j]->GetFlowControl());
        NS_ABORT_MSG_IF(!fc,"Missing CBFC");
        NS_ABORT_MSG_IF(o.wireTx != ports[n][j]->GetTxBytes(),"Port trace does not match native TX bytes");
        NS_ABORT_MSG_IF(o.peakEgress>egress || ports[n][j]->GetUbQueue()->GetCurrentBytes(),"Egress overflow/leak");
        NS_ABORT_MSG_IF(fc->GetConsumedCells()!=o.consumedExpected,"Credit consume differs from wire packets");
        NS_ABORT_MSG_IF(fc->GetReturnedCells()!=o.receivedCells,"Credit return differs from original received packets");
        NS_ABORT_MSG_IF(int64_t(initial)-int64_t(fc->GetConsumedCells())+int64_t(fc->GetRestoredCells())!=fc->GetTxFreeCells(1),"Credit conservation failed");
        NS_ABORT_MSG_IF(fc->GetTxFreeCells(1)!=initial || fc->GetCrdToReturn(1)!=0,"Credits did not fully drain");
        totalBlocked+=fc->GetBlockedQueryCount();
        portFile<<n<<","<<j<<","<<o.dataTx<<","<<o.dataRx<<","<<o.wireTx<<","<<o.wireRx<<","<<o.packetsTx<<","<<o.packetsRx<<","<<o.peakEgress<<","<<fc->GetConsumedCells()<<","<<fc->GetReturnedCells()<<","<<fc->GetRestoredCells()<<","<<fc->GetTxFreeCells(1)<<","<<fc->GetCrdToReturn(1)<<","<<fc->GetBlockedQueryCount()<<"\n";
    }
    NS_ABORT_MSG_IF(sw[5]->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes,"Switch did not drain");
    if(scenario=="pressure")NS_ABORT_MSG_IF(!totalBlocked,"Pressure case never exercised CBFC blocking");
    if(scenario=="competition"&&!direct)NS_ABORT_MSG_IF(sinks[2].completed[0]>=sinks[1].completed[0] || sinks[3].completed[0]>=sinks[1].completed[0],"Independent branches did not progress ahead of contended B");
    std::ofstream stats(directory+"/summary.csv");
    stats<<"scenario,direct,reserve_bytes,egress_bytes,initial_credit_cells,parents,branches,peak_parent_bytes,peak_logical_branch_bytes,peak_descriptors,ingress_peak,outport_logical_peak,upstream_return_bytes,blocked_queries,validation\n";
    stats<<scenario<<","<<direct<<","<<reserve<<","<<egress<<","<<initial<<","<<s.admitted<<","<<s.branches<<","<<s.peakParentBytes<<","<<s.peakBranchBytes<<","<<s.peakDescriptors<<","<<occupancy.ingressPeak<<","<<occupancy.outPeak<<","<<s.upstreamReturnBytes<<","<<totalBlocked<<",PASS\n";
    std::ofstream waits(directory+"/arbitration.csv");waits<<"port,branch_packets,voq_wait_total_ns\n";
    for(uint32_t p=0;p<5;++p)waits<<p<<","<<s.branchPackets[p]<<","<<s.branchWaitNs[p]<<"\n";
    std::cout<<"PASS "<<scenario<<" direct="<<direct<<" parents="<<s.admitted<<" branches="<<s.branches<<"\n";
    Simulator::Destroy();return 0;
}
