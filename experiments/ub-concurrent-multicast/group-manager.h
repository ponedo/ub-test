// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "../ub-lightweight-multicast-adapter/adapter.h"
#include <functional>
namespace lightweight {
// Bounded operation registry. Arbitration is exclusively the native source allocator.
// Caller provisions disjoint native children; each native WQE keeps its own task ID.
class GroupManager {
public:
 struct Member {uint32_t rank,task; ns3::Ptr<ns3::UbTransportChannel> tx,rx;};
 struct Group {uint32_t id,source,bytes;std::vector<Member> members;ns3::Ptr<SharedSource> queue;bool started=false,complete=false;std::map<uint32_t,uint32_t> nextSequence;};
 std::map<uint32_t,Group> groups;
 std::map<uint32_t,std::pair<uint32_t,uint32_t>> tasks;
 std::set<const ns3::UbTransportChannel*> owned,receivers;
 std::function<void(uint32_t)> onComplete;
 uint32_t limit=128;
 HeaderMode headerMode{HeaderMode::FULL};
 std::map<uint32_t,uint64_t> senderTimes;
 std::set<std::tuple<uint32_t,uint32_t,uint32_t>> seenFeedback;
 uint64_t responses=0;
 std::map<std::pair<uint32_t,uint32_t>,uint32_t> responseEndpoints;
 void Add(uint32_t id,uint32_t source,uint32_t bytes,uint32_t segment,ns3::Ptr<ns3::UbPort> port,const std::vector<Member>& members){
  NS_ABORT_MSG_IF(!limit||limit>128||groups.size()>=limit||groups.count(id)||!bytes||!segment||segment>4096||source>=64||port->GetNode()->GetId()!=source||members.empty()||members.size()>63,"multicast group capacity/configuration");
  std::vector<SharedSource::Child> children;std::vector<uint32_t> ranks;std::map<uint32_t,uint32_t> identities;
  for(auto& m:members){NS_ABORT_MSG_IF(m.rank==source||m.rank>=64||!m.tx||!m.rx||m.rx->GetSrc()!=m.rank||m.rx->GetDest()!=source||m.tx->GetDestTpn()!=m.rx->GetTpn()||m.rx->GetDestTpn()!=m.tx->GetTpn()||!receivers.insert(ns3::PeekPointer(m.rx)).second||!owned.insert(ns3::PeekPointer(m.tx)).second||!tasks.emplace(m.task,std::make_pair(id,m.rank)).second||!identities.emplace(m.rank,m.task).second,"multicast child ownership");NS_ABORT_MSG_IF(!responseEndpoints.emplace(std::make_pair(source,m.tx->GetTpn()),m.task).second,"duplicate response endpoint");children.push_back({m.rank,m.tx});ranks.push_back(m.rank);}
  auto q=ns3::CreateObject<SharedSource>();q->headerMode=headerMode;q->segmentBytes=segment;q->Install(port,children);q->Select(id,bytes,ranks);q->SetMemberTasks(identities);
  groups.emplace(id,Group{id,source,bytes,members,q});
 }
 void Start(uint32_t id){auto& g=groups.at(id);NS_ABORT_MSG_IF(g.started,"duplicate group start");g.started=true;}
 void Refresh(uint32_t source){for(auto&[id,g]:groups)if(g.source==source)g.queue->Refresh();}
 void Completed(uint32_t task){NS_ABORT_MSG_IF(!senderTimes.emplace(task,ns3::Simulator::Now().GetPicoSeconds()).second,"duplicate child sender notification");auto [id,rank]=tasks.at(task);auto& g=groups.at(id);NS_ABORT_MSG_IF(!g.started||g.complete,"group completion state");if(g.queue->MemberComplete(rank,task)){g.complete=true;if(onComplete)onComplete(id);}}
 void Receive(uint32_t rank,uint32_t id,uint32_t seq,ns3::Ptr<ns3::Packet> payload){
  NS_ABORT_MSG_IF(!groups.count(id),"unknown group envelope");auto& g=groups.at(id);auto it=std::find_if(g.members.begin(),g.members.end(),[&](auto& m){return m.rank==rank;});
  NS_ABORT_MSG_IF(!g.started||g.complete||it==g.members.end()||seq!=g.nextSequence[rank]++,"wrong/duplicate group envelope");auto packet=g.queue->ReconstructReceived(rank,id,seq,payload);ns3::UbTransportChannel::ReceivedDataPacketContext ctx;
  NS_ABORT_MSG_IF(!it->rx->ParseReceivedDataPacketForTest(packet->Copy(),ctx)||ctx.flowTag.GetFlowId()!=it->task,"group child packet identity");
  auto receiver=ns3::NodeList::GetNode(rank)->GetObject<ns3::UbController>();auto endpoint=receiver->GetTransportChannelManager()->ResolveInboundTp(ctx.transportHeader.GetSrcTpn(),ctx.transportHeader.GetDestTpn(),ctx.ipv4Header.GetSource(),ctx.ipv4Header.GetDestination(),ctx.dataLinkHeader.GetPacketVL());
  NS_ABORT_MSG_IF(endpoint.state!=ns3::UbInboundTpState::LIVE||endpoint.endpoint!=it->rx,"group endpoint mismatch");it->rx->RecvDataPacket(packet);
 }
 // Inspect native transaction feedback, then invoke the unchanged receive handler.
 void ReceiveNative(uint32_t node,ns3::Ptr<ns3::UbPort> port,ns3::Ptr<ns3::Packet> packet){auto sw=port->GetNode()->GetObject<ns3::UbSwitch>();
  if(!groups.empty()&&sw->GetPacketTypeForTest(packet)==ns3::UB_URMA_DATA_PACKET){auto copy=packet->Copy();ns3::UbDatalinkPacketHeader dl;ns3::UbIpBasedNetworkHeader net;ns3::Ipv4Header ip;ns3::UdpHeader udp;ns3::UbTransportHeader h;copy->RemoveHeader(dl);copy->RemoveHeader(net);copy->RemoveHeader(ip);copy->RemoveHeader(udp);copy->RemoveHeader(h);
   if(!ns3::UbTransportChannel::IsTransportResponseOpcode(h.GetTPOpcode())){ns3::UbTransportChannel::ReceivedDataPacketContext ctx;auto parser=groups.begin()->second.members.front().tx;NS_ABORT_MSG_IF(!parser->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"native feedback decode");auto task=ctx.flowTag.GetFlowId();auto binding=responseEndpoints.find({node,h.GetDestTpn()});if(ctx.transactionHeader.GetUbTransactionOpcode()==uint8_t(ns3::UbTransactionOpcode::TAACK)&&(binding!=responseEndpoints.end()||tasks.count(task))){NS_ABORT_MSG_IF(binding==responseEndpoints.end()||binding->second!=task,"multicast feedback task/endpoint mismatch");auto[id,rank]=tasks.at(task);auto& g=groups.at(id);auto it=std::find_if(g.members.begin(),g.members.end(),[&](auto& m){return m.task==task;});NS_ABORT_MSG_IF(!g.started||it==g.members.end()||node!=g.source||h.GetSrcTpn()!=it->rx->GetTpn()||h.GetDestTpn()!=it->tx->GetTpn(),"multicast feedback endpoint");NS_ABORT_MSG_IF(!seenFeedback.emplace(node,h.GetSrcTpn(),h.GetPsn()).second,"duplicate multicast feedback");++responses;}}
  }sw->SwitchHandlePacket(port,packet);Refresh(node);
 }
 // Conservative admission check for this fixed 160-byte CBFC-cell single-switch model.
 void CheckCapacity(const std::vector<ns3::Ptr<ns3::Node>>& nodes){for(auto&[id,g]:groups){uint32_t frame=ChargedHeaderBytes(g.queue->headerMode,g.members.size())+std::min(g.bytes,g.queue->segmentBytes);for(auto node:nodes){auto sw=node->GetObject<ns3::UbSwitch>();NS_ABORT_MSG_IF(frame>sw->GetQueueManager()->GetReservePerQueueBytes(),"group frame exceeds ingress capacity");for(uint32_t i=0;i<node->GetNDevices();++i){auto port=ns3::DynamicCast<ns3::UbPort>(node->GetDevice(i));ns3::UintegerValue cap;port->GetUbQueue()->GetAttribute("MaxEgressBytes",cap);auto fc=ns3::DynamicCast<ns3::UbCbfc>(port->GetFlowControl());NS_ABORT_MSG_IF(frame>cap.Get()||!fc||int64_t((frame+159)/160)>fc->GetTxFreeCells(7),"group frame exceeds egress/initial credit capacity");}}}}
 void CheckDrained(){for(auto&[id,g]:groups){NS_ABORT_MSG_IF(!g.started||!g.complete||g.queue->sentBytes!=g.bytes,"unfinished multicast group");g.queue->CheckOracleDrained();for(auto& m:g.members)NS_ABORT_MSG_IF(!m.tx->IsSafeForExplicitDestroy()||!m.rx->IsSafeForExplicitDestroy(),"multicast child state not drained");}}
};
}
