// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "ns3/unified-bus-module.h"
#include <map>
#include <set>
#include <vector>
#include <algorithm>
#include <functional>
namespace lightweight {
using namespace ns3;
// FULL is the accepted byte-complete envelope. The two explicit ORACLE modes are
// header-cost sensitivity models, not decodable standalone multicast protocols.
enum class HeaderMode { FULL, COMPACT_ORACLE, IDEAL_ORACLE };
inline const char* HeaderModeName(HeaderMode mode){switch(mode){case HeaderMode::FULL:return "full";case HeaderMode::COMPACT_ORACLE:return "compact-oracle";case HeaderMode::IDEAL_ORACLE:return "ideal-oracle";}NS_ABORT_MSG("invalid multicast header mode");return "invalid";}
inline uint32_t ChargedHeaderBytes(HeaderMode mode,uint32_t fanout){
 NS_ABORT_MSG_IF(!fanout||fanout>64,"invalid multicast header fanout");
 (void)HeaderModeName(mode);if(fanout==1)return 78;
 return 32+(mode==HeaderMode::FULL?137*fanout:mode==HeaderMode::COMPACT_ORACLE?16*fanout:0);
}
inline uint32_t EnvelopeMagic(HeaderMode mode){switch(mode){case HeaderMode::FULL:return 0x55424d31;case HeaderMode::COMPACT_ORACLE:return 0x55424d32;case HeaderMode::IDEAL_ORACLE:return 0x55424d33;}NS_ABORT_MSG("invalid multicast envelope mode");return 0;}
// Versioned experimental envelope, not a standardized UB header. Put/Take bytes
// are on wire; ORACLE restoration records below are explicitly simulator-only.
inline void Put(std::vector<uint8_t>& b,uint32_t x){for(int i=3;i>=0;--i)b.push_back(uint8_t(x>>(i*8)));}
inline uint32_t Take(const std::vector<uint8_t>& b,size_t& at){NS_ABORT_MSG_IF(at+4>b.size(),"truncated envelope");uint32_t x=0;for(int i=0;i<4;++i)x=(x<<8)|b[at++];return x;}
template<class T> void PutTag(std::vector<uint8_t>& b,Ptr<Packet> p){T tag;NS_ABORT_MSG_IF(!p->PeekPacketTag(tag),"missing native tag");size_t at=b.size();b.resize(at+tag.GetSerializedSize());tag.Serialize(TagBuffer(b.data()+at,b.data()+b.size()));}
template<class T> void TakeTag(const std::vector<uint8_t>& b,size_t& at,Ptr<Packet> p){T tag;auto n=tag.GetSerializedSize();NS_ABORT_MSG_IF(at+n>b.size(),"truncated native tag");std::vector<uint8_t> raw(b.begin()+at,b.begin()+at+n);tag.Deserialize(TagBuffer(raw.data(),raw.data()+n));p->AddPacketTag(tag);at+=n;}
// An integrity checksum only. Actual received payload bytes are always used to
// reconstruct the native packet, and the application still verifies those bytes.
inline uint64_t PayloadChecksum(const uint8_t* bytes,size_t count){uint64_t hash=14695981039346656037ULL;for(size_t i=0;i<count;++i){hash^=bytes[i];hash*=1099511628211ULL;}return hash;}
inline Ptr<Packet> Reconstruct(uint32_t rank,uint32_t group,uint32_t sequence,Ptr<Packet> payload);
class SharedSource : public UbIngressQueue {
public:
 struct Child {uint32_t rank;Ptr<UbTransportChannel> tp;};
 struct OracleMember {uint32_t destinationTp,psn,taSsn;std::vector<uint8_t> nativeMetadata;};
 struct OracleEnvelope {HeaderMode mode;uint32_t offset,length;uint64_t mask,remaining,checksum;std::map<uint32_t,OracleMember> members;};
 HeaderMode headerMode{HeaderMode::FULL};
 std::vector<Child> all,active; std::set<uint32_t> memberDone; std::map<uint32_t,uint32_t> memberTasks;
 uint32_t group{0},sequence{0},totalBytes{0},sentBytes{0},segmentBytes{1024};
 uint64_t envelopes{0},payloadSent{0},wireDataBytes{0},barrierChecks{0},emptyWaits{0},windowWaits{0};
 uint64_t chargedHeaderBytes{0},nativeChildHeaderBytes{0},fullModelHeaderBytes{0};
 uint64_t oracleNativeMetadataBytes{0},peakOracleNativeMetadataBytes{0},peakOracleEnvelopes{0};
 uint64_t oracleEnvelopeLimit{0};
 // This registry belongs to one installed source queue. GroupManager rejects
 // reused native children and duplicate groups; there is no global cross-source
 // lookup. Native ordered reception makes the pending sequence union a suffix,
 // bounded by the largest installed per-child send window.
 std::map<std::pair<uint32_t,uint32_t>,OracleEnvelope> pendingOracle;
 std::function<void(uint32_t,bool)> grantObserver;
 Ptr<UbPort> port;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::LightweightSharedSource").SetParent<UbIngressQueue>().AddConstructor<SharedSource>();return t;}
 IngressQueueType GetIngressQueueType() override{return IngressQueueType::CTP;}
 void Install(Ptr<UbPort> p,const std::vector<Child>& c){port=p;all=c;SetInPortId(p->GetIfIndex());SetOutPortId(p->GetIfIndex());SetIngressPriority(7);auto alloc=p->GetNode()->GetObject<UbSwitch>()->GetAllocator();
  std::set<uint32_t> ranks;std::set<const UbTransportChannel*> pointers;BooleanValue cc;GlobalValue::GetValueByName("UB_CC_ENABLED",cc);NS_ABORT_MSG_IF(cc.Get(),"adapter excludes congestion control");for(auto& x:all){NS_ABORT_MSG_IF(!x.tp||x.rank>=64||!ranks.insert(x.rank).second||!pointers.insert(PeekPointer(x.tp)).second||x.tp->GetSrc()!=p->GetNode()->GetId()||x.tp->GetDest()!=x.rank||x.tp->GetOutPortId()!=p->GetIfIndex()||x.tp->GetIngressPriority()!=7,"invalid/duplicate native child binding");NS_ABORT_MSG_IF(!x.tp->IsSafeForExplicitDestroy(),"install requires quiescent TP");BooleanValue enabled;x.tp->GetAttribute("EnableRetrans",enabled);NS_ABORT_MSG_IF(enabled.Get(),"adapter excludes retransmission");alloc->UnregisterUbIngressQueue(x.tp,p->GetIfIndex(),7);}
  if(headerMode!=HeaderMode::FULL){(void)HeaderModeName(headerMode);for(auto& x:all){UintegerValue window;x.tp->GetAttribute("DefaultMaxInflightPacketSize",window);NS_ABORT_MSG_IF(!window.Get(),"oracle requires finite positive native send window");oracleEnvelopeLimit=std::max(oracleEnvelopeLimit,window.Get());}}
  alloc->RegisterUbIngressQueue(this,p->GetIfIndex(),7);
 }
 void Select(uint32_t id,uint32_t bytes,const std::vector<uint32_t>& ranks){NS_ABORT_MSG_IF(sentBytes!=totalBytes||(totalBytes&&memberDone.size()!=active.size())||!pendingOracle.empty()||oracleNativeMetadataBytes,"replace active group before native member completion");memberDone.clear();memberTasks.clear();group=id;totalBytes=bytes;sentBytes=sequence=0;active.clear();std::set<uint32_t> unique;for(auto r:ranks){NS_ABORT_MSG_IF(r>=64||!unique.insert(r).second,"duplicate/out-of-range group member");auto it=std::find_if(all.begin(),all.end(),[&](const Child& c){return c.rank==r;});NS_ABORT_MSG_IF(it==all.end(),"unprovisioned group member");active.push_back(*it);}NS_ABORT_MSG_IF(active.empty(),"empty group");}
 void SetMemberTasks(const std::map<uint32_t,uint32_t>& tasks){NS_ABORT_MSG_IF(sentBytes||tasks.size()!=active.size(),"member task setup");std::set<uint32_t> unique;for(auto& c:active)NS_ABORT_MSG_IF(!tasks.count(c.rank)||!unique.insert(tasks.at(c.rank)).second,"member task identity");memberTasks=tasks;}
 uint32_t MemberTask(uint32_t rank)const{auto it=memberTasks.find(rank);return it==memberTasks.end()?group:it->second;}
 bool MemberComplete(uint32_t rank,uint32_t task){NS_ABORT_MSG_IF(task!=MemberTask(rank)||!totalBytes||sentBytes!=totalBytes||std::none_of(active.begin(),active.end(),[&](const Child& c){return c.rank==rank;})||!memberDone.insert(rank).second,"invalid/duplicate/early member completion");return memberDone.size()==active.size();}
 void Refresh(){RefreshAllocatorSummary();}
 Ptr<UbTransportChannel> Control(){for(auto& c:all)if(!c.tp->m_cnpQ.empty())return c.tp;for(auto& c:all)if(!c.tp->m_ackQ.empty())return c.tp;return nullptr;}
 bool IsEmpty() override{for(auto& c:all)if(!c.tp->IsEmpty())return false;return true;}
 bool IsLimited() override{if(Control())return false;if(active.empty())return true;for(auto& c:active){if(c.tp->IsEmpty()){++barrierChecks;++emptyWaits;return true;}if(c.tp->IsLimited()){++barrierChecks;++windowWaits;return true;}}return false;}
 uint32_t GetNextPacketSize() override{if(auto t=Control())return t->GetNextPacketSize();if(active.size()==1)return active.front().tp->GetNextPacketSize();if(active.empty()||sentBytes>=totalBytes)return 0;
  uint32_t len=std::min(segmentBytes,totalBytes-sentBytes);
  // 4B outer DL, 28B envelope, per member rank+prefix length (8), native prefix (78), tags (8+42+1).
  return ChargedHeaderBytes(headerMode,active.size())+len;
 }
 Ptr<Packet> GetNextPacket() override{
  if(grantObserver)grantObserver(group,bool(Control()));
  if(auto t=Control()){auto p=t->GetNextPacket();Refresh();return p;}
  NS_ABORT_MSG_IF(IsLimited(),"coalescer dequeue before all native children eligible");
  if(active.size()==1){auto p=active.front().tp->GetNextPacket();NS_ABORT_MSG_IF(!p,"empty singleton dequeue");if(totalBytes){UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!active.front().tp->ParseReceivedDataPacketForTest(p->Copy(),ctx)||ctx.flowTag.GetFlowId()!=MemberTask(active.front().rank)||ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE)||ctx.payloadBytes!=std::min(segmentBytes,totalBytes-sentBytes),"singleton child identity/length");}UbNetworkReplicationTag tag;tag.destinations=uint64_t{1}<<active.front().rank;tag.nativeSingleton=true;tag.object=group;p->AddPacketTag(tag);if(totalBytes){NS_ABORT_MSG_IF(p->GetSize()<78,"singleton WRITE size");auto len=p->GetSize()-78;sentBytes+=len;payloadSent+=len;wireDataBytes+=p->GetSize();chargedHeaderBytes+=78;nativeChildHeaderBytes+=78;fullModelHeaderBytes+=78;}Refresh();return p;}
  const uint32_t expectedSize=GetNextPacketSize(),len=std::min(segmentBytes,totalBytes-sentBytes);
  for(auto& c:active)NS_ABORT_MSG_IF(c.tp->GetNextPacketSize()!=78+len,"unmatched next native packet size");
  uint64_t mask=0;for(auto& c:active)mask|=uint64_t{1}<<c.rank;
  // All modes pay the common 28-byte envelope plus the original 4-byte DL.
  std::vector<uint8_t> b;Put(b,EnvelopeMagic(headerMode));Put(b,group);Put(b,sequence);Put(b,len);Put(b,active.size());Put(b,uint32_t(mask>>32));Put(b,uint32_t(mask));
  OracleEnvelope oracle{headerMode,sentBytes,len,mask,mask,0,{}};
  if(headerMode!=HeaderMode::FULL)NS_ABORT_MSG_IF(!oracleEnvelopeLimit||pendingOracle.size()>=oracleEnvelopeLimit,"oracle records exceed native send-window bound");
  std::vector<uint8_t> shared;
  for(auto& c:active){auto packet=c.tp->GetNextPacket();NS_ABORT_MSG_IF(!packet,"native child dequeue failed");UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!c.tp->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"native child decode failed");
   NS_ABORT_MSG_IF(ctx.flowTag.GetFlowId()!=MemberTask(c.rank)||ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE)||ctx.payloadBytes!=len,"native child range/type differs");
   std::vector<uint8_t> raw(packet->GetSize());packet->CopyData(raw.data(),raw.size());std::vector<uint8_t> payload(raw.end()-len,raw.end());if(shared.empty())shared=payload;else NS_ABORT_MSG_IF(shared!=payload,"native child payload differs");
   if(headerMode==HeaderMode::FULL){Put(b,c.rank);Put(b,raw.size()-len);b.insert(b.end(),raw.begin(),raw.end()-len);PutTag<UbFlowTag>(b,packet);PutTag<UbTransactionCorrelationTag>(b,packet);PutTag<UbExplicitPayloadTag>(b,packet);}
   else {
    OracleMember member{ctx.transportHeader.GetDestTpn(),ctx.transportHeader.GetPsn(),ctx.transactionHeader.GetIniTaSsn(),{raw.begin(),raw.end()-len}};
    NS_ABORT_MSG_IF(member.nativeMetadata.size()!=78,"oracle native prefix size");PutTag<UbFlowTag>(member.nativeMetadata,packet);PutTag<UbTransactionCorrelationTag>(member.nativeMetadata,packet);PutTag<UbExplicitPayloadTag>(member.nativeMetadata,packet);
    NS_ABORT_MSG_IF(member.nativeMetadata.size()!=129||!oracle.members.emplace(c.rank,member).second,"oracle member metadata");
    if(headerMode==HeaderMode::COMPACT_ORACLE){Put(b,c.rank);Put(b,member.destinationTp);Put(b,member.psn);Put(b,member.taSsn);}
   }
  }
  if(headerMode!=HeaderMode::FULL){oracle.checksum=PayloadChecksum(shared.data(),shared.size());NS_ABORT_MSG_IF(!pendingOracle.emplace(std::make_pair(group,sequence),std::move(oracle)).second,"duplicate oracle envelope identity");oracleNativeMetadataBytes+=129*active.size();peakOracleNativeMetadataBytes=std::max(peakOracleNativeMetadataBytes,oracleNativeMetadataBytes);peakOracleEnvelopes=std::max(peakOracleEnvelopes,uint64_t(pendingOracle.size()));}
  b.insert(b.end(),shared.begin(),shared.end());auto packet=Create<Packet>(b.data(),b.size());UbDatalinkPacketHeader dl;dl.SetPacketVL(7);packet->AddHeader(dl);UbNetworkReplicationTag tag;tag.destinations=mask;tag.object=group;tag.sequence=sequence++;tag.nativeEnvelope=true;packet->AddPacketTag(tag);
  NS_ABORT_MSG_IF(packet->GetSize()!=expectedSize,"predicted envelope size differs");sentBytes+=len;++envelopes;payloadSent+=len;wireDataBytes+=packet->GetSize();chargedHeaderBytes+=packet->GetSize()-len;nativeChildHeaderBytes+=78*active.size();fullModelHeaderBytes+=ChargedHeaderBytes(HeaderMode::FULL,active.size());Refresh();return packet;
 }
 uint64_t GetOraclePendingCount() const{return pendingOracle.size();}
 void CheckOracleDrained() const{NS_ABORT_MSG_IF(!pendingOracle.empty()||oracleNativeMetadataBytes,"oracle native restoration metadata not drained");}
 Ptr<Packet> ReconstructReceived(uint32_t rank,uint32_t id,uint32_t seq,Ptr<Packet> payload){
  if(headerMode==HeaderMode::FULL)return Reconstruct(rank,id,seq,payload);
  NS_ABORT_MSG_IF(!payload||rank>=64||id!=group,"oracle receive identity");
  auto found=pendingOracle.find({id,seq});NS_ABORT_MSG_IF(found==pendingOracle.end(),"unknown/already consumed oracle envelope");auto& record=found->second;
  NS_ABORT_MSG_IF(record.mode!=headerMode||!(record.remaining&(uint64_t{1}<<rank))||!record.members.count(rank),"oracle mode/member/duplicate mismatch");
  NS_ABORT_MSG_IF(record.offset!=uint64_t(seq)*segmentBytes||record.offset>totalBytes||record.length>totalBytes-record.offset||record.length!=std::min(segmentBytes,totalBytes-record.offset),"oracle payload range");
  std::vector<uint8_t> b(payload->GetSize());payload->CopyData(b.data(),b.size());size_t at=0;
  NS_ABORT_MSG_IF(Take(b,at)!=EnvelopeMagic(headerMode)||Take(b,at)!=id||Take(b,at)!=seq,"oracle wire identity");uint32_t len=Take(b,at),count=Take(b,at);uint64_t mask=uint64_t(Take(b,at))<<32;mask|=Take(b,at);
  NS_ABORT_MSG_IF(len!=record.length||count!=record.members.size()||mask!=record.mask||b.size()+4!=len+ChargedHeaderBytes(headerMode,count),"oracle wire size/membership");
  if(headerMode==HeaderMode::COMPACT_ORACLE){uint64_t seen=0;for(uint32_t i=0;i<count;++i){uint32_t r=Take(b,at),tp=Take(b,at),psn=Take(b,at),ssn=Take(b,at);auto member=record.members.find(r);NS_ABORT_MSG_IF(r>=64||member==record.members.end()||(seen&(uint64_t{1}<<r)),"oracle compact member identity");seen|=uint64_t{1}<<r;NS_ABORT_MSG_IF(tp!=member->second.destinationTp||psn!=member->second.psn||ssn!=member->second.taSsn,"oracle compact native identity");}NS_ABORT_MSG_IF(seen!=mask,"oracle compact member coverage");}
  NS_ABORT_MSG_IF(at+len!=b.size()||PayloadChecksum(b.data()+at,len)!=record.checksum,"oracle received payload mismatch");
  const auto& native=record.members.at(rank).nativeMetadata;NS_ABORT_MSG_IF(native.size()!=129,"oracle restoration prefix size");auto packet=Create<Packet>(native.data(),78);size_t nativeAt=78;TakeTag<UbFlowTag>(native,nativeAt,packet);TakeTag<UbTransactionCorrelationTag>(native,nativeAt,packet);TakeTag<UbExplicitPayloadTag>(native,nativeAt,packet);NS_ABORT_MSG_IF(nativeAt!=native.size(),"oracle native metadata trailing bytes");packet->AddAtEnd(Create<Packet>(b.data()+at,len));
  // Keep no payload or completed envelope history. The remaining set shrinks at
  // actual sink receipt, before native ACK/Response processing takes ownership.
  record.remaining&=~(uint64_t{1}<<rank);if(!record.remaining){NS_ABORT_MSG_IF(oracleNativeMetadataBytes<129*record.members.size(),"oracle metadata accounting underflow");oracleNativeMetadataBytes-=129*record.members.size();pendingOracle.erase(found);}return packet;
 }
};
// Decode actual received bytes, not a shared-memory side channel. Native TP remains authoritative.
inline Ptr<Packet> Reconstruct(uint32_t rank,uint32_t group,uint32_t sequence,Ptr<Packet> payload){std::vector<uint8_t> b(payload->GetSize());payload->CopyData(b.data(),b.size());size_t at=0;NS_ABORT_MSG_IF(Take(b,at)!=0x55424d31||Take(b,at)!=group||Take(b,at)!=sequence,"envelope identity");uint32_t len=Take(b,at),count=Take(b,at);uint64_t mask=uint64_t(Take(b,at))<<32;mask|=Take(b,at);NS_ABORT_MSG_IF(!count||count>64||rank>=64||!(mask&(uint64_t{1}<<rank)),"envelope membership");
 Ptr<Packet> selected;uint64_t seen=0;
 for(uint32_t i=0;i<count;++i){uint32_t r=Take(b,at),prefix=Take(b,at);NS_ABORT_MSG_IF(r>=64||!(mask&(uint64_t{1}<<r))||(seen&(uint64_t{1}<<r))||prefix!=78||at+prefix>b.size(),"envelope header record");seen|=uint64_t{1}<<r;auto p=Create<Packet>(b.data()+at,prefix);at+=prefix;TakeTag<UbFlowTag>(b,at,p);TakeTag<UbTransactionCorrelationTag>(b,at,p);TakeTag<UbExplicitPayloadTag>(b,at,p);if(r==rank)selected=p;}
 NS_ABORT_MSG_IF(seen!=mask||!selected||at+len!=b.size(),"envelope payload length/members");selected->AddAtEnd(Create<Packet>(b.data()+at,len));return selected;
}
}
