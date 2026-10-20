// SPDX-License-Identifier: GPL-2.0-only
#include "adapter-retrans.h"
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
using namespace ns3;
struct Multi {
 std::string out,scenario="basic",fault,mode="v2";uint32_t bytes=16384,window=1000;bool pressure=false,mixed=false,dwrr=false;
 std::vector<Ptr<Node>> nodes;std::map<uint32_t,Ptr<UbTransportChannel>> sendTp,recvTp;std::map<uint32_t,Ptr<UbJetty>> jetties;
 Ptr<lightweight::SharedSource> shared; Ptr<retransmission::SharedSource> v2;
 std::string loss="normal";uint32_t drops=0,repeats=0;bool enabled=true;std::ofstream packets;
 std::map<std::pair<uint32_t,uint32_t>,std::vector<uint8_t>> headerReference; uint64_t headerChecks=0;std::ofstream events,wire,windows;
 struct Port {uint64_t consumed=0,returned=0,peak=0;};std::map<std::pair<uint32_t,uint32_t>,Port> ps;
 std::map<uint32_t,std::vector<uint32_t>> members;std::map<uint32_t,std::vector<uint8_t>> source;
 std::map<std::pair<uint32_t,uint32_t>,std::vector<uint8_t>> got;std::map<std::pair<uint32_t,uint32_t>,uint32_t> nextOffset,covered,nextEnvelope;std::map<std::tuple<uint32_t,uint32_t,uint32_t>,uint32_t> chunks;
 std::map<std::pair<uint32_t,uint32_t>,std::pair<uint32_t,uint32_t>> ownership;
 std::set<std::pair<uint32_t,uint32_t>> seenTa,ready,senderDone;std::set<uint32_t> groupsDone;std::set<std::pair<uint32_t,uint32_t>> seenFeedback;
 uint64_t ingressPeak=0,feedback=0;bool injected=false;Ptr<UbTransportChannel> bgTx,bgRx;Ptr<UbJetty> bgJetty;uint32_t bgNext=0,bgCovered=0;bool bgDone=false;std::map<uint32_t,uint32_t> bgOffsets;
 Ptr<UbController> C(uint32_t n){return nodes[n]->GetObject<UbController>();}
 void Windows(const std::string& where){for(auto& [rank,tp]:sendTp){auto j=jetties.at(rank);windows<<Simulator::Now().GetPicoSeconds()<<','<<where<<','<<rank<<','<<tp->GetPsnSndUna()<<','<<tp->GetPsnSndNxt()<<','<<tp->GetOutstandingUnackedSegmentCount()<<','<<j->GetTaSsnSndUnaForTest()<<','<<j->GetTaSsnSndNxtForTest()<<','<<tp->GetGbnDescriptorCountForTest()<<','<<tp->IsRetransTimerRunningForTest()<<','<<recvTp[rank]->GetGbnDescriptorCountForTest()<<','<<recvTp[rank]->IsRetransTimerRunningForTest()<<','<<tp->GetPendingSelectiveRetransmissionCountForTest()<<'\n';windows.flush();}}
 void Event(const std::string& name,uint32_t task=0,uint32_t rank=0,uint32_t off=0,uint32_t len=0){events<<Simulator::Now().GetPicoSeconds()<<','<<name<<','<<task<<','<<rank<<','<<off<<','<<len<<'\n';events.flush();Windows(name);}
 void Pair(uint32_t src,uint32_t dst,uint32_t a,uint32_t b,Ptr<UbTransportChannel>& tx,Ptr<UbTransportChannel>& rx){Connection c;c.ownerNodeId=src;c.node1=src;c.node2=dst;c.port1=c.port2=0;c.tpn1=a;c.tpn2=b;c.priority=7;c.metrics=0;
  C(src)->GetTpConnManager()->AddUnilateralConnection(c,src);C(dst)->GetTpConnManager()->AddUnilateralConnection(c,dst);
  C(src)->GetTransportChannelManager()->CreateTp(src,dst,0,0,7,a,b,UbCongestionControl::Create(UB_DEVICE));C(dst)->GetTransportChannelManager()->CreateTp(dst,src,0,0,7,b,a,UbCongestionControl::Create(UB_DEVICE));tx=C(src)->GetTransportChannelManager()->GetTp(a);rx=C(dst)->GetTransportChannelManager()->GetTp(b);
 }
 void ReferenceHeader(Ptr<Packet> p,bool received=false){
  UbTransportChannel::ReceivedDataPacketContext ctx;
  NS_ABORT_MSG_IF(!sendTp.at(1)->ParseReceivedDataPacketForTest(p->Copy(),ctx),"header reference parse");
  if(ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE))return;
  auto q=p->Copy();UbDatalinkPacketHeader dl;q->RemoveHeader(dl);
  std::vector<uint8_t>b(q->GetSize()-ctx.payloadBytes);q->CopyData(b.data(),b.size());
  auto key=std::make_pair(ctx.transportHeader.GetDestTpn(),ctx.transportHeader.GetPsn());
  if(received){NS_ABORT_MSG_IF(!headerReference.count(key)||headerReference.at(key)!=b,"received native header differs from native child");headerReference.erase(key);++headerChecks;}
  else NS_ABORT_MSG_IF(!headerReference.emplace(key,b).second,"duplicate native reference");
 }
 void PacketLog(uint32_t n,uint32_t p,const std::string& ev,Ptr<Packet> packet){ Evidence(n,p,ev,packet);UbNetworkReplicationTag tag;bool v2wire=UbWriteV2::IsEnvelope(packet);bool envelope=v2wire||(packet->PeekPacketTag(tag)&&tag.nativeEnvelope);auto kind=envelope?UB_URMA_DATA_PACKET:nodes[n]->GetObject<UbSwitch>()->GetPacketTypeForTest(packet);uint32_t type=envelope?1:(kind==UB_CONTROL_FRAME?0:2),tp=999,ta=999,task=0;
  if(envelope){task=tag.object;if(v2wire){auto q=packet->Copy();UbDatalinkPacketHeader dl;q->RemoveHeader(dl);std::vector<uint8_t>b(q->GetSize());q->CopyData(b.data(),b.size());task=UbWriteV2::Decode(b).operation;}}
  else if(kind==UB_URMA_DATA_PACKET){auto copy=packet->Copy();UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader h;copy->RemoveHeader(dl);copy->RemoveHeader(net);copy->RemoveHeader(ip);copy->RemoveHeader(udp);copy->RemoveHeader(h);tp=h.GetTPOpcode();if(!UbTransportChannel::IsTransportResponseOpcode(tp)){UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!sendTp.at(1)->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"wire decode");ta=uint32_t(ctx.transactionHeader.GetUbTransactionOpcode());task=ctx.flowTag.GetFlowId();}}
  
  if(type){auto& s=ps[{n,p}];if(ev=="tx")s.consumed+=(packet->GetSize()+159)/160;else s.returned+=(packet->GetSize()+159)/160;}
  std::string cls=envelope?"multicast_data":(type==0?"credit":(ta==999?"transport_ack":(ta==uint32_t(UbTransactionOpcode::WRITE)?"write":"response")));
  wire<<Simulator::Now().GetPicoSeconds()<<','<<ev<<','<<n<<','<<p<<','<<packet->GetSize()<<','<<type<<','<<tp<<','<<ta<<','<<task<<','<<cls<<'\n';Windows(ev);
 }
 void ReceiveEnvelope(uint32_t rank,uint32_t task,uint32_t seq,Ptr<Packet> payload){NS_ABORT_MSG_IF(!members.count(task)||std::find(members.at(task).begin(),members.at(task).end(),rank)==members.at(task).end()||seq!=nextEnvelope[std::make_pair(task,rank)]++,"wrong/duplicate envelope");auto packet=lightweight::Reconstruct(rank,task,seq,payload);UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!recvTp.at(rank)->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"reconstructed decode");
  auto endpoint=C(rank)->GetTransportChannelManager()->ResolveInboundTp(ctx.transportHeader.GetSrcTpn(),ctx.transportHeader.GetDestTpn(),ctx.ipv4Header.GetSource(),ctx.ipv4Header.GetDestination(),ctx.dataLinkHeader.GetPacketVL());
  NS_ABORT_MSG_IF(endpoint.state!=UbInboundTpState::LIVE||endpoint.endpoint!=recvTp.at(rank)||ctx.flowTag.GetFlowId()!=task||ctx.payloadBytes>1024,"wrong reconstructed endpoint");Event("envelope_received",task,rank,seq,ctx.payloadBytes);recvTp.at(rank)->RecvDataPacket(packet);
 }
 void MemberDone(uint32_t rank,uint32_t task,uint32_t){NS_ABORT_MSG_IF(!ready.count({task,rank})||!senderDone.insert({task,rank}).second,"early/duplicate native sender complete");Event("sender_complete",task,rank);if(shared->MemberComplete(rank,task)){NS_ABORT_MSG_IF(!groupsDone.insert(task).second,"duplicate group complete");Event("group_complete",task);if(scenario=="dynamic"&&task==1001)Simulator::ScheduleNow([this]{Submit(1002);});}}
 void Submit(uint32_t task){auto ranks=members.at(task);shared->Select(task,bytes,ranks);Event("group_submit",task,0,0,bytes);for(auto rank:ranks){auto w=C(0)->GetUbFunction()->CreateWqe(0,rank,bytes,task,UbTransactionOpcode::WRITE);if(mixed && rank%2==0){auto fields=w->GetTransactionFields();fields.userData=UbUserDataFields{1,2,3,0};w->SetTransactionFields(fields);}
 w->SetExplicitPayload(Create<Packet>(source[task].data(),bytes));NS_ABORT_MSG_IF(C(0)->GetUbFunction()->SubmitWqe(w,10+rank).status!=UbWqeSubmissionStatus::ACCEPTED,"group child admission");}shared->Refresh();}
 void SourceReceive(Ptr<UbPort> port,Ptr<Packet> packet){
  nodes[0]->GetObject<UbSwitch>()->SwitchHandlePacket(port,packet);shared->Refresh();Windows("source_receive_done");
 }
 struct Identity {uint32_t src=999,dst=999,psn=999,ssn=999,op=999,tp=999,stpn=999,dtpn=999,task=0,len=0;uint64_t hash=0;};
 Identity Decode(Ptr<Packet> p){Identity x;if(UbWriteV2::IsEnvelope(p))return x;UbDatalinkHeader common;p->PeekHeader(common);if(common.GetConfig()!=3)return x;
  auto q=p->Copy();UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader tp;
  q->RemoveHeader(dl);if(dl.GetConfig()!=3)return x;
  q->RemoveHeader(net);q->RemoveHeader(ip);q->RemoveHeader(udp);q->RemoveHeader(tp);
  x.src=(ip.GetSource().Get()>>8)&255;x.dst=(ip.GetDestination().Get()>>8)&255;
  x.psn=tp.GetPsn();x.tp=tp.GetTPOpcode();x.stpn=tp.GetSrcTpn();x.dtpn=tp.GetDestTpn();
  if(!UbTransportChannel::IsTransportResponseOpcode(x.tp)){
   UbTransportChannel::ReceivedDataPacketContext c;NS_ABORT_MSG_IF(!sendTp.at(1)->ParseReceivedDataPacketForTest(p->Copy(),c),"identity parse");
   x.ssn=c.transactionHeader.GetIniTaSsn();x.op=c.transactionHeader.GetUbTransactionOpcode();x.task=c.flowTag.GetFlowId();x.len=c.payloadBytes;
   std::vector<uint8_t>b(p->GetSize());p->CopyData(b.data(),b.size());x.hash=lightweight::PayloadChecksum(b.data()+b.size()-x.len,x.len);
  }return x;
 }
 void Evidence(uint32_t n,uint32_t port,const std::string& event,Ptr<Packet> p){auto x=Decode(p);
  packets<<Simulator::Now().GetPicoSeconds()<<','<<event<<','<<n<<','<<port<<','<<p->GetUid()<<','<<p->GetSize()<<','<<UbWriteV2::IsEnvelope(p)<<','<<x.stpn<<','<<x.dtpn<<','<<x.psn<<','<<x.ssn<<','<<x.tp<<','<<x.op<<','<<x.task<<','<<x.len<<','<<x.hash<<'\n';packets.flush();
 }
 uint32_t Fault(uint32_t n,Ptr<Packet> p){auto x=Decode(p);Evidence(n,0,"tp_boundary",p);
  bool request=(n==1&&x.stpn==101&&x.op==uint32_t(UbTransactionOpcode::WRITE)&&x.psn==11);
  bool ack=(n==0&&x.stpn==201&&UbTransportChannel::IsTransportResponseOpcode(x.tp)&&x.psn==11);
  bool response=(n==0&&x.stpn==201&&x.op==uint32_t(UbTransactionOpcode::TAACK)&&x.psn==11);
  bool persistent=loss=="persistent-bounded"||loss=="persistent-exhaust";
  if((request&&(loss=="data-once"||loss=="retrans-disabled"||persistent)&&(drops==0||persistent)) ||
     (ack&&loss=="ack-once"&&!drops)||(response&&loss=="response-once"&&!drops)){
   ++drops;Evidence(n,0,"drop",p);Event("drop",1001,1,x.psn,p->GetSize());return 0;
  }
  if(request&&loss=="duplicate"&&!repeats){++repeats;Evidence(n,0,"duplicate",p);Event("duplicate",1001,1,x.psn,p->GetSize());return 2;}
  return 1;
 }
 void Init(){if(dwrr)Config::SetDefault("ns3::UbSwitch::VlScheduler",StringValue("DWRR"));GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false));utils::UbUtils::Get();for(auto key:{"UB_TRACE_ENABLE","UB_PACKET_TRACE_ENABLE","UB_PORT_TRACE_ENABLE","UB_RECORD_PKT_TRACE"})GlobalValue::Bind(key,BooleanValue(false));
  Config::SetDefault("ns3::UbTransportChannel::DefaultMaxInflightPacketSize",UintegerValue(window));Config::SetDefault("ns3::UbTransportChannel::DefaultMaxWqeSegNum",UintegerValue(1000));Config::SetDefault("ns3::UbJetty::UbJettyInflightMax",UintegerValue(512));
  if(pressure){UbEgressQueue::GetTypeId();Config::SetDefault("ns3::UbEgressQueue::MaxEgressBytes",UintegerValue(1600));Config::SetDefault("ns3::UbPort::CbfcCtrlCrdRtrThldCell",IntegerValue(1));}
  for(uint32_t n=0;n<6;++n){auto node=CreateObject<Node>();nodes.push_back(node);auto sw=CreateObject<UbSwitch>();node->AggregateObject(sw);sw->SetNodeType(n==5?UB_SWITCH:UB_DEVICE);if(n<5){auto c=CreateObject<UbController>();node->AggregateObject(c);c->CreateUbFunction();c->CreateUbTransaction();}if(pressure){sw->SetReservePerQueueBytes(1600);sw->SetCbfcCredits(10,0);sw->SetCbfcCellGeometry(20,8);sw->SetCbfcReturnCellGrain(1,1);}
   for(uint32_t p=0;p<(n==5?5:1);++p){auto port=CreateObject<UbPort>();port->SetAddress(Mac48Address::Allocate());port->SetAttribute("UbDataRate",DataRateValue(DataRate("100Gbps")));node->AddDevice(port);}sw->Init();UbCongestionControl::Create(UB_SWITCH)->OnSwitchAttached(sw);sw->GetQueueManager()->TraceConnectWithoutContext("IngressQueueOccupancyBytes",Callback<void,uint32_t,uint32_t,uint64_t>([this](uint32_t,uint32_t,uint64_t v){ingressPeak=std::max(ingressPeak,v);}));}
  for(uint32_t n=0;n<5;++n){auto link=CreateObject<UbLink>();link->SetAttribute("Delay",TimeValue(NanoSeconds(20)));DynamicCast<UbPort>(nodes[n]->GetDevice(0))->Attach(link);DynamicCast<UbPort>(nodes[5]->GetDevice(n))->Attach(link);}
  for(uint32_t n=0;n<6;++n)for(uint32_t d=0;d<5;++d)if(n!=d){uint16_t p=n==5?d:0;auto& t=nodes[n]->GetObject<UbSwitch>()->GetRoutingProcess()->GetRoutingTable();t.AddShortestRoute(NodeIdToIp(d).Get(),{p});t.AddShortestRoute(NodeIdToIp(d,0).Get(),{p});}
  nodes[5]->GetObject<UbSwitch>()->EnableNetworkReplication({0,1,2,3,4});
  std::vector<lightweight::SharedSource::Child> children;
  for(uint32_t rank=1;rank<=3;++rank){Pair(0,rank,100+rank,200+rank,sendTp[rank],recvTp[rank]);auto fn=C(0)->GetUbFunction();fn->CreateJetty(0,rank,10+rank);NS_ABORT_MSG_IF(!C(0)->GetUbTransaction()->JettyBindTp(0,rank,10+rank,false,{100+rank}),"bind child");auto jetty=fn->GetJetty(10+rank);jetties[rank]=jetty;jetty->SetTaSegmentBytes(1024);jetty->SetClientCallback(Callback<void,uint32_t,uint32_t>([this,rank](uint32_t task,uint32_t jetty){MemberDone(rank,task,jetty);}));children.push_back({rank,sendTp[rank]});
   sendTp[rank]->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this,rank](uint32_t,uint32_t task,uint32_t ssn){uint32_t off=nextOffset[{task,rank}],len=std::min(1024u,bytes-off);NS_ABORT_MSG_IF(!ownership.emplace(std::make_pair(rank,ssn),std::make_pair(task,off)).second,"duplicate child admission");nextOffset[{task,rank}]+=len;if(shared)shared->Refresh();Event("ta_admitted",task,rank,off,len);}));
   if(mode=="v1") nodes[rank]->GetObject<UbSwitch>()->EnableNetworkSink(rank,Callback<void,uint32_t,uint32_t,Ptr<Packet>>([this,rank](uint32_t task,uint32_t seq,Ptr<Packet> p){ReceiveEnvelope(rank,task,seq,p);}));
   NS_ABORT_MSG_IF(!C(rank)->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor([this,rank](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){uint32_t task=req->GetTaskId(),ssn=req->GetTaSsn(),off=0,len=req->GetPayloadBytes();
    if(task==9001){NS_ABORT_MSG_IF(rank!=1||!bgOffsets.count(ssn),"background identity");off=bgOffsets.at(ssn);std::vector<uint8_t> b(len);req->GetExplicitPayload()->CopyData(b.data(),len);for(uint32_t i=0;i<len;++i)NS_ABORT_MSG_IF(b[i]!=uint8_t((off+i)*17),"background payload");bgCovered+=len;done(UbWorkExecutionResult{});Event("background_target",task,rank,off,len);return;}
    auto key=std::make_pair(rank,ssn);NS_ABORT_MSG_IF(!ownership.count(key)||ownership.at(key).first!=task||!seenTa.insert(key).second||req->GetDest()!=rank||req->GetSrc()!=0||req->GetJettyNum()!=10+rank,"target TA identity");off=ownership.at(key).second;NS_ABORT_MSG_IF(len!=std::min(1024u,bytes-off),"target length");std::vector<uint8_t> b(len);req->GetExplicitPayload()->CopyData(b.data(),len);NS_ABORT_MSG_IF(!std::equal(b.begin(),b.end(),source.at(task).begin()+off),"target payload");std::copy(b.begin(),b.end(),got[{task,rank}].begin()+off);done(UbWorkExecutionResult{});Event("target_complete",task,rank,off,len);auto chunk=off/4096*4096;auto& chunkBytes=chunks[{task,rank,chunk}];chunkBytes+=len;NS_ABORT_MSG_IF(chunkBytes>std::min(4096u,bytes-chunk),"chunk overcoverage");if(chunkBytes==std::min(4096u,bytes-chunk))Event("chunk_ready",task,rank,chunk,chunkBytes);covered[{task,rank}]+=len;if(covered[{task,rank}]==bytes){NS_ABORT_MSG_IF(!ready.insert({task,rank}).second,"duplicate ready");Event("receiver_ready",task,rank);}
   })),"executor");
  }
  for(auto& [rank,tp]:sendTp){for(auto endpoint:{tp,recvTp.at(rank)}){endpoint->SetRetransEnable(enabled);endpoint->SetRetransmissionMode(UbRetransmissionMode::GBN);endpoint->SetBaseRto(NanoSeconds(5000));endpoint->SetRetransTimeoutMode(UbRetransTimeoutMode::STATIC);endpoint->SetMaxRetransAttempts(4);}}
  for(uint32_t n=0;n<4;++n)nodes[n]->GetObject<UbSwitch>()->transportDeliveryFaultForTest=Callback<uint32_t,Ptr<Packet>>([this,n](Ptr<Packet> p){return Fault(n,p);});
  auto sourcePort=DynamicCast<UbPort>(nodes[0]->GetDevice(0));
  if(mode=="v1"){shared=CreateObject<lightweight::SharedSource>();shared->Install(sourcePort,children);}
  else {v2=CreateObject<retransmission::SharedSource>();shared=v2;v2->Install(sourcePort,children);v2->nativeObserver=[this](Ptr<Packet> p){Evidence(0,0,"first_native",p);};v2->retryObserver=[this](uint32_t r,Ptr<Packet> p){Evidence(0,0,"native_retry",p);Event("native_retry",1001,r,Decode(p).psn,p->GetSize());};nodes[5]->GetObject<UbSwitch>()->SetWriteV2MetadataResolver(0,Callback<void,uint32_t,uint32_t,uint32_t,Ptr<Packet>>([this](uint32_t o,uint32_t seq,uint32_t m,Ptr<Packet> p){v2->Restore(o,seq,m,p);}));}
  sourcePort->SetReceiveHandler(MakeCallback(&Multi::SourceReceive,this));
  if(fault=="payload") DynamicCast<UbPort>(nodes[5]->GetDevice(0))->SetReceiveHandler(
    Callback<void,Ptr<UbPort>,Ptr<Packet>>([this](Ptr<UbPort> port,Ptr<Packet> p){
      if(!injected && UbWriteV2::IsEnvelope(p)){std::vector<uint8_t>b(p->GetSize());p->CopyData(b.data(),b.size());b.back()^=1;p=Create<Packet>(b.data(),b.size());injected=true;}
      nodes[5]->GetObject<UbSwitch>()->SwitchHandlePacket(port,p);
    }));
  if(scenario=="competition"||pressure){Pair(4,1,901,902,bgTx,bgRx);auto fn=C(4)->GetUbFunction();fn->CreateJetty(4,1,99);NS_ABORT_MSG_IF(!C(4)->GetUbTransaction()->JettyBindTp(4,1,99,false,{901}),"bg bind");bgJetty=fn->GetJetty(99);bgJetty->SetTaSegmentBytes(1024);bgJetty->SetClientCallback(Callback<void,uint32_t,uint32_t>([this](uint32_t,uint32_t){NS_ABORT_MSG_IF(bgCovered!=4*bytes||bgDone,"background early/duplicate complete");bgDone=true;Event("background_complete",9001);}));bgTx->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this](uint32_t,uint32_t,uint32_t ssn){bgOffsets[ssn]=bgNext;bgNext+=std::min(1024u,4*bytes-bgNext);}));}
  for(uint32_t n=0;n<6;++n)for(uint32_t p=0;p<nodes[n]->GetNDevices();++p){auto port=DynamicCast<UbPort>(nodes[n]->GetDevice(p));port->TraceConnectWithoutContext("TraComEventNotify",Callback<void,Ptr<Packet>,Time>([this,n,p](Ptr<Packet> packet,Time){PacketLog(n,p,"tx",packet);}));port->TraceConnectWithoutContext("PktRcvNotify",Callback<void,Ptr<Packet>>([this,n,p](Ptr<Packet> packet){PacketLog(n,p,"rx",packet);}));port->GetUbQueue()->TraceConnectWithoutContext("UbEnqueue",Callback<void,Ptr<const Packet>,uint32_t>([this,n,p](Ptr<const Packet> packet,uint32_t used){Evidence(n,p,"egress_enqueue",packet->Copy());ps[{n,p}].peak=std::max(ps[{n,p}].peak,uint64_t(used));}));}
 }
 void Run(){std::filesystem::create_directories(out);packets.open(out+"/packets.csv");packets<<"time_ps,event,node,port,uid,wire_bytes,envelope,src_tpn,dst_tpn,psn,ssn,tp_opcode,ta_opcode,task,payload_bytes,payload_hash\n";events.open(out+"/events.csv");wire.open(out+"/wire.csv");windows.open(out+"/windows.csv");windows<<"time_ps,event,rank,tp_una,tp_nxt,tp_outstanding,ta_una,ta_nxt,request_descriptors,request_timer,response_descriptors,response_timer,pending_selective\n";events<<"time_ps,event,task,rank,offset,bytes\n";wire<<"time_ps,event,node,port,bytes,type,tp_opcode,ta_opcode,task,packet_class\n";Init();members[1001]=scenario=="dynamic"?std::vector<uint32_t>{1,2}:std::vector<uint32_t>{1,2,3};if(scenario=="dynamic")members[1002]={2,3};
  for(auto&[task,ranks]:members){source[task].resize(bytes);for(uint32_t i=0;i<bytes;++i)source[task][i]=uint8_t((task*73+i*131+(i>>8)*17)%251);for(auto rank:ranks)got[{task,rank}].resize(bytes);}
  Simulator::Schedule(NanoSeconds(100),[this]{Submit(1001);if(bgJetty){std::vector<uint8_t>b(4*bytes);for(uint32_t i=0;i<b.size();++i)b[i]=uint8_t(i*17);auto w=C(4)->GetUbFunction()->CreateWqe(4,1,b.size(),9001,UbTransactionOpcode::WRITE);w->SetExplicitPayload(Create<Packet>(b.data(),b.size()));NS_ABORT_MSG_IF(C(4)->GetUbFunction()->SubmitWqe(w,99).status!=UbWqeSubmissionStatus::ACCEPTED,"background submit");}});
  Simulator::Schedule(MicroSeconds(14),[this]{Windows("bounded_snapshot");});
  Simulator::Stop(MicroSeconds(loss=="persistent-bounded"||loss=="retrans-disabled"?14:100));Simulator::Run();
  bool incomplete=loss=="persistent-bounded"||loss=="retrans-disabled";
  NS_ABORT_MSG_IF(incomplete ? (!groupsDone.empty() || senderDone.size()!=2 || !senderDone.count({1001,2}) || !senderDone.count({1001,3})) : groupsDone.size()!=members.size(),"completion semantics");NS_ABORT_MSG_IF(bgJetty&&(!bgDone||!bgJetty->IsIdle()||!bgTx->IsSafeForExplicitDestroy()||!bgRx->IsSafeForExplicitDestroy()),"background incomplete/not drained");
  std::ofstream payloads(out+"/payloads.csv");payloads<<"task,rank,bytes\n";for(auto&[key,b]:got){NS_ABORT_MSG_IF((!incomplete||key.second!=1)&&b!=source.at(key.first),"final payload mismatch");std::ofstream f(out+"/payload-"+std::to_string(key.first)+"-"+std::to_string(key.second)+".bin",std::ios::binary);f.write((char*)b.data(),b.size());payloads<<key.first<<','<<key.second<<','<<b.size()<<'\n';}
  std::ofstream ports(out+"/ports.csv");ports<<"node,port,peak,consumed,returned,restored,free,pending,blocked\n";uint64_t blocked=0;for(uint32_t n=0;n<6;++n)for(uint32_t p=0;p<nodes[n]->GetNDevices();++p){auto port=DynamicCast<UbPort>(nodes[n]->GetDevice(p));auto fc=DynamicCast<UbCbfc>(port->GetFlowControl());auto s=ps[{n,p}];auto initial=pressure?10:6553;NS_ABORT_MSG_IF(fc->GetConsumedCells()!=s.consumed||fc->GetReturnedCells()!=s.returned||int64_t(initial)-int64_t(fc->GetConsumedCells())+int64_t(fc->GetRestoredCells())!=fc->GetTxFreeCells(7),"credit conservation");NS_ABORT_MSG_IF(s.peak>(pressure?1600:524288)||port->GetUbQueue()->GetCurrentBytes(),"egress overflow/leak");blocked+=fc->GetBlockedQueryCount();ports<<n<<','<<p<<','<<s.peak<<','<<fc->GetConsumedCells()<<','<<fc->GetReturnedCells()<<','<<fc->GetRestoredCells()<<','<<fc->GetTxFreeCells(7)<<','<<fc->GetCrdToReturn(7)<<','<<fc->GetBlockedQueryCount()<<'\n';}
  NS_ABORT_MSG_IF(pressure&&!blocked,"CBFC pressure not exercised");NS_ABORT_MSG_IF(ingressPeak>(pressure?1600:1048576),"ingress overflow");auto sw=nodes[5]->GetObject<UbSwitch>();auto s=sw->GetNetworkReplicationStats();NS_ABORT_MSG_IF(s.admitted!=s.released||s.branches!=s.branchDequeues||s.parentBytes||s.branchBytes||s.descriptors||sw->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes,"replication leak");for(auto&[rank,tp]:sendTp){
   if(incomplete&&rank==1){NS_ABORT_MSG_IF(tp->GetOutstandingUnackedSegmentCount()!=1||jetties[rank]->IsIdle(),"missing bounded retained native work");}
   else NS_ABORT_MSG_IF(!tp->IsSafeForExplicitDestroy()||!recvTp[rank]->IsSafeForExplicitDestroy()||!jetties[rank]->IsIdle()||tp->GetGbnDescriptorCountForTest()||recvTp[rank]->GetGbnDescriptorCountForTest()||tp->IsRetransTimerRunningForTest()||recvTp[rank]->IsRetransTimerRunningForTest(),"native child not drained");
  }
  if(v2){v2->CheckDrained();}
  std::ofstream summary(out+"/summary.json");summary<<"{\"status\":\""<<(incomplete?"BOUNDED_INCOMPLETE":"PASS")<<"\",\"drops\":"<<drops<<",\"duplicates\":"<<repeats<<",\"unicast_retries\":"<<v2->unicastRetries<<",\"groups\":"<<groupsDone.size()<<",\"source_payload_bytes\":"<<shared->payloadSent<<",\"source_data_wire_bytes\":"<<shared->wireDataBytes<<",\"envelopes\":"<<shared->envelopes<<",\"branches\":"<<s.branches<<",\"input_release_bytes\":"<<s.upstreamReturnBytes<<",\"association_peak\":"<<(v2?v2->peakRecords:0)<<",\"association_restored\":"<<(v2?v2->restored:0)<<",\"window_barrier_checks\":"<<shared->barrierChecks<<",\"empty_waits\":"<<shared->emptyWaits<<",\"window_waits\":"<<shared->windowWaits<<",\"blocked_queries\":"<<blocked<<"}\n";Windows("final_state");events.close();wire.close();windows.close();Simulator::Destroy();std::cout<<(incomplete?"BOUNDED_INCOMPLETE":"PASS")<<" multi\n";
 }
};
int main(int argc,char**argv){Time::SetResolution(Time::PS);Multi t;t.bytes=12288;CommandLine c;c.AddValue("out","Private output",t.out);c.AddValue("loss","bounded fault case",t.loss);c.AddValue("window","native window",t.window);c.Parse(argc,argv);std::set<std::string> cases={"normal","data-once","duplicate","ack-once","response-once","persistent-bounded","persistent-exhaust","retrans-disabled"};NS_ABORT_MSG_IF(t.out.empty()||!cases.count(t.loss),"configuration");t.enabled=t.loss!="retrans-disabled";t.Run();}
