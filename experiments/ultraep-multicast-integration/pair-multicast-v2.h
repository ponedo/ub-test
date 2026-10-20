// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "../ub-multicast-v2/adapter-v2.h"
namespace pairv2 {
using namespace ns3;
class Manager;
class Proxy : public UbIngressQueue {
public:
 Manager* manager{}; uint32_t source{},target{}; Ptr<UbTransportChannel> tp;
 bool invalidateOnce{},invalidationScheduled{};Time blockedUntil=Seconds(0);uint64_t invalidatedGrants{};
 bool RevalidateOnCommit() const{return true;}
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::PairV2Proxy").SetParent<UbIngressQueue>().AddConstructor<Proxy>().AddAttribute("RevalidateOnCommit","Coordinated native heads can change during an allocation grant; reselect stale grants.",TypeId::ATTR_GET,BooleanValue(true),MakeBooleanAccessor(&Proxy::RevalidateOnCommit),MakeBooleanChecker());return t;}
 IngressQueueType GetIngressQueueType() override{return IngressQueueType::TP;}
 bool IsEmpty() override; bool IsLimited() override; uint32_t GetNextPacketSize() override;Ptr<Packet> GetNextPacket() override;
 void Refresh(){m_headArrivalTime=tp->GetHeadArrivalTime();RefreshAllocatorSummary();}
};
class Manager {
public:
 struct Member{uint32_t rank,task;Ptr<UbTransportChannel> tx,rx;};
 struct Group{uint32_t id,source,bytes,segment;std::vector<Member> members;Ptr<writev2::SharedSource> codec;bool started{},complete{},released{};uint64_t admittedPs{},releasedPs{};uint64_t grants{},retryPackets{};};
 std::map<uint32_t,Group> groups;
 std::map<uint32_t,std::pair<uint32_t,uint32_t>> tasks;
 std::map<std::pair<uint32_t,uint32_t>,Ptr<Proxy>> pairs;
 std::map<std::pair<uint32_t,uint32_t>,Ptr<Proxy>> localTp;
 std::map<std::pair<uint32_t,uint32_t>,std::vector<uint32_t>> pairGroups;
 std::map<uint32_t,uint64_t> senderTimes,completeTimes;
 std::function<uint64_t(uint32_t,uint32_t)> offset;
 std::function<void(uint32_t,uint32_t,Ptr<Packet>,bool)> observe;
 uint64_t retries{},singletonPackets{},totalAssociationLimit{};
 uint32_t limit=128;
 std::map<std::pair<uint32_t,uint32_t>,uint32_t> reservations;
 std::function<void(uint32_t)> submit;
 bool admissionScheduled{};
 static std::pair<uint32_t,uint32_t> Edge(uint32_t a,uint32_t b){return std::minmax(a,b);}
 void Admit(){admissionScheduled=false;for(auto&[id,g]:groups){if(g.started)continue;bool available=true;for(auto&m:g.members)if(reservations.count(Edge(g.source,m.rank)))available=false;if(!available)continue;
   for(auto&m:g.members)NS_ABORT_MSG_IF(!reservations.emplace(Edge(g.source,m.rank),id).second,"non-atomic group admission");
   g.started=true;g.admittedPs=Simulator::Now().GetPicoSeconds();for(auto&m:g.members)submit(m.task);
  }}
 void Release(Group& g){if(g.codec->sentBytes!=g.bytes)return;NS_ABORT_MSG_IF(!g.started||g.released,"duplicate first-send release");
  for(auto&m:g.members){auto key=Edge(g.source,m.rank);NS_ABORT_MSG_IF(!reservations.count(key)||reservations.at(key)!=g.id,"group reservation ownership");auto next=m.tx->PeekOriginalSegmentForAdapter();NS_ABORT_MSG_IF(next&&next->GetSegmentKind()==UbTransactionSegmentKind::REQUEST&&next->GetTaskId()==m.task,"release before native original drain");reservations.erase(key);}
  g.released=true;g.releasedPs=Simulator::Now().GetPicoSeconds();if(!admissionScheduled){admissionScheduled=true;Simulator::ScheduleNow([this]{Admit();});}
 }
 void Add(uint32_t id,uint32_t source,uint32_t bytes,uint32_t segment,Ptr<UbPort> port,const std::vector<Member>& members){
  NS_ABORT_MSG_IF(groups.size()>=limit||groups.count(id)||members.empty()||members.size()>63||source>=64||!segment||segment>4096,"pair v2 group capacity");
  auto q=CreateObject<writev2::SharedSource>();q->port=port;q->segmentBytes=segment;
  std::vector<uint32_t> ranks;std::map<uint32_t,uint32_t> identities;std::set<uint32_t> unique;
  for(auto& m:members){NS_ABORT_MSG_IF(m.rank==source||!unique.insert(m.rank).second||!m.tx||!m.rx||m.tx->GetSrc()!=source||m.tx->GetDest()!=m.rank||m.tx->GetDestTpn()!=m.rx->GetTpn()||m.rx->GetDestTpn()!=m.tx->GetTpn()||!tasks.emplace(m.task,std::make_pair(id,m.rank)).second,"pair group member binding");pairGroups[{source,m.rank}].push_back(id);q->all.push_back({m.rank,m.tx});ranks.push_back(m.rank);identities[m.rank]=m.task;UintegerValue w;m.tx->GetAttribute("DefaultMaxInflightPacketSize",w);NS_ABORT_MSG_IF(!w.Get(),"finite pair window required");q->capacity=std::max(q->capacity,w.Get());}
  // Codec helpers are NOT registered queues and do not own native TP dequeue.
  q->Select(id,bytes,ranks);q->SetMemberTasks(identities);totalAssociationLimit+=q->capacity;
  q->nativeObserver=[this,id,source](Ptr<Packet> p){if(observe)observe(id,source,p,false);};
  groups.emplace(id,Group{id,source,bytes,segment,members,q});
 }
 bool HasSource(uint32_t source)const{for(auto&[id,g]:groups)if(g.source==source)return true;return false;}
 void InstallSource(uint32_t source,Ptr<UbPort> port,const std::vector<Ptr<UbTransportChannel>>& channels,Ptr<UbSwitch> fabric){
  NS_ABORT_MSG_IF(!HasSource(source),"unneeded source wrapper");auto alloc=port->GetNode()->GetObject<UbSwitch>()->GetAllocator();NS_ABORT_MSG_IF(!DynamicCast<UbRoundRobinAllocator>(alloc),"pair v2 currently requires native RR allocator");
  uint32_t last=0;bool first=true;
  // Pair creation order is increasing target rank. Preserve one native RR slot
  // per pair, not one aggregated slot per source or one slot per expert.
  for(auto tp:channels){NS_ABORT_MSG_IF(!tp||tp->GetSrc()!=source||!tp->IsSafeForExplicitDestroy()||(!first&&tp->GetDest()<=last)|| (tp->GetRetransEnable()&&tp->GetRetransmissionMode()!=UbRetransmissionMode::GBN),"pair proxy install ordering/state");last=tp->GetDest();first=false;alloc->UnregisterUbIngressQueue(tp,port->GetIfIndex(),7);}
  for(auto tp:channels){auto q=CreateObject<Proxy>();q->manager=this;q->source=source;q->target=tp->GetDest();q->tp=tp;q->SetInPortId(port->GetIfIndex());q->SetOutPortId(port->GetIfIndex());q->SetIngressPriority(7);NS_ABORT_MSG_IF(!pairs.emplace(std::make_pair(source,q->target),q).second||!localTp.emplace(std::make_pair(source,tp->GetTpn()),q).second,"duplicate pair dequeue owner");alloc->RegisterUbIngressQueue(q,port->GetIfIndex(),7);}
  fabric->SetWriteV2MetadataResolver(source,Callback<void,uint32_t,uint32_t,uint32_t,Ptr<Packet>>([this,source](uint32_t id,uint32_t seq,uint32_t member,Ptr<Packet> p){auto& g=groups.at(id);NS_ABORT_MSG_IF(g.source!=source||!g.started,"v2 resolver source/operation");g.codec->Restore(id,seq,member,p);}));
 }
 static bool Priority(Ptr<UbTransportChannel> tp){return !tp->m_ackQ.empty()||!tp->m_cnpQ.empty()||(tp->GetRetransEnable()&&tp->HasPendingGbnRetransmissionForTest());}
 Group* OriginalGroup(Ptr<UbTransportChannel> tp){if(Priority(tp))return nullptr;auto s=tp->PeekOriginalSegmentForAdapter();if(!s||s->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST)return nullptr;auto i=tasks.find(s->GetTaskId());return i==tasks.end()?nullptr:&groups.at(i->second.first);}
 bool PendingGroup(uint32_t source,uint32_t target)const{auto it=pairGroups.find({source,target});if(it==pairGroups.end())return false;for(auto id:it->second){const auto& g=groups.at(id);if(g.codec->sentBytes<g.bytes)return true;}return false;}
 bool AllReady(Group& g){if(!g.started||g.codec->sentBytes>=g.bytes)return false;for(auto&m:g.members){if(Priority(m.tx)||m.tx->IsEmpty()||m.tx->IsLimited())return false;auto s=m.tx->PeekOriginalSegmentForAdapter();if(!s||s->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST||s->GetTaskId()!=m.task)return false;NS_ABORT_MSG_IF(!offset||offset(m.task,s->GetTaSsn())!=g.codec->sentBytes||s->GetBytesLeft()!=s->GetCarrierBytes(),"unaligned original weight head");}return true;}
 bool Limited(Proxy& p){if(p.tp->IsEmpty())return true;if(Priority(p.tp))return p.tp->IsLimited();auto g=OriginalGroup(p.tp);if(!g||g->members.size()==1)return p.tp->IsLimited();if(p.target!=g->members.front().rank)return true;return !AllReady(*g);}
 uint32_t Size(Proxy& p){if(!Priority(p.tp)){auto g=OriginalGroup(p.tp);if(g&&g->members.size()>1&&p.target==g->members.front().rank)return g->codec->GetNextPacketSize();}return p.tp->GetNextPacketSize();}
 Ptr<Packet> Pull(Proxy& p){NS_ABORT_MSG_IF(Limited(p),"dequeue ineligible pair");
  bool retry=p.tp->GetRetransEnable()&&p.tp->HasPendingGbnRetransmissionForTest()&&p.tp->m_ackQ.empty()&&p.tp->m_cnpQ.empty();auto g=Priority(p.tp)?nullptr:OriginalGroup(p.tp);
  if(g&&g->members.size()>1){NS_ABORT_MSG_IF(!AllReady(*g),"group heads changed");auto packet=g->codec->GetNextPacket();++g->grants;Release(*g);for(auto&m:g->members)Refresh(p.source,m.rank);return packet;}
  auto packet=p.tp->GetNextPacket();NS_ABORT_MSG_IF(!packet||UbWriteV2::IsEnvelope(packet),"ordinary/native retry path");
  if(retry){++retries;if(observe)observe(0,p.source,packet,true);}
  if(g){NS_ABORT_MSG_IF(g->members.size()!=1||!g->started,"singleton state");UbTransportChannel::ReceivedDataPacketContext c;NS_ABORT_MSG_IF(!p.tp->ParseReceivedDataPacketForTest(packet->Copy(),c)||c.flowTag.GetFlowId()!=g->members.front().task||c.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE)||c.payloadBytes!=std::min(g->segment,g->bytes-g->codec->sentBytes),"singleton native identity");g->codec->sentBytes+=c.payloadBytes;g->codec->payloadSent+=c.payloadBytes;g->codec->wireDataBytes+=packet->GetSize();g->codec->chargedHeaderBytes+=packet->GetSize()-c.payloadBytes;++g->codec->sequence;++g->grants;++singletonPackets;if(observe)observe(g->id,p.source,packet,false);Release(*g);}
  p.Refresh();return packet;
 }
 void Refresh(uint32_t source,uint32_t target){auto it=pairs.find({source,target});if(it!=pairs.end())it->second->Refresh();}
 void Receive(uint32_t node,Ptr<UbPort> port,Ptr<Packet> packet){Ptr<Proxy> proxy;UbDatalinkHeader common;packet->PeekHeader(common);if(common.GetConfig()==3){auto q=packet->Copy();UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader tp;q->RemoveHeader(dl);q->RemoveHeader(net);q->RemoveHeader(ip);q->RemoveHeader(udp);q->RemoveHeader(tp);auto it=localTp.find({node,tp.GetDestTpn()});if(it!=localTp.end())proxy=it->second;}port->GetNode()->GetObject<UbSwitch>()->SwitchHandlePacket(port,packet);if(proxy)proxy->Refresh();}
 void Start(){NS_ABORT_MSG_IF(!submit,"missing native admission callback");for(auto&[id,g]:groups)NS_ABORT_MSG_IF(g.started,"duplicate group start");Admit();}
 void Completed(uint32_t task){auto[id,rank]=tasks.at(task);auto& g=groups.at(id);NS_ABORT_MSG_IF(!g.started||g.complete||!senderTimes.emplace(task,Simulator::Now().GetPicoSeconds()).second,"duplicate/early group feedback");if(g.codec->MemberComplete(rank,task)){g.complete=true;completeTimes[id]=Simulator::Now().GetPicoSeconds();}}
 void CheckCapacity(const std::vector<Ptr<Node>>& nodes){for(auto&[id,g]:groups){auto frame=g.members.size()==1?78+std::min(g.bytes,g.segment):24+76*g.members.size()+std::min(g.bytes,g.segment);for(auto node:nodes){auto sw=node->GetObject<UbSwitch>();NS_ABORT_MSG_IF(frame>sw->GetQueueManager()->GetReservePerQueueBytes(),"v2 ingress capacity");for(uint32_t i=0;i<node->GetNDevices();++i){auto port=DynamicCast<UbPort>(node->GetDevice(i));UintegerValue cap;port->GetUbQueue()->GetAttribute("MaxEgressBytes",cap);auto fc=DynamicCast<UbCbfc>(port->GetFlowControl());NS_ABORT_MSG_IF(!fc||frame>cap.Get()||int64_t((frame+159)/160)>fc->GetTxFreeCells(7),"v2 egress/credit capacity");}}}}
 void CheckDrained(){NS_ABORT_MSG_IF(!reservations.empty()||admissionScheduled,"first-send admission not drained");for(auto&[id,g]:groups){NS_ABORT_MSG_IF(!g.started||!g.released||!g.complete||g.codec->sentBytes!=g.bytes,"unfinished v2 weight operation");g.codec->CheckDrained();}for(auto&[key,p]:pairs)NS_ABORT_MSG_IF(!p->tp->IsSafeForExplicitDestroy(),"pair TP not safely quiescent");}
};
inline bool Proxy::IsEmpty(){return tp->IsEmpty()&&!tp->GetOutstandingUnackedSegmentCount()&&!manager->PendingGroup(source,target);}
inline bool Proxy::IsLimited(){
 if(Simulator::Now()<blockedUntil)return true;
 const bool limited=manager->Limited(*this);
 if(!limited&&invalidateOnce&&!invalidationScheduled){invalidationScheduled=true;Ptr<Proxy> self=this;
  Simulator::Schedule(NanoSeconds(1),[self]{++self->invalidatedGrants;self->blockedUntil=Simulator::Now()+NanoSeconds(9);Simulator::Schedule(NanoSeconds(9),[self]{self->blockedUntil=Simulator::Now();self->Refresh();DynamicCast<UbPort>(NodeList::GetNode(self->source)->GetDevice(0))->TriggerTransmit();});});
 }
 return limited;
}
inline uint32_t Proxy::GetNextPacketSize(){return manager->Size(*this);}
inline Ptr<Packet> Proxy::GetNextPacket(){NS_ABORT_MSG_IF(Simulator::Now()<blockedUntil,"test stale grant committed while ineligible");return manager->Pull(*this);}
}
