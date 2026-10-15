// SPDX-License-Identifier: GPL-2.0-only
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "tracker.h"
#include <fstream>
#include <memory>
#include <array>
#include <filesystem>
using namespace ns3;

// One fresh Jetty per (hop, chunk): its TASSN starts at zero. This mapping is
// explicit application metadata, not an on-wire application payload header.
class Relay {
public:
  uint32_t small=65536, large=262144, segment=8192;
  uint64_t computeNs=5000;
  std::array<Ptr<Node>,3> nodes;
  std::array<std::array<std::unique_ptr<ChunkTracker>,2>,2> trackers;
  std::array<std::array<std::vector<uint8_t>,2>,2> buffers;
  bool corrupt=false;
  static uint8_t Byte(uint32_t c,uint64_t i) { return uint8_t((i*131+(i>>8)*17+c*73+19)%256); }
  std::ofstream events;
  uint32_t completed=0, senderCompleted=0, taCount=0;
  void Event(const std::string& event, uint32_t hop, uint32_t chunk,
             uint64_t offset=0, uint64_t bytes=0) {
    events << Simulator::Now().GetPicoSeconds() << ',' << event << ','
           << hop << ',' << chunk << ',' << offset << ',' << bytes << '\n';
  }
  uint32_t Size(uint32_t c) const { return c==0?small:large; }
  Ptr<UbController> Ctrl(uint32_t n) {return nodes[n]->GetObject<UbController>();}
  void InitNode(uint32_t n, uint32_t ports) {
    nodes[n]=CreateObject<Node>();
    auto sw=CreateObject<UbSwitch>(); nodes[n]->AggregateObject(sw); sw->SetNodeType(UB_DEVICE);
    auto ctrl=CreateObject<UbController>(); nodes[n]->AggregateObject(ctrl);
    ctrl->CreateUbFunction(); ctrl->CreateUbTransaction();
    for(uint32_t p=0;p<ports;++p) {
      auto port=CreateObject<UbPort>(); port->SetAddress(Mac48Address::Allocate());
      port->SetAttribute("UbDataRate",DataRateValue(DataRate("100Gbps")));
      nodes[n]->AddDevice(port);
    }
    sw->Init(); UbCongestionControl::Create(UB_SWITCH)->OnSwitchAttached(sw);
  }
  void Route(uint32_t node,uint32_t dest,uint32_t destPort,uint16_t out) {
    auto rt=nodes[node]->GetObject<UbSwitch>()->GetRoutingProcess();
    rt->GetRoutingTable().AddShortestRoute(NodeIdToIp(nodes[dest]->GetId()).Get(),{out});
    rt->GetRoutingTable().AddShortestRoute(NodeIdToIp(nodes[dest]->GetId(),destPort).Get(),{out});
  }
  void Link(uint32_t hop,uint32_t portA,uint32_t portB) {
    auto a=nodes[hop], b=nodes[hop+1];
    auto link=CreateObject<UbLink>(); link->SetAttribute("Delay",TimeValue(NanoSeconds(20)));
    DynamicCast<UbPort>(a->GetDevice(portA))->Attach(link);
    DynamicCast<UbPort>(b->GetDevice(portB))->Attach(link);
    Route(hop,hop+1,portB,portA); Route(hop+1,hop,portA,portB);
    uint32_t tx=10+hop*2,rx=tx+1;
    Connection connection;
    connection.ownerNodeId=a->GetId(); connection.node1=a->GetId(); connection.port1=portA;
    connection.tpn1=tx; connection.node2=b->GetId(); connection.port2=portB;
    connection.tpn2=rx; connection.priority=7; connection.metrics=0;
    Ctrl(hop)->GetTpConnManager()->AddUnilateralConnection(connection,a->GetId());
    Ctrl(hop+1)->GetTpConnManager()->AddUnilateralConnection(connection,b->GetId());
    Ctrl(hop)->GetTransportChannelManager()->CreateTp(a->GetId(),b->GetId(),portA,portB,7,tx,rx,UbCongestionControl::Create(UB_DEVICE));
    Ctrl(hop+1)->GetTransportChannelManager()->CreateTp(b->GetId(),a->GetId(),portB,portA,7,rx,tx,UbCongestionControl::Create(UB_DEVICE));
    Ctrl(hop)->GetTransportChannelManager()->GetTp(tx)->TraceConnectWithoutContext(
      "WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>(
        [this,hop](uint32_t,uint32_t task,uint32_t ssn){
          uint64_t off=uint64_t(ssn)*segment;
          Event("ta_send_admitted",hop,task%100,off,std::min<uint64_t>(segment,Size(task%100)-off));
        }));
    for(uint32_t c=0;c<2;++c) {
      auto fn=Ctrl(hop)->GetUbFunction(); fn->CreateJetty(a->GetId(),b->GetId(),c);
      NS_ABORT_MSG_IF(!Ctrl(hop)->GetUbTransaction()->JettyBindTp(a->GetId(),b->GetId(),c,false,{tx}),"bind rejected");
      auto jetty=fn->GetJetty(c); jetty->SetTaSegmentBytes(segment);
      jetty->SetClientCallback(Callback<void,uint32_t,uint32_t>([this,hop,c](uint32_t,uint32_t){
        ++senderCompleted; Event("sender_wqe_complete",hop,c);
      }));
      trackers[hop][c]=std::make_unique<ChunkTracker>(Size(c));
      buffers[hop][c].resize(Size(c));
    }
    NS_ABORT_MSG_IF(!Ctrl(hop+1)->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor(
      [this,hop](Ptr<const UbWqeSegment> request,const UbTransactionRule&,UbTargetCompletion done) {
        uint32_t task=request->GetTaskId(), c=task%100;
        NS_ABORT_MSG_IF(task/100!=hop || c>=2 || request->GetType()!=UbTransactionOpcode::WRITE ||
          !request->HasTransactionResolved() || request->GetSrc()!=nodes[hop]->GetId() ||
          request->GetDest()!=nodes[hop+1]->GetId(),"unexpected inbound metadata");
        uint64_t off=uint64_t(request->GetTaSsn())*segment, len=request->GetLogicalBytes();
        NS_ABORT_MSG_IF(off>=Size(c) || len!=std::min<uint64_t>(segment,Size(c)-off) ||
                        request->GetPayloadBytes()!=len,"TA metadata length mismatch");
        Event("target_ta_received",hop,c,off,len);
        NS_ABORT_MSG_IF(!request->HasExplicitPayload() || request->GetExplicitPayload()->GetSize()!=len,"missing explicit bytes");
        std::vector<uint8_t> bytes(len);
        request->GetExplicitPayload()->CopyData(bytes.data(),len);
        for(uint64_t i=0;i<len;++i) {
          if(bytes[i]!=Byte(c,off+i)) {
            Event("payload_mismatch",hop,c,off+i,1); events.flush();
            UbUtils::Get()->Destroy();
            NS_ABORT_MSG("payload byte mismatch");
          }
          buffers[hop][c][off+i]=bytes[i];
        }
        Event("payload_bytes_verified",hop,c,off,len);
        done(UbWorkExecutionResult{}); // report successful target execution, normal TA response
        ++taCount; Event("target_ta_complete",hop,c,off,len);
        if(trackers[hop][c]->Notify(request->GetTaSsn(),off,len)) {
          Event("chunk_complete",hop,c,0,Size(c));
          if(hop==0) {
            Event("compute_start",hop,c);
            Simulator::Schedule(NanoSeconds(computeNs),[this,hop,c]{Event("compute_end",hop,c);});
            Event("forward",hop,c,0,Size(c));
            Send(1,c); // same simulation time; never wait for the other chunk or sender WQE
          } else ++completed;
        }
      })),"executor registration rejected");
  }
  void Send(uint32_t hop,uint32_t c) {
    NS_ABORT_MSG_IF(hop==1 && !trackers[0][c]->Complete(),"early forward");
    Event("chunk_send",hop,c,0,Size(c));
    auto fn=Ctrl(hop)->GetUbFunction();
    auto wqe=fn->CreateWqe(nodes[hop]->GetId(),nodes[hop+1]->GetId(),Size(c),hop*100+c,UbTransactionOpcode::WRITE);
    std::vector<uint8_t> payload(Size(c));
    if(hop==0) { for(uint64_t i=0;i<payload.size();++i) payload[i]=Byte(c,i); }
    else payload=buffers[0][c]; // forward the actually received bytes, never regenerate at B
    if(corrupt && hop==1 && c==0) payload[payload.size()/2]^=1;
    wqe->SetExplicitPayload(Create<Packet>(payload.data(),payload.size()));
    NS_ABORT_MSG_IF(fn->SubmitWqe(wqe,c).status!=UbWqeSubmissionStatus::ACCEPTED,"dynamic WQE admission rejected");
  }
  void Run(const std::string& output) {
    NS_ABORT_MSG_IF(!small || !large || !segment || small<=segment || large<=segment,"each chunk needs multiple TAs");
    events.open(output); NS_ABORT_MSG_IF(!events,"cannot open event file");
    events<<"time_ps,event,hop,chunk,offset,bytes\n";
    GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false));
    UbUtils::Get(); // instantiate utility-owned GlobalValues before configuring trace
    GlobalValue::Bind("UB_TRACE_ENABLE",BooleanValue(true));
    GlobalValue::Bind("UB_PACKET_TRACE_ENABLE",BooleanValue(true));
    GlobalValue::Bind("UB_PORT_TRACE_ENABLE",BooleanValue(true));
    GlobalValue::Bind("UB_RECORD_PKT_TRACE",BooleanValue(true));
    std::string tracePath=output+".native";
    std::filesystem::create_directories(tracePath+"/runlog");
    UbUtils::SetTracePathForTest(tracePath);
    InitNode(0,1); InitNode(1,2); InitNode(2,1);
    Link(0,0,0); Link(1,1,0);
    UbUtils::Get()->TopoTraceConnect();
    UbUtils::Get()->SingleTpTraceConnect(0,10);
    UbUtils::Get()->SingleTpTraceConnect(1,11);
    UbUtils::Get()->SingleTpTraceConnect(1,12);
    UbUtils::Get()->SingleTpTraceConnect(2,13);
    Simulator::Schedule(NanoSeconds(10),[this]{Send(0,0);Send(0,1);});
    Simulator::Stop(MilliSeconds(1)); Simulator::Run();
    NS_ABORT_MSG_IF(completed!=2 || senderCompleted!=4,"missing chunk or sender completion");
    std::cout<<"PASS network: C chunks="<<completed<<" sender completions="<<senderCompleted<<" target TAs="<<taCount<<"\n";
    events.close(); UbUtils::Get()->Destroy(); Simulator::Destroy();
  }
};
int main(int argc,char** argv) {
  Relay relay; std::string output="relay-events.csv";
  CommandLine cmd; cmd.AddValue("output","event CSV",output);
  cmd.AddValue("chunk0Bytes","chunk 0 logical bytes",relay.small);
  cmd.AddValue("chunk1Bytes","chunk 1 logical bytes",relay.large);
  cmd.AddValue("segmentBytes","TA segment bytes",relay.segment);
  cmd.AddValue("computeNs","independent B NPU duration per ready chunk",relay.computeNs);
  cmd.AddValue("corrupt","negative test: flip one byte at B before real-network forwarding",relay.corrupt);
  cmd.Parse(argc,argv); relay.Run(output); return 0;
}
