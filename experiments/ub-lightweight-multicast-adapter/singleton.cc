// SPDX-License-Identifier: GPL-2.0-only
// Native endpoint reuse; candidate exercises the switch parent/branch replication path.
#include "adapter.h"
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <vector>
#include <iostream>
using namespace ns3;
struct Test {
 bool adapter=false, pressure=false,shared=false; Ptr<lightweight::SharedSource> sharedSource; std::string out;
 uint32_t bytes=4096,count=1,segment=1024,window=1000; uint64_t delay=0,processing=0;
 std::vector<Ptr<Node>> nodes; Ptr<UbJetty> jetty; Ptr<UbTransportChannel> tx,rx;
 std::map<uint32_t,std::vector<uint8_t>> original,received;
 std::map<uint32_t,uint32_t> nextOffset; std::map<uint32_t,std::pair<uint32_t,uint32_t>> admitted;
 std::set<uint32_t> seenSsn,ready,completed;
 struct PortStats {uint64_t consumed=0,returned=0,peak=0;};
 std::map<std::pair<uint32_t,uint32_t>,PortStats> ports; uint64_t ingressPeak=0;
 uint64_t submitted=0,tagged=0; std::ofstream events,wire;
 Ptr<UbController> Ctrl(uint32_t n){return nodes[n]->GetObject<UbController>();}
 void State(const std::string& event,uint32_t task=0,uint32_t ssn=0,uint32_t off=0,uint32_t len=0){
  events<<Simulator::Now().GetPicoSeconds()<<','<<event<<','<<task<<','<<ssn<<','<<off<<','<<len<<','
   <<jetty->GetTaSsnSndUnaForTest()<<','<<jetty->GetTaSsnSndNxtForTest()<<','
   <<tx->GetPsnSndUna()<<','<<tx->GetPsnSndNxt()<<','<<tx->GetOutstandingUnackedSegmentCount()<<','
   <<rx->GetPsnSndUna()<<','<<rx->GetPsnSndNxt()<<','<<rx->GetOutstandingUnackedSegmentCount()<<'\n';
 }
 void PacketEvent(uint32_t node,uint32_t port,const std::string& event,Ptr<Packet> p){
  auto sw=nodes[node]->GetObject<UbSwitch>(); auto kind=sw->GetPacketTypeForTest(p);
  uint32_t opcode=999,ta=999,psn=0,ssn=0,task=0;
  if(kind==UB_URMA_DATA_PACKET){
   auto& st=ports[{node,port}];if(event=="tx")st.consumed+=(p->GetSize()+159)/160;else st.returned+=(p->GetSize()+159)/160;
   auto cp=p->Copy(); UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader tp;
   cp->RemoveHeader(dl);cp->RemoveHeader(net);cp->RemoveHeader(ip);cp->RemoveHeader(udp);cp->RemoveHeader(tp);
   opcode=tp.GetTPOpcode();psn=tp.GetPsn();
   if(!UbTransportChannel::IsTransportResponseOpcode(opcode)){
    UbTransportChannel::ReceivedDataPacketContext ctx;
    NS_ABORT_MSG_IF(!tx->ParseReceivedDataPacketForTest(p->Copy(),ctx),"production decode failed");
    ta=uint32_t(ctx.transactionHeader.GetUbTransactionOpcode()); ssn=ctx.transactionHeader.GetIniTaSsn(); task=ctx.flowTag.GetFlowId();
    if(adapter && !shared && node==0 && event=="tx" && ta==uint32_t(UbTransactionOpcode::WRITE)){
     UbNetworkReplicationTag tag;tag.destinations=uint64_t{1}<<1;tag.object=task;tag.sequence=psn;tag.nativeSingleton=true;
     p->AddPacketTag(tag);++tagged;
    }
   }
  }
  std::vector<uint8_t> b(p->GetSize());p->CopyData(b.data(),b.size());uint64_t h=14695981039346656037ULL;for(auto v:b){h^=v;h*=1099511628211ULL;}
  wire<<Simulator::Now().GetPicoSeconds()<<','<<event<<','<<node<<','<<port<<','<<p->GetSize()<<','<<int(kind)<<','<<opcode<<','<<ta<<','<<psn<<','<<ssn<<','<<task<<','<<h<<','; const char* hex="0123456789abcdef";for(auto v:b)wire<<hex[v>>4]<<hex[v&15];wire<<'\n';
  State(event+"_"+std::to_string(node)+"_"+std::to_string(port),task,ssn,0,p->GetSize());
 }
 void Complete(uint32_t task,uint32_t){NS_ABORT_MSG_IF(!ready.count(task)||!completed.insert(task).second,"early/duplicate sender completion");State("sender_complete",task);}
 void Init(){
  GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false)); utils::UbUtils::Get();
  for(auto k:{"UB_TRACE_ENABLE","UB_PACKET_TRACE_ENABLE","UB_PORT_TRACE_ENABLE","UB_RECORD_PKT_TRACE"})GlobalValue::Bind(k,BooleanValue(false));
  Config::SetDefault("ns3::UbSwitch::InPortProcessingDelay",TimeValue(NanoSeconds(processing)));
  Config::SetDefault("ns3::UbTransportChannel::DefaultMaxInflightPacketSize",UintegerValue(window));
  Config::SetDefault("ns3::UbTransportChannel::DefaultMaxWqeSegNum",UintegerValue(window));
  Config::SetDefault("ns3::UbJetty::UbJettyInflightMax",UintegerValue(std::min(512u,window)));
  if(pressure){UbEgressQueue::GetTypeId();Config::SetDefault("ns3::UbEgressQueue::MaxEgressBytes",UintegerValue(4608));Config::SetDefault("ns3::UbPort::CbfcCtrlCrdRtrThldCell",IntegerValue(1));}
  for(uint32_t n=0;n<3;++n){auto node=CreateObject<Node>();nodes.push_back(node);auto sw=CreateObject<UbSwitch>();node->AggregateObject(sw);sw->SetNodeType(n==2?UB_SWITCH:UB_DEVICE);
   if(n<2){auto c=CreateObject<UbController>();node->AggregateObject(c);c->CreateUbFunction();c->CreateUbTransaction();}
   if(pressure){sw->SetReservePerQueueBytes(4640);sw->SetCbfcCredits(29,0);sw->SetCbfcCellGeometry(20,8);sw->SetCbfcReturnCellGrain(1,1);}
   for(uint32_t p=0;p<(n==2?2:1);++p){auto port=CreateObject<UbPort>();port->SetAddress(Mac48Address::Allocate());port->SetAttribute("UbDataRate",DataRateValue(DataRate("100Gbps")));node->AddDevice(port);}
   sw->Init();UbCongestionControl::Create(UB_SWITCH)->OnSwitchAttached(sw);
   sw->GetQueueManager()->TraceConnectWithoutContext("IngressQueueOccupancyBytes",Callback<void,uint32_t,uint32_t,uint64_t>([this](uint32_t,uint32_t,uint64_t used){ingressPeak=std::max(ingressPeak,used);}));
  }
  for(uint32_t n=0;n<2;++n){auto l=CreateObject<UbLink>();l->SetAttribute("Delay",TimeValue(NanoSeconds(20)));DynamicCast<UbPort>(nodes[n]->GetDevice(0))->Attach(l);DynamicCast<UbPort>(nodes[2]->GetDevice(n))->Attach(l);}
  for(uint32_t n=0;n<3;++n)for(uint32_t d=0;d<2;++d)if(n!=d){auto& table=nodes[n]->GetObject<UbSwitch>()->GetRoutingProcess()->GetRoutingTable();uint16_t p=n==2?d:0;table.AddShortestRoute(NodeIdToIp(d).Get(),{p});table.AddShortestRoute(NodeIdToIp(d,0).Get(),{p});}
  if(adapter)nodes[2]->GetObject<UbSwitch>()->EnableNetworkReplication({0,1});
  Connection c;c.ownerNodeId=0;c.node1=0;c.node2=1;c.port1=c.port2=0;c.tpn1=101;c.tpn2=202;c.priority=7;c.metrics=0;
  for(uint32_t n=0;n<2;++n){Ctrl(n)->GetTpConnManager()->AddUnilateralConnection(c,n);Ctrl(n)->GetTransportChannelManager()->CreateTp(n,1-n,0,0,7,n?202:101,n?101:202,UbCongestionControl::Create(UB_DEVICE));}
  tx=Ctrl(0)->GetTransportChannelManager()->GetTp(101);rx=Ctrl(1)->GetTransportChannelManager()->GetTp(202);
  auto fn=Ctrl(0)->GetUbFunction();fn->CreateJetty(0,1,3);NS_ABORT_MSG_IF(!Ctrl(0)->GetUbTransaction()->JettyBindTp(0,1,3,false,{101}),"bind");jetty=fn->GetJetty(3);jetty->SetTaSegmentBytes(segment);jetty->SetClientCallback(MakeCallback(&Test::Complete,this));
  tx->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this](uint32_t,uint32_t task,uint32_t ssn){uint32_t off=nextOffset[task],len=std::min(segment,bytes-off);NS_ABORT_MSG_IF(!admitted.emplace(ssn,std::make_pair(task,off)).second,"duplicate admission");nextOffset[task]+=len;if(sharedSource)sharedSource->Refresh();State("ta_admitted",task,ssn,off,len);}));
  if(shared){NS_ABORT_MSG_IF(!adapter,"shared queue requires adapter mode");sharedSource=CreateObject<lightweight::SharedSource>();auto p=DynamicCast<UbPort>(nodes[0]->GetDevice(0));sharedSource->Install(p,{{1,tx}});sharedSource->Select(0,0,{1});p->SetReceiveHandler(Callback<void,Ptr<UbPort>,Ptr<Packet>>([this](Ptr<UbPort> port,Ptr<Packet> packet){nodes[0]->GetObject<UbSwitch>()->SwitchHandlePacket(port,packet);sharedSource->Refresh();}));}
  Ctrl(1)->GetUbTransaction()->SetTargetExecutionDelay(NanoSeconds(delay));
  NS_ABORT_MSG_IF(!Ctrl(1)->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor([this](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){
   auto ssn=req->GetTaSsn();auto task=req->GetTaskId();NS_ABORT_MSG_IF(!admitted.count(ssn)||admitted.at(ssn).first!=task||!seenSsn.insert(ssn).second,"invalid target identity");auto off=admitted.at(ssn).second;auto len=req->GetPayloadBytes();
   NS_ABORT_MSG_IF(req->GetType()!=UbTransactionOpcode::WRITE||req->GetDest()!=1||req->GetSrc()!=0||req->GetJettyNum()!=3||len!=std::min(segment,bytes-off),"target shape");
   std::vector<uint8_t> b(len);req->GetExplicitPayload()->CopyData(b.data(),len);NS_ABORT_MSG_IF(!std::equal(b.begin(),b.end(),original.at(task).begin()+off),"payload corruption");std::copy(b.begin(),b.end(),received.at(task).begin()+off);State("target_execute",task,ssn,off,len);done(UbWorkExecutionResult{});State("target_complete",task,ssn,off,len);
   uint64_t covered=0;for(auto x:seenSsn)if(admitted.at(x).first==task)covered+=std::min(segment,bytes-admitted.at(x).second);
   if(covered==bytes){NS_ABORT_MSG_IF(!ready.insert(task).second,"duplicate ready");State("receiver_ready",task);}
  })),"executor");
  for(uint32_t n=0;n<3;++n)for(uint32_t p=0;p<nodes[n]->GetNDevices();++p){auto port=DynamicCast<UbPort>(nodes[n]->GetDevice(p));port->GetUbQueue()->TraceConnectWithoutContext("UbEnqueue",Callback<void,Ptr<const Packet>,uint32_t>([this,n,p](Ptr<const Packet>,uint32_t used){ports[{n,p}].peak=std::max(ports[{n,p}].peak,uint64_t(used));}));port->TraceConnectWithoutContext("TraComEventNotify",Callback<void,Ptr<Packet>,Time>([this,n,p](Ptr<Packet> packet,Time){PacketEvent(n,p,"tx",packet);}));port->TraceConnectWithoutContext("PktRcvNotify",Callback<void,Ptr<Packet>>([this,n,p](Ptr<Packet> packet){PacketEvent(n,p,"rx",packet);}));}
 }
 void Run(){std::filesystem::create_directories(out);events.open(out+"/events.csv");wire.open(out+"/wire.csv");events<<"time_ps,event,task,ssn,offset,bytes,ta_una,ta_nxt,tx_una,tx_nxt,tx_segments,rx_una,rx_nxt,rx_segments\n";wire<<"time_ps,event,node,port,wire_bytes,kind,tp_opcode,ta_opcode,psn,ssn,task,wire_fnv1a64,wire_hex\n";Init();
  for(uint32_t i=0;i<count;++i){uint32_t id=1001+i;original[id].resize(bytes);received[id].resize(bytes);for(uint32_t b=0;b<bytes;++b)original[id][b]=uint8_t((id*73+b*131+(b>>8)*17)%251);}
  Simulator::Schedule(NanoSeconds(100),[this]{for(uint32_t i=0;i<count;++i){uint32_t id=1001+i;State("submit",id);auto w=Ctrl(0)->GetUbFunction()->CreateWqe(0,1,bytes,id,UbTransactionOpcode::WRITE);w->SetExplicitPayload(Create<Packet>(original[id].data(),bytes));NS_ABORT_MSG_IF(Ctrl(0)->GetUbFunction()->SubmitWqe(w,3).status!=UbWqeSubmissionStatus::ACCEPTED,"submit");++submitted;}});
  Simulator::Stop(MilliSeconds(10));Simulator::Run();State("final_drain");NS_ABORT_MSG_IF(completed.size()!=count||ready.size()!=count||!jetty->IsIdle()||!tx->IsSafeForExplicitDestroy()||!rx->IsSafeForExplicitDestroy(),"unfinished endpoint");
  for(auto&[task,b]:original){NS_ABORT_MSG_IF(received[task]!=b,"final payload");std::ofstream f(out+"/payload-"+std::to_string(task)+".bin",std::ios::binary);f.write((char*)received[task].data(),bytes);}
  auto s=nodes[2]->GetObject<UbSwitch>()->GetNetworkReplicationStats();if(shared)tagged=s.admitted;NS_ABORT_MSG_IF(adapter&&(!tagged||s.admitted!=tagged||s.branches!=tagged||s.released!=tagged||s.parentBytes||s.branchBytes||s.descriptors),"replication not exercised/drained");
  std::ofstream resource(out+"/ports.csv");resource<<"node,port,egress_peak,consumed,returned,restored,free,pending,blocked\n";uint64_t blocked=0;
  for(uint32_t n=0;n<3;++n)for(uint32_t p=0;p<nodes[n]->GetNDevices();++p){auto port=DynamicCast<UbPort>(nodes[n]->GetDevice(p));auto fc=DynamicCast<UbCbfc>(port->GetFlowControl());auto st=ports[{n,p}];uint64_t initial=pressure?29:6553;
   NS_ABORT_MSG_IF(fc->GetConsumedCells()!=st.consumed||fc->GetReturnedCells()!=st.returned,"credit trace balance");
   NS_ABORT_MSG_IF(int64_t(initial)-int64_t(fc->GetConsumedCells())+int64_t(fc->GetRestoredCells())!=fc->GetTxFreeCells(7),"credit conservation");
   NS_ABORT_MSG_IF(st.peak>(pressure?4608:524288)||port->GetUbQueue()->GetCurrentBytes(),"egress overflow/leak");blocked+=fc->GetBlockedQueryCount();
   resource<<n<<','<<p<<','<<st.peak<<','<<fc->GetConsumedCells()<<','<<fc->GetReturnedCells()<<','<<fc->GetRestoredCells()<<','<<fc->GetTxFreeCells(7)<<','<<fc->GetCrdToReturn(7)<<','<<fc->GetBlockedQueryCount()<<'\n';
  }
  NS_ABORT_MSG_IF(ingressPeak>(pressure?4640:1048576)||nodes[2]->GetObject<UbSwitch>()->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes,"ingress overflow/leak");
  NS_ABORT_MSG_IF(pressure&&!blocked,"pressure did not exercise blocking");
  std::ofstream result(out+"/summary.json");result<<"{\"status\":\"PASS\",\"adapter\":"<<adapter<<",\"tagged\":"<<tagged<<",\"parents\":"<<s.admitted<<",\"branches\":"<<s.branches<<",\"released\":"<<s.released<<",\"completed_wqes\":"<<completed.size()<<",\"target_tas\":"<<seenSsn.size()<<"}\n";events.close();wire.close();Simulator::Destroy();std::cout<<"PASS singleton\n";
 }
};
int main(int argc,char**argv){Time::SetResolution(Time::PS);Test t;CommandLine c;c.AddValue("out","Private evidence",t.out);c.AddValue("adapter","Singleton replication",t.adapter);c.AddValue("bytes","Bytes per WQE",t.bytes);c.AddValue("count","Concurrent WQEs",t.count);c.AddValue("segment","TA bytes",t.segment);c.AddValue("window","Window bound",t.window);c.AddValue("delay","Target execution ns",t.delay);c.AddValue("pressure","Small queues/credits",t.pressure);c.AddValue("shared","Shared native source queue",t.shared);c.AddValue("processing","Switch pipeline ns",t.processing);c.Parse(argc,argv);NS_ABORT_MSG_IF(t.out.empty()||!t.count||!t.bytes||!t.segment||!t.window,"invalid config");t.Run();}
