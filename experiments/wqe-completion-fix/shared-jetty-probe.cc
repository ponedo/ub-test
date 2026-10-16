// SPDX-License-Identifier: GPL-2.0-only
// Standalone application-only capability probe. No native protocol changes.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <vector>
using namespace ns3;
namespace {
inline Ptr<UbPort>
CreatePort(Ptr<Node> node)
{
    Ptr<UbPort> port = CreateObject<UbPort>();
    port->SetAddress(Mac48Address::Allocate());
    node->AddDevice(port);
    return port;
}

inline void
InitNode(Ptr<Node> node,
         UbNodeType_t nodeType,
         uint32_t portCount,
         bool provisionDefaultCtpEntity = true)
{
    Ptr<UbSwitch> sw = CreateObject<UbSwitch>();
    node->AggregateObject(sw);
    sw->SetNodeType(nodeType);

    if (nodeType == UB_DEVICE)
    {
        Ptr<UbController> controller = CreateObject<UbController>();
        node->AggregateObject(controller);
        controller->CreateUbFunction();
        controller->CreateUbTransaction();
    }

    for (uint32_t index = 0; index < portCount; ++index)
    {
        CreatePort(node);
    }

    if (nodeType == UB_DEVICE && provisionDefaultCtpEntity)
    {
        Ptr<UbController> controller = node->GetObject<UbController>();
        controller->CreateDefaultCtpEntity(1);
        controller->FreezeCtpEntities();
    }

    sw->Init();
    Ptr<UbCongestionControl> congestionCtrl = UbCongestionControl::Create(UB_SWITCH);
    congestionCtrl->OnSwitchAttached(sw);
}

inline void
AddShortestRoute(Ptr<Node> node, uint32_t destNodeId, uint32_t destPortId, uint16_t outPort)
{
    std::vector<uint16_t> outPorts = {outPort};
    Ptr<UbRoutingProcess> routing = node->GetObject<UbSwitch>()->GetRoutingProcess();
    routing->GetRoutingTable().AddShortestRoute(NodeIdToIp(destNodeId).Get(), outPorts);
    routing->GetRoutingTable().AddShortestRoute(NodeIdToIp(destNodeId, destPortId).Get(), outPorts);
}
constexpr uint32_t kTargetExecutionSenderTpn = 101;
constexpr uint32_t kTargetExecutionReceiverTpn = 202;
constexpr uint32_t kTargetExecutionPriority = 7;
constexpr uint32_t kTargetExecutionJettyNum = 3;

/** One direct-link RTP pair that can carry a real inbound request to a target executor. */
struct TargetExecutionPair
{
    Ptr<Node> sender;
    Ptr<Node> receiver;
    Ptr<UbPort> senderPort;
    Ptr<UbPort> receiverPort;
    Ptr<UbTransportChannel> senderTp;
    Ptr<UbTransportChannel> receiverTp;
    Ptr<UbFunction> senderFunction;
    Ptr<UbTransaction> senderTransaction;
    Ptr<UbTransaction> receiverTransaction;
    Ptr<UbJetty> senderJetty;
};

TargetExecutionPair
BuildTargetExecutionPair()
{
    Config::Reset();
    GlobalValue::Bind("UB_CC_ENABLED", BooleanValue(false));
    TargetExecutionPair pair;
    pair.sender = CreateObject<Node>(0);
    pair.receiver = CreateObject<Node>(0);
    InitNode(pair.sender, UB_DEVICE, 1);
    InitNode(pair.receiver, UB_DEVICE, 1);
    pair.senderPort = DynamicCast<UbPort>(pair.sender->GetDevice(0));
    pair.receiverPort = DynamicCast<UbPort>(pair.receiver->GetDevice(0));

    Ptr<UbLink> link = CreateObject<UbLink>();
    pair.senderPort->Attach(link);
    pair.receiverPort->Attach(link);
    AddShortestRoute(pair.sender,
                     pair.receiver->GetId(),
                     pair.receiverPort->GetIfIndex(),
                     pair.senderPort->GetIfIndex());
    AddShortestRoute(pair.receiver,
                     pair.sender->GetId(),
                     pair.senderPort->GetIfIndex(),
                     pair.receiverPort->GetIfIndex());

    Ptr<UbController> senderCtrl = pair.sender->GetObject<UbController>();
    Ptr<UbController> receiverCtrl = pair.receiver->GetObject<UbController>();
    Connection connection;
    connection.ownerNodeId = pair.sender->GetId();
    connection.node1 = pair.sender->GetId();
    connection.port1 = pair.senderPort->GetIfIndex();
    connection.tpn1 = kTargetExecutionSenderTpn;
    connection.node2 = pair.receiver->GetId();
    connection.port2 = pair.receiverPort->GetIfIndex();
    connection.tpn2 = kTargetExecutionReceiverTpn;
    connection.priority = kTargetExecutionPriority;
    connection.metrics = 0;
    senderCtrl->GetTpConnManager()->AddUnilateralConnection(connection, pair.sender->GetId());
    receiverCtrl->GetTpConnManager()->AddUnilateralConnection(connection, pair.receiver->GetId());
    senderCtrl->GetTransportChannelManager()->CreateTp(pair.sender->GetId(),
                                                       pair.receiver->GetId(),
                                                       pair.senderPort->GetIfIndex(),
                                                       pair.receiverPort->GetIfIndex(),
                                                       kTargetExecutionPriority,
                                                       kTargetExecutionSenderTpn,
                                                       kTargetExecutionReceiverTpn,
                                                       UbCongestionControl::Create(UB_DEVICE));
    receiverCtrl->GetTransportChannelManager()->CreateTp(pair.receiver->GetId(),
                                                         pair.sender->GetId(),
                                                         pair.receiverPort->GetIfIndex(),
                                                         pair.senderPort->GetIfIndex(),
                                                         kTargetExecutionPriority,
                                                         kTargetExecutionReceiverTpn,
                                                         kTargetExecutionSenderTpn,
                                                         UbCongestionControl::Create(UB_DEVICE));

    pair.senderTp = senderCtrl->GetTransportChannelManager()->GetTp(kTargetExecutionSenderTpn);
    pair.receiverTp =
        receiverCtrl->GetTransportChannelManager()->GetTp(kTargetExecutionReceiverTpn);
    pair.senderTransaction = senderCtrl->GetUbTransaction();
    pair.receiverTransaction = receiverCtrl->GetUbTransaction();

    pair.senderFunction = senderCtrl->GetUbFunction();
    pair.senderFunction->CreateJetty(pair.sender->GetId(),
                                     pair.receiver->GetId(),
                                     kTargetExecutionJettyNum);
    NS_ABORT_MSG_IF(!pair.senderTransaction->JettyBindTp(pair.sender->GetId(),
                                                         pair.receiver->GetId(),
                                                         kTargetExecutionJettyNum,
                                                         false,
                                                         {kTargetExecutionSenderTpn}),
                    "sender Jetty must bind to the direct TP");
    pair.senderJetty = pair.senderFunction->GetJetty(kTargetExecutionJettyNum);
    return pair;
}

struct State {
    uint32_t size=0, callbacks=0, receipts=0, completed=0;
    bool submitted=false;
    std::vector<uint8_t> expected, seen;
    std::set<uint32_t> offsets;
};
class SharedJettyProbe {
public:
    std::string mode="concurrentmulti", output="shared-jetty";
    uint32_t count=3, segment=1024, segments=4;
    bool duplicateDone=false;
    uint64_t delayNs=50000, lateNs=200000, delayedLastNs=0, checkpointNs=0;
    TargetExecutionPair pair;
    std::map<uint32_t,State> states;
    std::map<uint32_t,uint32_t> owners;
    std::ofstream events;
    std::vector<std::string> failures;
    uint32_t outstanding=0, peak=0;
    void Event(const std::string& event,uint32_t id=0,uint32_t ssn=0,
               uint32_t off=0,uint32_t bytes=0,const std::string& detail="") {
        events<<Simulator::Now().GetNanoSeconds()<<','<<event<<','<<id<<','<<ssn<<','
              <<off<<','<<bytes<<','<<pair.senderJetty->GetTaSsnSndUnaForTest()<<','
              <<pair.senderJetty->GetTaSsnSndNxtForTest()<<','<<detail<<'\n';
        events.flush(); // retain evidence even if native aborts
    }
    void Fail(const std::string& why,uint32_t id=0,uint32_t ssn=0) {
        failures.push_back(why); Event("FAIL",id,ssn,0,0,why);
    }
    static void Put(std::vector<uint8_t>& v,uint32_t at,uint32_t n) {
        for(uint32_t k=0;k<4;++k) v[at+k]=uint8_t(n>>(8*k));
    }
    static uint32_t Get(const std::vector<uint8_t>& v,uint32_t at) {
        uint32_t n=0;for(uint32_t k=0;k<4;++k)n|=uint32_t(v[at+k])<<(8*k);return n;
    }
    void Prepare(uint32_t id) {
        auto& s=states[id];s.size=(mode=="onesegment" || mode=="singleonesegment")?segment:segment*segments+32;
        s.expected.resize(s.size);s.seen.resize(s.size);
        // Each fragment carries an independently decodable identity and offset.
        for(uint32_t off=0;off<s.size;off+=segment) {
            uint32_t len=std::min(segment,s.size-off);
            for(uint32_t j=0;j<len;++j) s.expected[off+j]=uint8_t((id*73+(off+j)*131+((off+j)>>8)*17)%251);
            Put(s.expected,off,0x5945544a);Put(s.expected,off+4,id);
            Put(s.expected,off+8,off);Put(s.expected,off+12,len);
        }
    }
    void Submit(uint32_t id) {
        auto& s=states.at(id);s.submitted=true;++outstanding;peak=std::max(peak,outstanding);
        Event("submit",id,0,0,s.size);
        auto w=pair.senderFunction->CreateWqe(pair.sender->GetId(),pair.receiver->GetId(),s.size,id,UbTransactionOpcode::WRITE);
        w->SetOrderType(OrderType::ORDER_NO);
        w->SetExplicitPayload(Create<Packet>(s.expected.data(),s.expected.size()));
        if(pair.senderFunction->SubmitWqe(w,kTargetExecutionJettyNum).status!=UbWqeSubmissionStatus::ACCEPTED)
            Fail("submit_rejected",id);
    }
    void Sent(uint32_t,uint32_t id,uint32_t ssn) {
        auto [it,inserted]=owners.emplace(ssn,id);
        if(!inserted && it->second!=id) Fail("ssn_owner_changed",id,ssn);
        if(!states.count(id)) Fail("unknown_sent_task",id,ssn);
        Event("segment_sent",id,ssn);
    }
    void Callback(uint32_t id,uint32_t jetty) {
        Event("sender_callback",id);
        if(jetty!=kTargetExecutionJettyNum || !states.count(id)) {Fail("wrong_callback_identity",id);return;}
        auto& s=states.at(id);++s.callbacks;
        if(s.callbacks!=1) Fail("duplicate_callback",id);
        if(!s.submitted) Fail("callback_before_submit",id);
        if(std::count(s.seen.begin(),s.seen.end(),uint8_t(1))!=s.size) Fail("sender_before_all_target_bytes",id);
        if(s.completed!=(s.size+segment-1)/segment) Fail("sender_before_all_target_completions",id);
        if(outstanding) --outstanding;
    }
    void Target(Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done) {
        uint32_t task=req->GetTaskId(),ssn=req->GetTaSsn(),len=req->GetLogicalBytes();
        Event("target_receive",task,ssn,0,len);
        bool valid=true;
        if(req->GetSrc()!=pair.sender->GetId() || req->GetDest()!=pair.receiver->GetId() ||
           req->GetType()!=UbTransactionOpcode::WRITE || !req->HasTransactionResolved()) {
            Fail("target_metadata",task,ssn);valid=false;
        }
        auto own=owners.find(ssn);
        if(own==owners.end() || own->second!=task) {Fail("target_ssn_owner",task,ssn);valid=false;}
        uint32_t decoded=0,off=0;
        if(!req->HasExplicitPayload() || req->GetExplicitPayload()->GetSize()!=len || req->GetPayloadBytes()!=len || len<16) {
            Fail("missing_or_wrong_payload_size",task,ssn);valid=false;
        } else {
            std::vector<uint8_t> bytes(len); req->GetExplicitPayload()->CopyData(bytes.data(),len);
            decoded=Get(bytes,4);off=Get(bytes,8);
            if(Get(bytes,0)!=0x5945544a || decoded!=task || !states.count(decoded) || Get(bytes,12)!=len) {
                Fail("payload_identity_mismatch",task,ssn);valid=false;
            } else {
                auto& s=states.at(decoded);
                if(off>=s.size || off%segment || len!=std::min(segment,s.size-off)) {
                    Fail("payload_offset_or_length",task,ssn);valid=false;
                } else {
                    if(!std::equal(bytes.begin(),bytes.end(),s.expected.begin()+off)) {Fail("payload_byte_mismatch",task,ssn);valid=false;}
                    if(!s.offsets.insert(off).second) {Fail("duplicate_fragment",task,ssn);valid=false;}
                    if(valid) {std::fill(s.seen.begin()+off,s.seen.begin()+off+len,1);++s.receipts;Event("bytes_verified",task,ssn,off,len);}
                }
            }
        }
        // Delays vary by fragment identity, not SSN, and permit out-of-order completion.
        uint64_t delay=delayNs+(uint64_t(task%3)*5000)+((off/segment)%2?10000:0);
        Simulator::Schedule(NanoSeconds(delay),[this,done,task,ssn,off,len,valid] {
            if(valid) ++states.at(task).completed;
            Event("target_complete",task,ssn,off,len);
            done(UbWorkExecutionResult{});
            if(duplicateDone) { Event("duplicate_target_done",task,ssn); done(UbWorkExecutionResult{}); }
        });
    }
    int Run() {
        if((mode!="concurrentmulti" && mode!="single" && mode!="onesegment" && mode!="singleonesegment") || count<3 || count>16 ||
           segment<64 || segment>65536 || segments<2 || segments>32 || delayNs<1 || delayNs>1000000 ||
           lateNs<1 || lateNs>2000000 || delayedLastNs>2000000) {
            std::cerr<<"invalid CLI: mode concurrentmulti/single/onesegment; count 3..16; segment 64..65536; segments 2..32; delay 1..1e6ns; late 1..2e6ns\n";return 2;
        }
        {std::ofstream out(output+"-summary.txt");
         if(!out) return 2;
         out<<"status=INCOMPLETE_OR_NATIVE_ABORT\n";}
        pair=BuildTargetExecutionPair();pair.senderJetty->SetTaSegmentBytes(segment);
        events.open(output+"-events.csv");if(!events)return 2;
        events<<"time_ns,event,wqe_id,ssn,offset,bytes,snd_una,snd_nxt,detail\n";
        pair.senderJetty->SetClientCallback(MakeCallback(&SharedJettyProbe::Callback,this));
        pair.senderTp->TraceConnectWithoutContext("WqeSegmentSendsNotify",MakeCallback(&SharedJettyProbe::Sent,this));
        if(!pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor([this](Ptr<const UbWqeSegment> r,const UbTransactionRule& rule,UbTargetCompletion done){Target(r,rule,done);}))) return 2;
        uint32_t initial=(mode=="single" || mode=="singleonesegment")?1:count;
        for(uint32_t i=0;i<initial;++i)Prepare(1001+i);
        if(mode!="single" && mode!="singleonesegment")Prepare(9001);
        Simulator::Schedule(NanoSeconds(10),[this,initial]{
            for(uint32_t i=0;i<initial;++i) {
                if(delayedLastNs && i+1==initial) Simulator::Schedule(NanoSeconds(delayedLastNs),&SharedJettyProbe::Submit,this,1001+i);
                else Submit(1001+i);
            }
        });
        if(mode!="single" && mode!="singleonesegment")Simulator::Schedule(NanoSeconds(lateNs),&SharedJettyProbe::Submit,this,9001);
        if(checkpointNs) Simulator::Schedule(NanoSeconds(checkpointNs), [this] {
            Event("checkpoint");
            for(const auto& [id,s]:states) Event("checkpoint_wqe",id,0,s.completed,s.callbacks);
        });
        Simulator::Stop(MilliSeconds(10));Simulator::Run();
        for(const auto& [id,s]:states) {
            if(!s.submitted || s.callbacks!=1)Fail("missing_or_duplicate_completion",id);
            if(s.receipts!=(s.size+segment-1)/segment || s.completed!=s.receipts ||
               std::count(s.seen.begin(),s.seen.end(),uint8_t(1))!=s.size)Fail("incomplete_target",id);
        }
        if(mode!="single" && mode!="singleonesegment" && peak<2)Fail("no_concurrent_outstanding_wqes");
        auto una=pair.senderJetty->GetTaSsnSndUnaForTest(),nxt=pair.senderJetty->GetTaSsnSndNxtForTest();
        if(una!=nxt)Fail("ack_window_not_drained");
        if(pair.senderJetty->GetActiveWqeCount()!=0 || !pair.senderJetty->IsIdle())Fail("jetty_not_idle");
        if(pair.senderTransaction->GetResidentOperationCount()!=0 ||
           pair.senderTransaction->GetActiveOperationCount()!=0 ||
           pair.senderTransaction->GetResidentSegmentCount()!=0) Fail("transaction_state_not_reclaimed");
        if(pair.senderTp->GetOutstandingUnackedSegmentCount()!=0 ||
           pair.receiverTp->GetOutstandingUnackedSegmentCount()!=0) Fail("transport_state_not_reclaimed");
        Event("final");
        std::ofstream out(output+"-summary.txt");
        out<<"status="<<(failures.empty()?"PASS":"FAIL")<<"\nmode="<<mode<<"\npeak_outstanding="<<peak
           <<"\nsnd_una="<<una<<"\nsnd_nxt="<<nxt<<"\nssn_owners="<<owners.size()<<"\nfailures="<<failures.size()<<'\n';
        for(const auto& [id,s]:states)out<<"wqe="<<id<<" size="<<s.size<<" callbacks="<<s.callbacks<<" received_segments="<<s.receipts<<" target_completions="<<s.completed<<'\n';
        for(const auto& f:failures)out<<"failure="<<f<<'\n';
        out.flush();events.close();Simulator::Destroy();return failures.empty()?0:1;
    }
};
} // namespace
int main(int argc,char**argv) {
    SharedJettyProbe p;CommandLine cli;
    cli.AddValue("mode","concurrentmulti (default), single, onesegment",p.mode);
    cli.AddValue("output","output prefix (parent directory must exist)",p.output);
    cli.AddValue("count","initial concurrent WQEs (3..16)",p.count);
    cli.AddValue("segmentBytes","TA segment bytes",p.segment);
    cli.AddValue("segments","full segments per multi WQE, plus 32-byte tail",p.segments);
    cli.AddValue("delayNs","target execution delay base",p.delayNs);
    cli.AddValue("lateNs","late WQE absolute submission time",p.lateNs);
    cli.AddValue("delayedLastNs","optional delay for last initial submission",p.delayedLastNs);
    cli.AddValue("duplicateDone","invoke target done twice to exercise dedup",p.duplicateDone);
    cli.AddValue("checkpointNs","optional passive state snapshot time",p.checkpointNs);
    cli.Parse(argc,argv);return p.Run();
}
