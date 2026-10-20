// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "../ub-multicast-v2/adapter-v2.h"
namespace retransmission {
using namespace ns3;
class SharedSource : public writev2::SharedSource {
public:
 uint64_t unicastRetries{};
 std::function<void(uint32_t,Ptr<Packet>)> retryObserver;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::RetransWriteV2SharedSource").SetParent<writev2::SharedSource>().AddConstructor<SharedSource>();return t;}
 void Install(Ptr<UbPort> p,const std::vector<Child>& c){port=p;all=c;SetInPortId(p->GetIfIndex());SetOutPortId(p->GetIfIndex());SetIngressPriority(7);auto alloc=p->GetNode()->GetObject<UbSwitch>()->GetAllocator();
  std::set<uint32_t> ranks;std::set<const UbTransportChannel*> pointers;BooleanValue cc;GlobalValue::GetValueByName("UB_CC_ENABLED",cc);NS_ABORT_MSG_IF(cc.Get(),"adapter excludes congestion control");for(auto& x:all){NS_ABORT_MSG_IF(!x.tp||x.rank>=64||!ranks.insert(x.rank).second||!pointers.insert(PeekPointer(x.tp)).second||x.tp->GetSrc()!=p->GetNode()->GetId()||x.tp->GetDest()!=x.rank||x.tp->GetOutPortId()!=p->GetIfIndex()||x.tp->GetIngressPriority()!=7,"invalid/duplicate native child binding");NS_ABORT_MSG_IF(!x.tp->IsSafeForExplicitDestroy(),"install requires quiescent TP");NS_ABORT_MSG_IF(x.tp->GetRetransEnable() && x.tp->GetRetransmissionMode()!=UbRetransmissionMode::GBN,"bounded adapter validates GBN only");alloc->UnregisterUbIngressQueue(x.tp,p->GetIfIndex(),7);}
  if(headerMode!=lightweight::HeaderMode::FULL){(void)lightweight::HeaderModeName(headerMode);for(auto& x:all){UintegerValue window;x.tp->GetAttribute("DefaultMaxInflightPacketSize",window);NS_ABORT_MSG_IF(!window.Get(),"oracle requires finite positive native send window");oracleEnvelopeLimit=std::max(oracleEnvelopeLimit,window.Get());}}
  for(auto& x:all){UintegerValue w;x.tp->GetAttribute("DefaultMaxInflightPacketSize",w);NS_ABORT_MSG_IF(!w.Get(),"finite native window required");capacity=std::max(capacity,w.Get());}
  alloc->RegisterUbIngressQueue(this,p->GetIfIndex(),7);
 }
 Ptr<UbTransportChannel> Retry() {
  for(auto& c:all) if(c.tp->GetRetransEnable() && c.tp->HasPendingGbnRetransmissionForTest() && !c.tp->IsLimited()) return c.tp;
  return nullptr;
 }
 // A detached child's timeout refreshes its own unbound queue summary, then
 // triggers the native port. Keep this wrapper discoverable while native work
 // is retained. IsLimited still blocks dequeue until an actual native retry.
 // No new timer, ACK ledger, retry buffer, or success transition.
 bool IsEmpty() override {
  for(auto& c:all) if(!c.tp->IsEmpty() || c.tp->GetOutstandingUnackedSegmentCount()) return false;
  return true;
 }
 bool IsLimited() override {
  if(Control() || Retry()) return false;
  if(sentBytes>=totalBytes) return true;
  return lightweight::SharedSource::IsLimited();
 }
 uint32_t GetNextPacketSize() override {
  if(auto t=Control())return t->GetNextPacketSize();
  if(auto t=Retry())return t->GetNextPacketSize();
  return writev2::SharedSource::GetNextPacketSize();
 }
 Ptr<Packet> GetNextPacket() override {
  if(auto t=Control()){auto p=t->GetNextPacket();Refresh();return p;}
  if(auto t=Retry()){
   const auto before=t->GetPsnSndNxt();auto p=t->GetNextPacket();
   NS_ABORT_MSG_IF(!p || UbWriteV2::IsEnvelope(p) || t->GetPsnSndNxt()!=before,"native retry changed original-send state");
   ++unicastRetries;if(retryObserver)retryObserver(t->GetDest(),p);Refresh();return p;
  }
  return writev2::SharedSource::GetNextPacket();
 }
};
}
