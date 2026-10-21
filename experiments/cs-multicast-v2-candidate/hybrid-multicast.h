// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "../multicast-controlled-ablation/pair-multicast-v2.h"
#include <sys/resource.h>
#include <array>
namespace csmc {
using namespace ns3;
// Only this APP wrapper changes. UbWriteV2 bytes, native WRITE builders, ACKs,
// retransmission descriptors and the switch decoder remain the accepted v2 path.
class OffsetCodec : public writev2::SharedSource {
public:
 uint32_t previousEnd=0;
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::CsMcOffsetCodec").SetParent<writev2::SharedSource>().AddConstructor<OffsetCodec>();return t;}
 Ptr<Packet> EmitAt(uint32_t relativeOffset,uint32_t length){
  NS_ABORT_MSG_IF(relativeOffset<previousEnd||relativeOffset>=totalBytes||length!=std::min(segmentBytes,totalBytes-relativeOffset),"hybrid envelope cursor/range");
  // sentBytes is ONLY the inherited codec's emission cursor, never logical coverage.
  // Gaps were sent by native unicast. Sequence/counters advance only in real Encode.
  sentBytes=relativeOffset;auto p=writev2::SharedSource::GetNextPacket();
  NS_ABORT_MSG_IF(sentBytes!=relativeOffset+length||!UbWriteV2::IsEnvelope(p),"hybrid envelope emission");previousEnd=sentBytes;return p;
 }
};
enum class Role:uint32_t {Stage1,Stage2,DirectFallback};
inline const char* RoleName(Role r){return r==Role::Stage1?"stage1":r==Role::Stage2?"stage2":"direct-fallback";}
enum class Reason:uint32_t {Merge,Singleton,Absent,Priority,Limited,WrongTask,WrongKind,Offset,Length,Header,Egress,Credit,Association,Count};
inline const char* ReasonName(Reason r){static const char* names[]={"merged","singleton","member_absent","member_priority","member_native_limited","member_task_mismatch","member_kind_mismatch","member_offset_mismatch","member_length_mismatch","unsupported_header","envelope_egress_fit","envelope_credit_fit","codec_association_capacity"};return names[uint32_t(r)];}
// Native segment identity is full logical uint32; serialized TA SSN is wire16.
// The captured full identity owns offsets even when the pair Jetty wraps.
constexpr bool WireSsnMatches(uint32_t logical,uint32_t wire){return wire==(logical&65535u);}
static_assert(WireSsnMatches(65536u+42u,42u));
static_assert(!WireSsnMatches(65536u+42u,43u));
static_assert(!WireSsnMatches(65536u+42u,65536u+42u));
class Manager;
class Proxy:public UbIngressQueue {
public:
 Manager* manager{};uint32_t source{},target{};Ptr<UbTransportChannel> tp;Ptr<UbPort> port;
 bool invalidateOnce{},invalidationScheduled{};Time blockedUntil=Seconds(0);uint64_t invalidatedGrants{};
 // Candidate state is per persistent TP, never per group or RR grant.
 struct HoldState {
  bool known=false,active=false,spent=false,consumed=false;uint32_t task=0,ssn=0,offset=0,length=0,group=0,member=0;
  uint64_t generation=0,armedPs=0,deadlinePs=0,releasedPs=0;EventId expiry;
 } hold;
 bool RevalidateOnCommit()const{return true;}
 static TypeId GetTypeId(){static TypeId t=TypeId("ns3::CsMcPairProxy").SetParent<UbIngressQueue>().AddConstructor<Proxy>().AddAttribute("RevalidateOnCommit","Revalidate exact native heads and actual envelope fit at commit.",TypeId::ATTR_GET,BooleanValue(true),MakeBooleanAccessor(&Proxy::RevalidateOnCommit),MakeBooleanChecker());return t;}
 IngressQueueType GetIngressQueueType()override{return IngressQueueType::TP;}
 bool IsEmpty()override{return tp->IsEmpty()&&!tp->GetOutstandingUnackedSegmentCount();}
 bool IsLimited()override;
 uint32_t GetNextPacketSize()override;
 Ptr<Packet> GetNextPacket()override;
 void Refresh(){m_headArrivalTime=tp->GetHeadArrivalTime();RefreshAllocatorSummary();}
};
class Manager {
public:
 static constexpr uint64_t maxStage2Tasks=65536,maxEntries=131072,maxRssBytes=UINT64_C(6)*1024*1024*1024;
 struct Member {uint32_t rank,task;Ptr<UbTransportChannel> tx,rx;uint32_t firstBytes=0;uint64_t submittedPs=0,firstPs=0,firstDonePs=0,senderPs=0;bool submitted=false,complete=false;};
 struct Group {
  uint32_t id,source,sourcePhysical,expert,globalOffset,bytes,segment;Role role;std::vector<uint32_t> dependencies;std::vector<Member> members;Ptr<UbPort> port;Ptr<OffsetCodec> codec;
  uint32_t firstDone=0,completed=0;uint64_t completePs=0;
  uint64_t envelopes=0,envelopePayload=0,envelopeWire=0,envelopeHeaders=0,branchPayload=0,branchWire=0,nativePackets=0,nativePayload=0,nativeWire=0,associationPeak=0,restored=0,associationCapacity=0,firstEnvelopeOffset=UINT64_MAX,lastEnvelopeEnd=0;
 };
 struct TaskRef {uint32_t group=0,member=0;};
 struct Choice {uint32_t group=0,member=0,offset=0,length=0,size=0,logicalSsn=0;Reason reason=Reason::WrongTask;bool merge=false;};
 struct Fallback {uint64_t packets=0,payload=0,wire=0;};
 bool alignHold=false; // Only Candidate enables this; immutable fixed 5 ns, no sweep.
 static constexpr uint64_t holdPs=5000;
 uint64_t holdsArmed=0,holdsReleased=0,holdExpired=0,holdEarly=0,holdHeadChanged=0,holdPriorityBypass=0,maxHoldPs=0,activeHolds=0,peakHolds=0,heldHeadsConsumed=0,maxReleaseToConsumePs=0;
 std::map<std::string,uint64_t> holdFallback;
 std::function<void(Proxy&,const Choice&,const char*,const char*)> holdTrace;
 ~Manager(){for(auto& item:pairs)item.second->hold.expiry.Cancel();}
 std::vector<Group> groups; // group id is index + 1; immutable after setup
 std::vector<TaskRef> taskIndex;
 std::map<std::pair<uint32_t,uint32_t>,Ptr<Proxy>> pairs,localTp;
 std::set<uint32_t> sources;
 std::function<uint64_t(uint32_t,uint32_t)> offset;
 std::function<void(uint32_t,uint32_t,Ptr<Packet>,bool)> observe;
 std::function<void(const Choice&,Ptr<Packet>,bool)> pulled;
 reversal::Recorder* diagnostic=nullptr;
 std::array<std::array<Fallback,size_t(Reason::Count)>,3> fallback{};
 uint64_t descriptorEntries=0,liveCodecs=0,peakCodecs=0,allocatedCodecs=0,retiredCodecs=0,pendingAssociations=0,peakAssociations=0,pendingMembers=0,peakPendingMembers=0,retainedAssociationCapacity=0,peakAssociationCapacity=0,peakRssBytes=0,pulls=0,retries=0,retryBytes=0,retryWeightPackets=0,retryWeightBytes=0;
 Group& G(uint32_t id){NS_ABORT_MSG_IF(!id||id>groups.size(),"hybrid group identity");return groups[id-1];}
 const Group& G(uint32_t id)const{NS_ABORT_MSG_IF(!id||id>groups.size(),"hybrid group identity");return groups[id-1];}
 void CheckRss(){struct rusage u{};NS_ABORT_MSG_IF(getrusage(RUSAGE_SELF,&u),"hybrid RSS accounting unavailable");peakRssBytes=std::max(peakRssBytes,uint64_t(u.ru_maxrss)*1024);NS_ABORT_MSG_IF(peakRssBytes>maxRssBytes,"hybrid RSS exceeds 6 GiB hard safety limit");}
 void Initialize(size_t totalTasks){NS_ABORT_MSG_IF(!groups.empty()||!taskIndex.empty()||totalTasks>maxEntries,"hybrid task lookup bound");taskIndex.resize(totalTasks);}
 void Add(uint32_t source,uint32_t sourcePhysical,uint32_t expert,uint32_t globalOffset,uint32_t bytes,uint32_t segment,Role role,const std::vector<uint32_t>& deps,Ptr<UbPort> port,std::vector<Member> members){
  NS_ABORT_MSG_IF(groups.size()>=maxStage2Tasks||members.empty()||members.size()>63||source>=64||!bytes||!segment||segment>4096,"hybrid immutable group bound");
  const auto id=uint32_t(groups.size()+1);descriptorEntries+=1+members.size()+deps.size();NS_ABORT_MSG_IF(descriptorEntries>maxEntries,"hybrid immutable descriptor entries hard bound");
  std::set<uint32_t> ranks;for(uint32_t i=0;i<members.size();++i){auto&m=members[i];NS_ABORT_MSG_IF(m.rank==source||!ranks.insert(m.rank).second||!m.tx||!m.rx||m.task>=taskIndex.size()||taskIndex[m.task].group||m.tx->GetSrc()!=source||m.tx->GetDest()!=m.rank||m.tx->GetDestTpn()!=m.rx->GetTpn()||m.rx->GetDestTpn()!=m.tx->GetTpn(),"hybrid member binding/provenance");taskIndex[m.task]={id,i};}
  Group g;g.id=id;g.source=source;g.sourcePhysical=sourcePhysical;g.expert=expert;g.globalOffset=globalOffset;g.bytes=bytes;g.segment=segment;g.role=role;g.dependencies=deps;g.members=std::move(members);g.port=port;groups.push_back(std::move(g));sources.insert(source);
 }
 static bool Priority(Ptr<UbTransportChannel> tp){return !tp->m_cnpQ.empty()||!tp->m_ackQ.empty()||(tp->GetRetransEnable()&&tp->HasPendingGbnRetransmissionForTest());}
 static uint64_t CellBytes(Ptr<UbPort> port){UintegerValue flit,cells;port->GetAttribute("CbfcFlitLenByte",flit);port->GetAttribute("CbfcFlitsPerCell",cells);NS_ABORT_MSG_IF(!flit.Get()||!cells.Get(),"hybrid credit geometry");return flit.Get()*cells.Get();}
 // No reservations, waiting, queue mutation, sequence changes or query counters.
 // A failed full fixed-membership match means selected native progress, not a stall.
 Choice Choose(Proxy& p){
  Choice c;c.size=p.tp->GetNextPacketSize();if(Priority(p.tp))return c;
  auto selected=p.tp->PeekOriginalSegmentForAdapter();if(!selected||selected->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST)return c;
  if(selected->GetTaskId()>=taskIndex.size())return c;auto ref=taskIndex[selected->GetTaskId()];if(!ref.group)return c;
  c.group=ref.group;c.member=ref.member;auto&g=G(c.group);auto&sm=g.members[c.member];NS_ABORT_MSG_IF(g.source!=p.source||sm.rank!=p.target||sm.tx!=p.tp,"hybrid selected identity");
  NS_ABORT_MSG_IF(!offset||!sm.submitted,"hybrid native head before original submission");c.logicalSsn=selected->GetTaSsn();c.offset=offset(sm.task,c.logicalSsn);
  NS_ABORT_MSG_IF(c.offset>=g.bytes||c.offset!=sm.firstBytes,"hybrid original first-send progression");c.length=std::min(g.segment,g.bytes-c.offset);
  if(g.members.size()==1){c.reason=Reason::Singleton;return c;}
  uint64_t size=24+2*g.members.size()+c.length;std::vector<uint8_t> payload;
  for(auto&m:g.members){
   if(Priority(m.tx)){c.reason=Reason::Priority;return c;}
   if(m.tx->IsEmpty()){c.reason=Reason::Absent;return c;}
   if(m.tx->IsLimited()){c.reason=Reason::Limited;return c;}
   auto s=m.tx->PeekOriginalSegmentForAdapter();if(!s){c.reason=Reason::Absent;return c;}
   if(s->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST){c.reason=Reason::WrongKind;return c;}
   if(s->GetTaskId()!=m.task){c.reason=Reason::WrongTask;return c;}
   if(offset(m.task,s->GetTaSsn())!=c.offset){c.reason=Reason::Offset;return c;}
   if(s->GetType()!=UbTransactionOpcode::WRITE||s->GetBytesLeft()!=s->GetCarrierBytes()||s->GetPayloadBytes()!=c.length||s->GetCarrierBytes()!=c.length||!s->HasExplicitPayload()||s->GetExplicitPayload()->GetSize()!=c.length){c.reason=Reason::Length;return c;}
   // Native DL/VL comes from the TP, not the WQE segment (whose default is 8).
   // Keep the submitted WQE untouched; accepted native pairs serialize TP priority 7.
   const uint32_t native=m.tx->GetNextPacketSize();if(native!=78+c.length||m.tx->GetPriority()!=7){c.reason=Reason::Header;return c;}
   NS_ABORT_MSG_IF(!m.submitted||m.firstBytes!=c.offset,"hybrid matched identity/coverage corruption");
   std::vector<uint8_t> bytes(c.length);s->GetExplicitPayload()->CopyData(bytes.data(),bytes.size());if(payload.empty())payload=std::move(bytes);else NS_ABORT_MSG_IF(payload!=bytes,"hybrid same-range native payload differs");size+=native-c.length-4;
  }
  NS_ABORT_MSG_IF(size>UINT32_MAX,"hybrid envelope size overflow");
  if(g.codec&&g.codec->pending.size()>=g.codec->capacity){c.reason=Reason::Association;return c;}
  if(!p.port->GetUbQueue()->CanEnqueue(size)){c.reason=Reason::Egress;return c;}
  auto fc=DynamicCast<UbCbfc>(p.port->GetFlowControl());NS_ABORT_MSG_IF(!fc,"hybrid requires native CBFC");auto cells=(size+CellBytes(p.port)-1)/CellBytes(p.port);if(int64_t(cells)>fc->GetTxFreeCells(7)){c.reason=Reason::Credit;return c;}
  c.size=size;c.merge=true;c.reason=Reason::Merge;return c;
 }
 // Structural-only classification: no CC/IsLimited queries, proxy recursion,
 // arming, reservations, or dequeue. Choose may have observed only a prefix;
 // unobserved peer CC eligibility is UNKNOWN, not proven ready.
 // Native priority masks original-data eligibility. Do not probe generic CC here:
 // structurally aligned priority peers are speculative, with data eligibility UNKNOWN.
 struct HoldDecision {bool wait=false;const char* why="not_chunk_head";};
 HoldDecision ClassifyHold(Proxy&p,const Choice&c){
  if(!c.group)return {};auto&g=G(c.group);
  if(g.role==Role::DirectFallback)return {false,"whole_expert_fallback"};
  if(g.members.size()<2)return {false,"singleton"};
  if(c.merge)return {false,"full_merge_ready"};
  if(c.reason==Reason::Limited)return {false,"member_native_limited"};
  auto selected=p.tp->PeekOriginalSegmentForAdapter();
  if(!selected||selected->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST||selected->GetType()!=UbTransactionOpcode::WRITE)return {false,"selected_not_write"};
  bool absent=false,priorityUnknown=false;std::vector<uint8_t> reference;
  for(auto&m:g.members){
   if(!m.submitted)return {false,"member_unsubmitted"};
   if(m.complete||m.firstBytes!=c.offset)return {false,m.firstBytes>c.offset?"member_consumed":"member_coverage_offset"};
   const bool priority=Priority(m.tx);priorityUnknown|=priority;
   if(m.tx->IsInflightLimited())return {false,"member_inflight_limited"};
   auto head=m.tx->PeekOriginalSegmentForAdapter();
   if(!head){if(priority)return {false,"priority_missing_original"};absent=true;continue;}
   if(head->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST)return {false,"member_kind_mismatch"};
   if(head->GetTaskId()!=m.task)return {false,"member_task_mismatch"};
   if(offset(m.task,head->GetTaSsn())!=c.offset)return {false,"member_offset_mismatch"};
   if(head->GetType()!=UbTransactionOpcode::WRITE||head->GetBytesLeft()!=head->GetCarrierBytes()||head->GetPayloadBytes()!=c.length||head->GetCarrierBytes()!=c.length||!head->HasExplicitPayload()||head->GetExplicitPayload()->GetSize()!=c.length)return {false,"member_length_mismatch"};
   if(m.tx->GetPriority()!=7||(!priority&&m.tx->GetNextPacketSize()!=78+c.length))return {false,"unsupported_header"};
   std::vector<uint8_t> bytes(c.length);head->GetExplicitPayload()->CopyData(bytes.data(),bytes.size());
   if(reference.empty())reference=std::move(bytes);else if(reference!=bytes)return {false,"member_payload_mismatch"};
  }
  // Predicted hidden WRITE size for hold budgeting only; actual send still uses Choose.
  const uint64_t size=24+76*g.members.size()+c.length;
  if(g.codec&&g.codec->pending.size()>=g.codec->capacity)return {false,"codec_association_capacity"};
  if(!p.port->GetUbQueue()->CanEnqueue(size))return {false,"envelope_egress_fit"};
  auto fc=DynamicCast<UbCbfc>(p.port->GetFlowControl());NS_ABORT_MSG_IF(!fc,"candidate requires native CBFC");
  if(int64_t((size+CellBytes(p.port)-1)/CellBytes(p.port))>fc->GetTxFreeCells(7))return {false,"envelope_credit_fit"};
  return priorityUnknown?HoldDecision{true,"priority_with_unknown_data_eligibility"}:absent?HoldDecision{true,"submitted_aligned_absent_data_eligibility_unknown"}:HoldDecision{false,"no_transient_obstruction"};
 }
 Choice HeldChoice(const Proxy&p)const{Choice c;c.group=p.hold.group;c.member=p.hold.member;c.offset=p.hold.offset;c.length=p.hold.length;c.logicalSsn=p.hold.ssn;return c;}
 void ReleaseHold(Proxy&p,const char* why){
  auto&h=p.hold;if(!h.active)return;const uint64_t now=Simulator::Now().GetPicoSeconds();
  NS_ABORT_MSG_IF(now>h.deadlinePs,"candidate hold missed fixed deadline");
  h.active=false;h.spent=true;h.releasedPs=now;h.expiry.Cancel();--activeHolds;++holdsReleased;
  maxHoldPs=std::max(maxHoldPs,now-h.armedPs);
  if(std::string(why)=="deadline")++holdExpired;else if(std::string(why)=="head_changed"||std::string(why)=="head_consumed")++holdHeadChanged;else ++holdEarly;
  if(holdTrace)holdTrace(p,HeldChoice(p),"release",why);
 }
 // This is intentionally stateful IsLimited, including scanned but ungranted TPs.
 // Never Refresh while arming: summary refresh may recursively query IsLimited.
 bool HoldLimited(Proxy&p,bool nativeLimited){
  if(!alignHold)return nativeLimited;auto&h=p.hold;
  auto head=p.tp->PeekOriginalSegmentForAdapter();
  const bool same=h.known&&head&&head->GetTaskId()==h.task&&head->GetTaSsn()==h.ssn&&head->GetSegmentKind()==UbTransactionSegmentKind::REQUEST;
  if(h.known&&!same){ReleaseHold(p,"head_changed");h.expiry.Cancel();const auto next=h.generation+1;h=Proxy::HoldState{};h.generation=next;}
  if(h.active&&uint64_t(Simulator::Now().GetPicoSeconds())>=h.deadlinePs)ReleaseHold(p,"deadline");
  if(Priority(p.tp)){if(h.active)++holdPriorityBypass;return nativeLimited;}
  if(nativeLimited){ReleaseHold(p,"selected_native_limited");return true;}
  // Excluded paths perform no extra Choose/native policy probes.
  if(!head||head->GetSegmentKind()!=UbTransactionSegmentKind::REQUEST||head->GetType()!=UbTransactionOpcode::WRITE||head->GetTaskId()>=taskIndex.size())return false;
  const auto ref=taskIndex[head->GetTaskId()];
  if(!ref.group||G(ref.group).role==Role::DirectFallback||G(ref.group).members.size()<2)return false;
  if(h.known&&h.spent)return false;
  const auto c=Choose(p);const auto decision=ClassifyHold(p,c);
  if(!decision.wait){ReleaseHold(p,decision.why);return false;}
  if(h.active)return true;
  h.known=h.active=true;h.spent=false;h.task=G(c.group).members[c.member].task;h.ssn=c.logicalSsn;h.offset=c.offset;h.length=c.length;h.group=c.group;h.member=c.member;
  h.armedPs=Simulator::Now().GetPicoSeconds();h.deadlinePs=h.armedPs+holdPs;h.releasedPs=0;const uint64_t generation=++h.generation;
  ++holdsArmed;++activeHolds;peakHolds=std::max(peakHolds,activeHolds);
  Ptr<Proxy> self=&p;
  h.expiry=Simulator::Schedule(PicoSeconds(holdPs),[this,self,generation]{
   if(self->hold.generation!=generation||!self->hold.active)return;
   ReleaseHold(*self,"deadline");self->Refresh();self->port->TriggerTransmit();
  });
  if(holdTrace)holdTrace(p,c,"arm",decision.why);return true;
 }
 void ConsumedHold(Group&g,Member&m,uint32_t off,uint32_t len){
  if(!alignHold)return;auto it=pairs.find({g.source,m.rank});if(it==pairs.end())return;auto&p=*it->second;auto&h=p.hold;
  if(!h.known||h.consumed||h.task!=m.task||h.offset!=off||h.length!=len)return;
  ReleaseHold(p,"head_consumed");h.consumed=true;++heldHeadsConsumed;
  maxReleaseToConsumePs=std::max(maxReleaseToConsumePs,uint64_t(Simulator::Now().GetPicoSeconds())-h.releasedPs);
  if(holdTrace)holdTrace(p,HeldChoice(p),"consumed","actual_original_consumption");
 }
 void EnsureCodec(Group&g){if(g.codec)return;NS_ABORT_MSG_IF(g.completed==g.members.size(),"hybrid codec after completion");auto q=CreateObject<OffsetCodec>();q->port=g.port;q->segmentBytes=g.segment;std::vector<uint32_t> ranks;std::map<uint32_t,uint32_t> identities;
  for(auto&m:g.members){q->all.push_back({m.rank,m.tx});ranks.push_back(m.rank);identities[m.rank]=m.task;UintegerValue w;m.tx->GetAttribute("DefaultMaxInflightPacketSize",w);NS_ABORT_MSG_IF(!w.Get(),"hybrid finite native packet window required");q->capacity=std::max(q->capacity,w.Get());}
  q->Select(g.id,g.bytes,ranks);q->SetMemberTasks(identities);q->nativeObserver=[this,id=g.id,source=g.source](Ptr<Packet> p){if(observe)observe(id,source,p,false);};g.codec=q;g.associationCapacity=q->capacity;++liveCodecs;++allocatedCodecs;peakCodecs=std::max(peakCodecs,liveCodecs);retainedAssociationCapacity+=q->capacity;peakAssociationCapacity=std::max(peakAssociationCapacity,retainedAssociationCapacity);CheckRss();
 }
 void Retire(Group&g){if(!g.codec||g.firstDone!=g.members.size()||g.completed!=g.members.size()||!g.codec->pending.empty())return;g.codec->CheckDrained();g.associationPeak=g.codec->peakRecords;g.restored=g.codec->restored;retainedAssociationCapacity-=g.codec->capacity;g.codec=nullptr;--liveCodecs;++retiredCodecs;}
 void Advance(Group&g,Member&m,uint32_t off,uint32_t len){NS_ABORT_MSG_IF(!m.submitted||m.complete||off!=m.firstBytes||len!=std::min(g.segment,g.bytes-off),"hybrid actual original coverage");if(!m.firstBytes)m.firstPs=Simulator::Now().GetPicoSeconds();m.firstBytes+=len;if(m.firstBytes==g.bytes){m.firstDonePs=Simulator::Now().GetPicoSeconds();++g.firstDone;}}
 uint32_t Size(Proxy&p){return Choose(p).size;}
 Ptr<Packet> Pull(Proxy&p){
  NS_ABORT_MSG_IF(p.tp->IsEmpty()||p.tp->IsLimited(),"hybrid selected native head ineligible");const auto c=Choose(p); // same pure rule used by commit-time Size, synchronously
  if(alignHold){const char* why=c.merge?"full_merge_ready":c.group?ReasonName(c.reason):"native_priority_or_unrelated";
   if(c.group&&!c.merge){for(auto&m:G(c.group).members)if(m.firstBytes>c.offset){why="member_consumed";break;}++holdFallback[why];}
   if(holdTrace)holdTrace(p,c,"pull",why);
  }
  const bool retry=p.tp->GetRetransEnable()&&p.tp->HasPendingGbnRetransmissionForTest()&&p.tp->m_ackQ.empty()&&p.tp->m_cnpQ.empty();Ptr<Packet> packet;
  if(c.merge){auto&g=G(c.group);EnsureCodec(g);NS_ABORT_MSG_IF(pendingAssociations>=maxEntries||pendingMembers+g.members.size()>maxEntries,"hybrid pending association hard bound");packet=g.codec->EmitAt(c.offset,c.length);NS_ABORT_MSG_IF(packet->GetSize()!=c.size,"hybrid stale bigger frame");++pendingAssociations;pendingMembers+=g.members.size();peakAssociations=std::max(peakAssociations,pendingAssociations);peakPendingMembers=std::max(peakPendingMembers,pendingMembers);++g.envelopes;g.envelopePayload+=c.length;g.envelopeWire+=packet->GetSize();g.envelopeHeaders+=packet->GetSize()-c.length;g.branchPayload+=uint64_t(c.length)*g.members.size();g.branchWire+=uint64_t(78+c.length)*g.members.size();g.firstEnvelopeOffset=std::min(g.firstEnvelopeOffset,uint64_t(c.offset));g.lastEnvelopeEnd=c.offset+c.length;
   if(diagnostic&&diagnostic->enabled){std::vector<uint32_t> tasks;for(auto&m:g.members)tasks.push_back(m.task);diagnostic->BindSourceFrame(packet,g.source,tasks,Simulator::Now().GetPicoSeconds());}
   for(auto&m:g.members){ConsumedHold(g,m,c.offset,c.length);Advance(g,m,c.offset,c.length);Refresh(g.source,m.rank);}
  }else{
   packet=p.tp->GetNextPacket();NS_ABORT_MSG_IF(!packet||UbWriteV2::IsEnvelope(packet)||packet->GetSize()!=c.size,"hybrid native fallback/commit identity");
   if(retry){++retries;retryBytes+=packet->GetSize();UbFlowTag tag;if(packet->PeekPacketTag(tag)&&tag.GetFlowId()<taskIndex.size()&&taskIndex[tag.GetFlowId()].group){++retryWeightPackets;retryWeightBytes+=packet->GetSize();}if(observe)observe(0,p.source,packet,true);}
   if(c.group){auto&g=G(c.group);auto&m=g.members[c.member];UbTransportChannel::ReceivedDataPacketContext ctx;NS_ABORT_MSG_IF(!p.tp->ParseReceivedDataPacketForTest(packet->Copy(),ctx)||ctx.flowTag.GetFlowId()!=m.task||ctx.transactionHeader.GetUbTransactionOpcode()!=uint8_t(UbTransactionOpcode::WRITE)||ctx.payloadBytes!=c.length||!WireSsnMatches(c.logicalSsn,ctx.transactionHeader.GetIniTaSsn()),"hybrid actual fallback task/range");ConsumedHold(g,m,c.offset,c.length);Advance(g,m,c.offset,c.length);++g.nativePackets;g.nativePayload+=c.length;g.nativeWire+=packet->GetSize();auto&f=fallback[uint32_t(g.role)][uint32_t(c.reason)];++f.packets;f.payload+=c.length;f.wire+=packet->GetSize();if(observe)observe(g.id,p.source,packet,false);Retire(g);}
   p.Refresh();
  }
  if(pulled)pulled(c,packet,retry);if((++pulls&1023)==0)CheckRss();return packet;
 }
 void Submitted(uint32_t task){auto ref=taskIndex.at(task);auto&g=G(ref.group);auto&m=g.members.at(ref.member);NS_ABORT_MSG_IF(m.submitted,"hybrid duplicate native submission");m.submitted=true;m.submittedPs=Simulator::Now().GetPicoSeconds();}
 void Completed(uint32_t task){auto ref=taskIndex.at(task);auto&g=G(ref.group);auto&m=g.members.at(ref.member);NS_ABORT_MSG_IF(!m.submitted||m.complete||m.firstBytes!=g.bytes,"hybrid duplicate/early native completion");m.complete=true;m.senderPs=Simulator::Now().GetPicoSeconds();if(++g.completed==g.members.size())g.completePs=m.senderPs;Retire(g);}
 bool HasSource(uint32_t source)const{return sources.count(source);}
 void InstallSource(uint32_t source,Ptr<UbPort> port,const std::vector<Ptr<UbTransportChannel>>&channels,Ptr<UbSwitch> fabric){
  NS_ABORT_MSG_IF(!HasSource(source),"hybrid unneeded source proxy");auto alloc=port->GetNode()->GetObject<UbSwitch>()->GetAllocator();NS_ABORT_MSG_IF(!DynamicCast<UbRoundRobinAllocator>(alloc),"hybrid native RR required");uint32_t last=0;bool first=true;
  for(auto tp:channels){NS_ABORT_MSG_IF(!tp||tp->GetSrc()!=source||!tp->IsSafeForExplicitDestroy()||(!first&&tp->GetDest()<=last)||(tp->GetRetransEnable()&&tp->GetRetransmissionMode()!=UbRetransmissionMode::GBN),"hybrid native install order/state");last=tp->GetDest();first=false;alloc->UnregisterUbIngressQueue(tp,port->GetIfIndex(),7);}
  for(auto tp:channels){auto q=CreateObject<Proxy>();q->manager=this;q->source=source;q->target=tp->GetDest();q->tp=tp;q->port=port;q->SetInPortId(port->GetIfIndex());q->SetOutPortId(port->GetIfIndex());q->SetIngressPriority(7);NS_ABORT_MSG_IF(!pairs.emplace(std::make_pair(source,q->target),q).second||!localTp.emplace(std::make_pair(source,tp->GetTpn()),q).second,"hybrid duplicate pair owner");alloc->RegisterUbIngressQueue(q,port->GetIfIndex(),7);}
  fabric->SetWriteV2MetadataResolver(source,Callback<void,uint32_t,uint32_t,uint32_t,Ptr<Packet>>([this,source](uint32_t id,uint32_t seq,uint32_t member,Ptr<Packet> p){auto&g=G(id);NS_ABORT_MSG_IF(g.source!=source||!g.codec,"hybrid restoration operation");auto before=g.codec->pending.size();g.codec->Restore(id,seq,member,p);NS_ABORT_MSG_IF(!pendingMembers,"hybrid association accounting underflow");--pendingMembers;if(g.codec->pending.size()<before)--pendingAssociations;Retire(g);}));
 }
 void Refresh(uint32_t source,uint32_t target){auto it=pairs.find({source,target});if(it!=pairs.end())it->second->Refresh();}
 void Receive(uint32_t node,Ptr<UbPort> port,Ptr<Packet> packet){Ptr<Proxy> proxy;UbDatalinkHeader common;packet->PeekHeader(common);if(common.GetConfig()==3){auto q=packet->Copy();UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader tp;q->RemoveHeader(dl);q->RemoveHeader(net);q->RemoveHeader(ip);q->RemoveHeader(udp);q->RemoveHeader(tp);auto it=localTp.find({node,tp.GetDestTpn()});if(it!=localTp.end())proxy=it->second;}port->GetNode()->GetObject<UbSwitch>()->SwitchHandlePacket(port,packet);if(proxy)proxy->Refresh();}
 void CheckCapacity(const std::vector<Ptr<Node>>&nodes){uint32_t maximum=0;for(auto&g:groups)maximum=std::max(maximum,uint32_t((g.members.size()==1?78:24+76*g.members.size())+std::min(g.segment,g.bytes)));for(auto node:nodes){auto sw=node->GetObject<UbSwitch>();NS_ABORT_MSG_IF(maximum>sw->GetQueueManager()->GetReservePerQueueBytes(),"hybrid ingress frame capacity");for(uint32_t i=0;i<node->GetNDevices();++i){auto p=DynamicCast<UbPort>(node->GetDevice(i));UintegerValue cap;p->GetUbQueue()->GetAttribute("MaxEgressBytes",cap);auto fc=DynamicCast<UbCbfc>(p->GetFlowControl());NS_ABORT_MSG_IF(!fc||maximum>cap.Get()||int64_t((maximum+CellBytes(p)-1)/CellBytes(p))>fc->GetTxFreeCells(7),"hybrid configured envelope egress/credit capacity");}}CheckRss();}
 void CheckDrained(){if(alignHold){NS_ABORT_MSG_IF(activeHolds||holdsArmed!=holdsReleased||holdsArmed!=heldHeadsConsumed,"candidate hold lifecycle leak");for(auto&item:pairs)NS_ABORT_MSG_IF(item.second->hold.active||item.second->hold.expiry.IsPending(),"candidate live hold/event at drain");}for(auto&g:groups){NS_ABORT_MSG_IF(g.firstDone!=g.members.size()||g.completed!=g.members.size(),"hybrid incomplete logical group");for(auto&m:g.members)NS_ABORT_MSG_IF(m.firstBytes!=g.bytes||!m.complete,"hybrid incomplete member");Retire(g);NS_ABORT_MSG_IF(g.codec,"hybrid codec not safely retired");}NS_ABORT_MSG_IF(liveCodecs||pendingAssociations||pendingMembers||retainedAssociationCapacity||allocatedCodecs!=retiredCodecs,"hybrid lifecycle leak");for(auto&[key,p]:pairs)NS_ABORT_MSG_IF(!p->tp->IsSafeForExplicitDestroy(),"hybrid native TP not safely quiescent");CheckRss();}
};
inline bool Proxy::IsLimited(){if(Simulator::Now()<blockedUntil)return true;const bool limited=tp->IsEmpty()||tp->IsLimited();if(!limited&&invalidateOnce&&!invalidationScheduled){invalidationScheduled=true;Ptr<Proxy> self=this;Simulator::Schedule(NanoSeconds(1),[self]{++self->invalidatedGrants;self->blockedUntil=Simulator::Now()+NanoSeconds(9);Simulator::Schedule(NanoSeconds(9),[self]{self->blockedUntil=Simulator::Now();self->Refresh();self->port->TriggerTransmit();});});}return manager->alignHold?manager->HoldLimited(*this,limited):limited;}
inline uint32_t Proxy::GetNextPacketSize(){return manager->Size(*this);}
inline Ptr<Packet> Proxy::GetNextPacket(){NS_ABORT_MSG_IF(Simulator::Now()<blockedUntil,"hybrid stale grant committed while ineligible");return manager->Pull(*this);}
}
