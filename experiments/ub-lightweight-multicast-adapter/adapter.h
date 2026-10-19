// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "ns3/unified-bus-module.h"
#include <map>
#include <set>
#include <vector>
#include <algorithm>
namespace lightweight {
using namespace ns3;
// Versioned experimental envelope, not a standardized UB header. All bytes below are on wire.
inline void Put(std::vector<uint8_t>& b,uint32_t x){for(int i=3;i>=0;--i)b.push_back(uint8_t(x>>(i*8)));}
inline uint32_t Take(const std::vector<uint8_t>& b,size_t& at){NS_ABORT_MSG_IF(at+4>b.size(),"truncated envelope");uint32_t x=0;for(int i=0;i<4;++i)x=(x<<8)|b[at++];return x;}
template<class T> void PutTag(std::vector<uint8_t>& b,Ptr<Packet> p){T tag;NS_ABORT_MSG_IF(!p->PeekPacketTag(tag),"missing native tag");size_t at=b.size();b.resize(at+tag.GetSerializedSize());tag.Serialize(TagBuffer(b.data()+at,b.data()+b.size()));}
template<class T> void TakeTag(const std::vector<uint8_t>& b,size_t& at,Ptr<Packet> p){T tag;auto n=tag.GetSerializedSize();NS_ABORT_MSG_IF(at+n>b.size(),"truncated native tag");std::vector<uint8_t> raw(b.begin()+at,b.begin()+at+n);tag.Deserialize(TagBuffer(raw.data(),raw.data()+n));p->AddPacketTag(tag);at+=n;}
class SharedSource : public UbIngressQueue {
public:
 struct Child {uint32_t rank;Ptr<UbTransportChannel> tp;};
 std::vector<Child> all,active; std::set<uint32_t> memberDone;
 uint32_t group{0},sequence{0},totalBytes{0},sentBytes{0},segmentBytes{1024};
 uint64_t envelopes{0},payloadSent{0},wireDataBytes{0},barrierChecks{0},emptyWaits{0},windowWaits{0};
 Ptr<UbPort> port;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::LightweightSharedSource").SetParent<UbIngressQueue>().AddConstructor<SharedSource>();return t;}
 IngressQueueType GetIngressQueueType() override{return IngressQueueType::CTP;}
 void Install(Ptr<UbPort> p,const std::vector<Child>& c){port=p;all=c;SetInPortId(p->GetIfIndex());SetOutPortId(p->GetIfIndex());SetIngressPriority(7);auto alloc=p->GetNode()->GetObject<UbSwitch>()->GetAllocator();
  std::set<uint32_t> ranks;std::set<const UbTransportChannel*> pointers;BooleanValue cc;GlobalValue::GetValueByName("UB_CC_ENABLED",cc);NS_ABORT_MSG_IF(cc.Get(),"adapter excludes congestion control");for(auto& x:all){NS_ABORT_MSG_IF(!x.tp||x.rank>=64||!ranks.insert(x.rank).second||!pointers.insert(PeekPointer(x.tp)).second||x.tp->GetSrc()!=p->GetNode()->GetId()||x.tp->GetDest()!=x.rank||x.tp->GetOutPortId()!=p->GetIfIndex()||x.tp->GetIngressPriority()!=7,"invalid/duplicate native child binding");NS_ABORT_MSG_IF(!x.tp->IsSafeForExplicitDestroy(),"install requires quiescent TP");BooleanValue enabled;x.tp->GetAttribute("EnableRetrans",enabled);NS_ABORT_MSG_IF(enabled.Get(),"adapter excludes retransmission");alloc->UnregisterUbIngressQueue(x.tp,p->GetIfIndex(),7);}
  alloc->RegisterUbIngressQueue(this,p->GetIfIndex(),7);
 }
 void Select(uint32_t id,uint32_t bytes,const std::vector<uint32_t>& ranks){NS_ABORT_MSG_IF(sentBytes!=totalBytes||(totalBytes&&memberDone.size()!=active.size()),"replace active group before native member completion");memberDone.clear();group=id;totalBytes=bytes;sentBytes=sequence=0;active.clear();std::set<uint32_t> unique;for(auto r:ranks){NS_ABORT_MSG_IF(r>=64||!unique.insert(r).second,"duplicate/out-of-range group member");auto it=std::find_if(all.begin(),all.end(),[&](const Child& c){return c.rank==r;});NS_ABORT_MSG_IF(it==all.end(),"unprovisioned group member");active.push_back(*it);}NS_ABORT_MSG_IF(active.empty(),"empty group");}
 bool MemberComplete(uint32_t rank,uint32_t task){NS_ABORT_MSG_IF(task!=group||!totalBytes||sentBytes!=totalBytes||std::none_of(active.begin(),active.end(),[&](const Child& c){return c.rank==rank;})||!memberDone.insert(rank).second,"invalid/duplicate/early member completion");return memberDone.size()==active.size();}
 void Refresh(){RefreshAllocatorSummary();}
 Ptr<UbTransportChannel> Control(){for(auto& c:all)if(!c.tp->m_cnpQ.empty())return c.tp;for(auto& c:all)if(!c.tp->m_ackQ.empty())return c.tp;return nullptr;}
 bool IsEmpty() override{for(auto& c:all)if(!c.tp->IsEmpty())return false;return true;}
 bool IsLimited() override{if(Control())return false;if(active.empty())return true;for(auto& c:active){if(c.tp->IsEmpty()){++barrierChecks;++emptyWaits;return true;}if(c.tp->IsLimited()){++barrierChecks;++windowWaits;return true;}}return false;}
 uint32_t GetNextPacketSize() override{if(auto t=Control())return t->GetNextPacketSize();if(active.size()==1)return active.front().tp->GetNextPacketSize();if(active.empty()||sentBytes>=totalBytes)return 0;
  uint32_t len=std::min(segmentBytes,totalBytes-sentBytes);
  // 4B outer DL, 28B envelope, per member rank+prefix length (8), native prefix (78), tags (8+42+1).
  return 4+28+active.size()*(8+78+8+42+1)+len;
 }
 Ptr<Packet> GetNextPacket() override{
  if(auto t=Control()){auto p=t->GetNextPacket();Refresh();return p;}
  NS_ABORT_MSG_IF(IsLimited(),"coalescer dequeue before all native children eligible");
  if(active.size()==1){auto p=active.front().tp->GetNextPacket();NS_ABORT_MSG_IF(!p,"empty singleton dequeue");UbNetworkReplicationTag tag;tag.destinations=uint64_t{1}<<active.front().rank;tag.nativeSingleton=true;tag.object=group;p->AddPacketTag(tag);if(totalBytes){NS_ABORT_MSG_IF(p->GetSize()<78,"singleton WRITE size");auto len=p->GetSize()-78;sentBytes+=len;payloadSent+=len;wireDataBytes+=p->GetSize();}Refresh();return p;}
  const uint32_t expectedSize=GetNextPacketSize(),len=std::min(segmentBytes,totalBytes-sentBytes);
  for(auto& c:active)NS_ABORT_MSG_IF(c.tp->GetNextPacketSize()!=78+len,"unmatched next native packet size");
  uint64_t mask=0;for(auto& c:active)mask|=uint64_t{1}<<c.rank;
  std::vector<uint8_t> b;Put(b,0x55424d31);Put(b,group);Put(b,sequence);Put(b,len);Put(b,active.size());Put(b,uint32_t(mask>>32));Put(b,uint32_t(mask));
  std::vector<uint8_t> shared;
  for(auto& c:active){auto packet=c.tp->GetNextPacket();NS_ABORT_MSG_IF(!packet,"native child dequeue failed");UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!c.tp->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"native child decode failed");
   NS_ABORT_MSG_IF(ctx.flowTag.GetFlowId()!=group||ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE)||ctx.payloadBytes!=len,"native child range/type differs");
   std::vector<uint8_t> raw(packet->GetSize());packet->CopyData(raw.data(),raw.size());std::vector<uint8_t> payload(raw.end()-len,raw.end());if(shared.empty())shared=payload;else NS_ABORT_MSG_IF(shared!=payload,"native child payload differs");
   Put(b,c.rank);Put(b,raw.size()-len);b.insert(b.end(),raw.begin(),raw.end()-len);PutTag<UbFlowTag>(b,packet);PutTag<UbTransactionCorrelationTag>(b,packet);PutTag<UbExplicitPayloadTag>(b,packet);
  }
  b.insert(b.end(),shared.begin(),shared.end());auto packet=Create<Packet>(b.data(),b.size());UbDatalinkPacketHeader dl;dl.SetPacketVL(7);packet->AddHeader(dl);UbNetworkReplicationTag tag;tag.destinations=mask;tag.object=group;tag.sequence=sequence++;tag.nativeEnvelope=true;packet->AddPacketTag(tag);
  NS_ABORT_MSG_IF(packet->GetSize()!=expectedSize,"predicted envelope size differs");sentBytes+=len;++envelopes;payloadSent+=len;wireDataBytes+=packet->GetSize();Refresh();return packet;
 }
};
// Decode actual received bytes, not a shared-memory side channel. Native TP remains authoritative.
inline Ptr<Packet> Reconstruct(uint32_t rank,uint32_t group,uint32_t sequence,Ptr<Packet> payload){std::vector<uint8_t> b(payload->GetSize());payload->CopyData(b.data(),b.size());size_t at=0;NS_ABORT_MSG_IF(Take(b,at)!=0x55424d31||Take(b,at)!=group||Take(b,at)!=sequence,"envelope identity");uint32_t len=Take(b,at),count=Take(b,at);uint64_t mask=uint64_t(Take(b,at))<<32;mask|=Take(b,at);NS_ABORT_MSG_IF(!count||count>64||rank>=64||!(mask&(uint64_t{1}<<rank)),"envelope membership");
 Ptr<Packet> selected;uint64_t seen=0;
 for(uint32_t i=0;i<count;++i){uint32_t r=Take(b,at),prefix=Take(b,at);NS_ABORT_MSG_IF(r>=64||!(mask&(uint64_t{1}<<r))||(seen&(uint64_t{1}<<r))||prefix!=78||at+prefix>b.size(),"envelope header record");seen|=uint64_t{1}<<r;auto p=Create<Packet>(b.data()+at,prefix);at+=prefix;TakeTag<UbFlowTag>(b,at,p);TakeTag<UbTransactionCorrelationTag>(b,at,p);TakeTag<UbExplicitPayloadTag>(b,at,p);if(r==rank)selected=p;}
 NS_ABORT_MSG_IF(seen!=mask||!selected||at+len!=b.size(),"envelope payload length/members");selected->AddAtEnd(Create<Packet>(b.data()+at,len));return selected;
}
}
