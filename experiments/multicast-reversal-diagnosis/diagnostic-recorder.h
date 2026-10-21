// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "ns3/ub-reversal-diagnostic.h"
#include <map>
#include <algorithm>
#include <cstdint>
#include <string>
#include <set>
#include <sstream>
#include <vector>
#include <deque>
#include <tuple>
#include <fstream>
#include <functional>
#include <stdexcept>
namespace reversal {
using namespace ns3;
enum Reason : uint32_t {Ready=0,NotStarted,Drained,Ack,Cnp,Retry,Empty,Limited,NoSegment,WrongKind,WrongTask,NonRepresentative,LimitedInflight,LimitedCc};
inline const char* ReasonName(uint32_t r){static const char* names[]={"ready","not_started","drained","ack","cnp","retry","empty","limited_existing_native_result","no_segment","wrong_segment_kind","wrong_task","non_representative","limited_inflight","limited_cc"};return r<14?names[r]:"unknown";}
struct Recorder {
 static inline Recorder* active=nullptr;
 std::string nodeFilter;std::set<uint32_t> selectedNodes;
 bool enabled=false,incomplete=false; uint32_t criticalSource=UINT32_MAX,criticalTarget=UINT32_MAX,criticalGroup=UINT32_MAX;
 static constexpr size_t maxTasks=65536,maxEntries=131072,maxTail=65536;
 uint64_t events=0,tailOverwrites=0;uint64_t lastWeightPs=0;uint32_t lastWeightPhysical=UINT32_MAX;
 struct Task {uint32_t source,target,physical,expert,bytes,offset;uint64_t submit=0,firstSend=0,lastSend=0,received=0,ready=0,sender=0;};
 std::map<uint32_t,Task> tasks;
 struct Group {uint64_t first=0,last=0,grants=0,lastQuery=0;uint32_t reason=Ready,member=UINT32_MAX;bool queried=false;};
 std::map<uint32_t,Group> groups;
 struct Stat {uint64_t count=0,sum=0,max=0;void Add(uint64_t v){++count;sum+=v;if(v>max)max=v;}};
 std::map<std::tuple<uint32_t,uint32_t,uint32_t>,Stat> polls;
 // Actual AllReady evaluations, distinct from coalesced observation spans.
 std::map<std::tuple<uint32_t,uint32_t,uint32_t>,uint64_t> queryCounts;
 struct Tail {uint64_t time,uid,parent,a,b;uint32_t kind,node,port,task,group,seq;uint32_t tp=UINT32_MAX;uint64_t queue=0,aux2=0,aux3=0;uint32_t reason=0;};
 std::deque<Tail> tail,weightTail;
 struct Corr {uint64_t parent;uint32_t group,seq;};std::map<uint64_t,Corr> correlations;
 using Key=std::tuple<uintptr_t,uint64_t,uint32_t>;
 std::map<Key,uint64_t> starts; // allocation observations only, not packet identities
 struct QueueObservation {uint64_t time,uid;uint32_t trafficClass;};
 using FifoKey=std::pair<uintptr_t,uint32_t>;
 std::map<FifoKey,std::deque<QueueObservation>> queueObservations;
 uint64_t queueObservationCount=0,queueObservationPeak=0,queueUnmatched=0,queueOrderErrors=0,queueDepthErrors=0;
 static constexpr size_t maxObservedQueues=8192;
 std::map<std::pair<uint32_t,uint32_t>,uint64_t> grantStarts;
 uint64_t grantUnmatched=0,grantStartOverwrites=0;
 std::map<uintptr_t,std::pair<uint32_t,uint32_t>> locations;
 std::map<uintptr_t,uint32_t> limitedReasons;
 uint32_t LimitedReason(uintptr_t queue)const{auto it=limitedReasons.find(queue);return it==limitedReasons.end()?Limited:it->second;}
 // metric,node,port,traffic class; sums are packet-time, never wall-time attribution.
 std::map<std::tuple<uint32_t,uint32_t,uint32_t,uint32_t>,Stat> metrics,weightPhaseCohorts;
 struct Activity {uint64_t cursor=0,txUntil=0,allocationUntil=0,tx=0,allocationOnly=0,idle=0;};
 std::map<std::pair<uint32_t,uint32_t>,Activity> activity,lastSendActivity;std::map<uint32_t,uint64_t> sourceLastSend;bool phase=false;uint64_t phaseBegin=0,phaseFinish=0;
 void Advance(Activity&a,uint64_t now){if(!phase)return;while(a.cursor<now){uint64_t end=now;if(a.txUntil>a.cursor)end=std::min(end,a.txUntil);if(a.allocationUntil>a.cursor)end=std::min(end,a.allocationUntil);auto dt=end-a.cursor;if(a.txUntil>a.cursor)a.tx+=dt;else if(a.allocationUntil>a.cursor)a.allocationOnly+=dt;else a.idle+=dt;a.cursor=end;}}
 void PhaseStart(uint64_t now){if(!enabled)return;phase=true;phaseBegin=now;for(auto&[k,a]:activity)a.cursor=now;}
 void PhaseEnd(uint64_t now){if(!enabled)return;for(auto&[k,a]:activity)Advance(a,now);phase=false;phaseFinish=now;weightTail=tail;}
 std::function<std::pair<uint32_t,uint32_t>(Ptr<const Packet>)> classify;
 void Bound(size_t n,size_t cap){if(n>=cap){incomplete=true;throw std::runtime_error("diagnostic hard cap exceeded; incomplete evidence");}}
 void AddTail(Tail x){if(tail.size()==maxTail){tail.pop_front();++tailOverwrites;}tail.push_back(x);}
 bool Selected(uint32_t source,uint32_t target,uint32_t group=UINT32_MAX)const{return (criticalSource==UINT32_MAX||source==criticalSource)&&(criticalTarget==UINT32_MAX||target==criticalTarget)&&(criticalGroup==UINT32_MAX||group==UINT32_MAX||group==criticalGroup);}
 void Register(uint32_t id,uint32_t source,uint32_t target,uint32_t physical,uint32_t expert,uint32_t bytes,uint32_t offset){if(!enabled)return;Bound(tasks.size(),maxTasks);tasks.emplace(id,Task{source,target,physical,expert,bytes,offset});}
 void App(uint32_t task,uint32_t kind,uint64_t now){if(!enabled)return;auto i=tasks.find(task);if(i==tasks.end())return;auto&x=i->second;switch(kind){case 100:x.submit=now;break;case 101:if(!x.firstSend)x.firstSend=now;x.lastSend=now;break;case 102:x.received=now;break;case 103:x.ready=now;break;case 104:x.sender=now;break;}if(Selected(x.source,x.target))AddTail({now,0,0,0,0,kind,x.source,x.target,task,UINT32_MAX,0});}
 void Weight(uint32_t physical,uint64_t now){if(enabled){lastWeightPs=now;lastWeightPhysical=physical;AddTail({now,0,0,physical,0,105,UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX,0});}}
 void Close(uint32_t group,uint64_t now){if(!enabled)return;auto it=groups.find(group);if(it!=groups.end()&&it->second.queried){auto&g=it->second;auto k=std::make_tuple(group,g.member,g.reason);if(!polls.count(k))Bound(polls.size(),maxEntries);polls[k].Add(now-g.lastQuery);g.queried=false;}}
 void Query(uint32_t group,uint32_t source,uint32_t member,uint32_t reason,uint64_t now){if(!enabled)return;auto observedKey=std::make_tuple(group,member,reason);if(!queryCounts.count(observedKey))Bound(queryCounts.size(),maxEntries);++queryCounts[observedKey];if(reason==Drained)return;if(!groups.count(group))Bound(groups.size(),1024);auto&g=groups[group];if(g.queried&&g.reason==reason&&g.member==member)return;if(g.queried){auto key=std::make_tuple(group,g.member,g.reason);if(!polls.count(key))Bound(polls.size(),maxEntries);polls[key].Add(now-g.lastQuery);}g.queried=true;g.lastQuery=now;g.reason=reason;g.member=member;if(Selected(source,member,group))AddTail({now,0,0,reason,0,106,source,member,UINT32_MAX,group,0});}
 void Grant(uint32_t group,uint32_t source,uint64_t now,uint32_t seq){if(!enabled)return;if(!groups.count(group))Bound(groups.size(),1024);auto&g=groups[group];if(!g.grants)g.first=now;g.last=now;++g.grants;if(criticalGroup==UINT32_MAX||group==criticalGroup)AddTail({now,0,0,0,0,107,source,UINT32_MAX,UINT32_MAX,group,seq});}
 void Metric(uint32_t kind,uint32_t node,uint32_t port,uint32_t cls,uint64_t duration){auto k=std::make_tuple(kind,node,port,cls);if(!metrics.count(k))Bound(metrics.size(),maxEntries);metrics[k].Add(duration);if(phase){if(!weightPhaseCohorts.count(k))Bound(weightPhaseCohorts.size(),maxEntries);weightPhaseCohorts[k].Add(duration);}}
 void Start(Key k,uint64_t now){if(std::get<2>(k)==1&&starts.count(k))return;if(!starts.count(k))Bound(starts.size(),maxEntries);starts[k]=now;}
 void End(Key k,uint64_t now,uint32_t kind,uint32_t node,uint32_t port,uint32_t cls){auto i=starts.find(k);if(i!=starts.end()){Metric(kind,node,port,cls,now-i->second);starts.erase(i);}else Metric(kind+1000,node,port,cls,0);}
 void QueueFailure(uint64_t& counter,const char* message){++counter;incomplete=true;throw std::runtime_error(message);}
 void QueuePush(uintptr_t queue,uint32_t kind,uint64_t uid,uint64_t now,uint32_t cls,uint64_t postDepth=UINT64_MAX){
  auto key=std::make_pair(queue,kind);if(!queueObservations.count(key))Bound(queueObservations.size(),maxObservedQueues);Bound(queueObservationCount,maxEntries);
  auto&q=queueObservations[key];q.push_back({now,uid,cls});++queueObservationCount;queueObservationPeak=std::max(queueObservationPeak,queueObservationCount);
  if(postDepth!=UINT64_MAX&&q.size()!=postDepth)QueueFailure(queueDepthErrors,"diagnostic FIFO push depth mismatch");
 }
 void QueuePop(uintptr_t queue,uint32_t kind,uint64_t uid,uint64_t now,uint32_t node,uint32_t port,uint64_t postDepth=UINT64_MAX){
  auto it=queueObservations.find({queue,kind});if(it==queueObservations.end()||it->second.empty())QueueFailure(queueUnmatched,"diagnostic FIFO unmatched pop");
  auto&q=it->second;const auto front=q.front();if(front.uid!=uid||now<front.time)QueueFailure(queueOrderErrors,"diagnostic FIFO order/time mismatch");
  q.pop_front();--queueObservationCount;if(postDepth!=UINT64_MAX&&q.size()!=postDepth)QueueFailure(queueDepthErrors,"diagnostic FIFO pop depth mismatch");
  Metric(kind,node,port,front.trafficClass,now-front.time);if(q.empty())queueObservations.erase(it);
 }
 void GrantStarted(uint32_t node,uint32_t port,uint64_t now){auto key=std::make_pair(node,port);if(grantStarts.count(key))QueueFailure(grantStartOverwrites,"diagnostic allocation start overwritten");Bound(grantStarts.size(),4096);grantStarts[key]=now;}
 void GrantEnded(uint32_t node,uint32_t port,uint64_t now,uint32_t metric,uint32_t cls){auto it=grantStarts.find({node,port});if(it==grantStarts.end()||now<it->second)QueueFailure(grantUnmatched,"diagnostic unmatched allocation outcome");Metric(metric,node,port,cls,now-it->second);grantStarts.erase(it);}
 static void Sink(const UbReversalDiagnosticEvent&e){if(active)active->Native(e);}
 void Native(const UbReversalDiagnosticEvent&e){if(!enabled)return;++events;using K=UbReversalDiagnosticKind;uint64_t now=e.timePs,uid=e.packet?e.packet->GetUid():UINT64_MAX;uint32_t node=e.node,port=e.port;
  if(e.kind==K::AllocSelect||e.kind==K::QueueBind){if(!locations.count(e.queue))Bound(locations.size(),maxEntries);locations[e.queue]={node,port};}
  if(node==UINT32_MAX&&locations.count(e.queue)){node=locations[e.queue].first;port=locations[e.queue].second;}
  if(e.kind==K::TpLimited){if(!limitedReasons.count(e.queue))Bound(limitedReasons.size(),maxEntries);limitedReasons[e.queue]=e.reason==UbReversalDiagnosticReason::Inflight?LimitedInflight:e.reason==UbReversalDiagnosticReason::Cc?LimitedCc:Limited;}
  const bool selectedNode=selectedNodes.empty()||selectedNodes.count(node);
  if(!selectedNode&&e.kind!=K::TpPop){if(e.kind==K::Rx&&e.packet){UbFlowTag tag;if(e.packet->PeekPacketTag(tag)){auto ti=tasks.find(tag.GetFlowId());if(ti!=tasks.end()&&ti->second.target==node)correlations.erase(uid);}}return;}
  bool wire=e.kind==K::VoqPush||e.kind==K::VoqPop||e.kind==K::GrantCommit||e.kind==K::EgressEnqueue||e.kind==K::EgressSend||e.kind==K::TxStart||e.kind==K::Rx||e.kind==K::EnvelopeDecode||e.kind==K::NativeBranch||e.kind==K::TpPop;
  auto c=e.packet&&classify&&wire?classify(e.packet):std::make_pair(2u,UINT32_MAX);if(e.packet&&!wire){UbFlowTag tag;if(e.packet->PeekPacketTag(tag))c.second=tag.GetFlowId();}uint32_t cls=c.first,task=c.second;
  if(!selectedNode){if(e.kind==K::TpPop&&cls==0)App(task,101,now);return;}
  if(node!=UINT32_MAX&&port!=UINT32_MAX&&(phase||phaseFinish==0)){
   auto key=std::make_pair(node,port);if(!activity.count(key)){Bound(activity.size(),4096);activity[key].cursor=phaseBegin;}auto&a=activity[key];Advance(a,now);
   if(e.kind==K::TxStart&&e.aux3!=1)a.txUntil=std::max(a.txUntil,now+e.aux1);
   if(e.kind==K::GrantStart)a.allocationUntil=std::max(a.allocationUntil,now+e.aux0);
  }
  if(e.kind==K::TpLimited)Metric(200+uint32_t(e.reason),node,port,2,0);
  if(e.kind==K::NativeBranch){if(!correlations.count(uid))Bound(correlations.size(),maxEntries);correlations[uid]={e.aux0,uint32_t(e.aux1),uint32_t(e.aux2)};}
  switch(e.kind){
   case K::VoqPush:QueuePush(e.queue,0,uid,now,cls,e.aux0);break;
   case K::VoqPop:QueuePop(e.queue,0,uid,now,node,port,e.aux0);break;
   case K::AllocSelect:Start({e.queue,0,1},now);break;
   case K::GrantCommit:End({e.queue,0,1},now,1,node,port,cls);GrantEnded(node,port,now,10,cls);break;
   case K::GrantStart:GrantStarted(node,port,now);Metric(2,node,port,cls,e.aux0);break;
   case K::GrantRejected:GrantEnded(node,port,now,8,2);break;
   case K::GrantNoIngress:GrantEnded(node,port,now,9,2);break;
   case K::EgressEnqueue:QueuePush(e.queue,3,uid,now,cls);break;
   case K::EgressSend:QueuePop(e.queue,3,uid,now,node,port);break;
   case K::TxStart:Metric(4,node,port,cls,e.aux0-e.aux2);Metric(7,node,port,cls,e.aux2);Metric(5,node,port,cls,e.packet?e.packet->GetSize():0);break;
   case K::Rx:Metric(6,node,port,cls,e.packet?e.packet->GetSize():0);break;
   case K::TpPop:if(cls==0){App(task,101,now);if(node!=UINT32_MAX){sourceLastSend[node]=now;for(auto&[key,a]:activity)if(key.first==node){Advance(a,now);lastSendActivity[key]=a;}}}break;
   default:break;
  }
  Corr corr{0,UINT32_MAX,0};auto ci=correlations.find(uid);if(ci!=correlations.end())corr=ci->second;
  bool selected=(criticalSource!=UINT32_MAX&&node==criticalSource&&!e.packet);auto ti=tasks.find(task);if(ti!=tasks.end())selected=selected||Selected(ti->second.source,ti->second.target,corr.group);if(corr.group!=UINT32_MAX&&criticalGroup==corr.group)selected=true;
  // An envelope has no member task tag. Retain its physical path by UID;
  // the existing decode event supplies operation/sequence, and NativeBranch
  // carries this same parent UID. No extra decode or packet copy is needed.
  if(cls==0&&task==UINT32_MAX)selected=true;
  if((e.kind==K::GrantStart||e.kind==K::TxStart||e.kind==K::GrantRejected||e.kind==K::GrantNoIngress)&&phase&&selectedNode)selected=true;
  if(e.kind==K::EnvelopeDecode){corr.group=uint32_t(e.aux0);corr.seq=uint32_t(e.aux1);if(criticalGroup==UINT32_MAX||criticalGroup==corr.group)selected=true;}
  if(selected)AddTail({now,uid,corr.parent,e.aux0,e.aux1,uint32_t(e.kind),node,port,task,corr.group,corr.seq,e.tp,uint64_t(e.queue),e.aux2,e.aux3,uint32_t(e.reason)});
  // Branch packets terminate at RX. Correlation is emitted in tail before release.
  if(e.kind==K::Rx&&ci!=correlations.end()&&ti!=tasks.end()&&node==ti->second.target)correlations.erase(ci);
 }
 void Enable(){if(enabled){if(!nodeFilter.empty()){std::istringstream in(nodeFilter);std::string item;while(std::getline(in,item,',')){if(item.empty()||item.find_first_not_of("0123456789")!=std::string::npos)throw std::runtime_error("invalid diagnosticNodes");auto n=std::stoull(item);if(n>UINT32_MAX)throw std::runtime_error("invalid diagnostic node");selectedNodes.insert(uint32_t(n));}}active=this;UbReversalDiagnostic::SetSink(&Sink);}}
 void Disable(){if(active==this){UbReversalDiagnostic::SetSink(nullptr);active=nullptr;}}
 void Write(const std::string&out,uint64_t now){if(!enabled)return;if(queueObservationCount||queueUnmatched||queueOrderErrors||queueDepthErrors||grantUnmatched||grantStartOverwrites||!grantStarts.empty())incomplete=true;
  for(auto&[id,g]:groups)if(g.queried){auto key=std::make_tuple(id,g.member,g.reason);polls[key].Add(now-g.lastQuery);g.queried=false;}
  if(phase)PhaseEnd(now);
  std::ofstream a(out+"/diagnostic-port-partition.csv");a<<"node,port,phase_start_ps,phase_end_ps,tx_busy_union_ps,allocator_pending_excluding_tx_ps,uncovered_idle_ps,total_ps\n";for(auto&[k,x]:activity)a<<k.first<<','<<k.second<<','<<phaseBegin<<','<<phaseFinish<<','<<x.tx<<','<<x.allocationOnly<<','<<x.idle<<','<<(x.tx+x.allocationOnly+x.idle)<<'\n';
  std::ofstream ls(out+"/diagnostic-source-last-send-partition.csv");ls<<"node,port,phase_start_ps,last_weight_native_send_ps,tx_busy_union_ps,allocator_pending_excluding_tx_ps,uncovered_idle_ps,total_ps\n";for(auto&[k,x]:lastSendActivity)ls<<k.first<<','<<k.second<<','<<phaseBegin<<','<<sourceLastSend[k.first]<<','<<x.tx<<','<<x.allocationOnly<<','<<x.idle<<','<<(x.tx+x.allocationOnly+x.idle)<<'\n';
  std::ofstream f(out+"/diagnostic-transfers.csv");f<<"task,expert,source,target,physical,offset,bytes,submit_ps,first_native_send_ps,last_native_send_ps,last_received_ps,receiver_ready_ps,sender_complete_ps\n";for(auto&[id,x]:tasks)f<<id<<','<<x.expert<<','<<x.source<<','<<x.target<<','<<x.physical<<','<<x.offset<<','<<x.bytes<<','<<x.submit<<','<<x.firstSend<<','<<x.lastSend<<','<<x.received<<','<<x.ready<<','<<x.sender<<'\n';
  std::ofstream g(out+"/diagnostic-groups.csv");g<<"group,actual_grants,first_grant_ps,last_grant_ps\n";for(auto&[id,x]:groups)g<<id<<','<<x.grants<<','<<x.first<<','<<x.last<<'\n';
  std::ofstream p(out+"/diagnostic-poll-upper-bounds.csv");p<<"group,first_failing_member,reason,actual_evaluations,observed_spans,sum_observed_span_upper_bound_ps,max_observed_span_upper_bound_ps\n";for(auto&[k,count]:queryCounts){auto it=polls.find(k);const Stat empty{};const auto&s=it==polls.end()?empty:it->second;p<<std::get<0>(k)<<','<<std::get<1>(k)<<','<<ReasonName(std::get<2>(k))<<','<<count<<','<<s.count<<','<<s.sum<<','<<s.max<<'\n';}
  std::ofstream m(out+"/diagnostic-native-aggregates.csv");m<<"metric,node,port,class,count,sum,max\n";for(auto&[k,s]:metrics)m<<std::get<0>(k)<<','<<std::get<1>(k)<<','<<std::get<2>(k)<<','<<std::get<3>(k)<<','<<s.count<<','<<s.sum<<','<<s.max<<'\n';
  // These are event cohorts, not clipped occupancy. Full residence belongs
  // to an end-in-phase cohort; full TX/grant service to a start-in-phase cohort.
  std::ofstream wc(out+"/diagnostic-weight-phase-cohorts.csv");wc<<"metric,node,port,class,cohort,count,sum,max\n";for(auto&[k,s]:weightPhaseCohorts){auto metric=std::get<0>(k);bool ended=metric==0||metric==1||metric==3||metric==8||metric==9||metric==10||metric>=1000;wc<<metric<<','<<std::get<1>(k)<<','<<std::get<2>(k)<<','<<std::get<3>(k)<<','<<(ended?"end_event_in_weight_phase_full_residence":"event_start_in_weight_phase_full_value")<<','<<s.count<<','<<s.sum<<','<<s.max<<'\n';}
  std::ofstream t(out+"/diagnostic-tail.csv");t<<"time_ps,kind,node,port,task,uid,parent_uid,group,sequence,aux0,aux1,tp,queue_identity,aux2,aux3,reason\n";for(auto&x:tail)t<<x.time<<','<<x.kind<<','<<x.node<<','<<x.port<<','<<x.task<<','<<x.uid<<','<<x.parent<<','<<x.group<<','<<x.seq<<','<<x.a<<','<<x.b<<','<<x.tp<<','<<x.queue<<','<<x.aux2<<','<<x.aux3<<','<<x.reason<<'\n';
  std::ofstream wt(out+"/diagnostic-weight-tail.csv");wt<<"time_ps,kind,node,port,task,uid,parent_uid,group,sequence,aux0,aux1,tp,queue_identity,aux2,aux3,reason\n";for(auto&x:weightTail)wt<<x.time<<','<<x.kind<<','<<x.node<<','<<x.port<<','<<x.task<<','<<x.uid<<','<<x.parent<<','<<x.group<<','<<x.seq<<','<<x.a<<','<<x.b<<','<<x.tp<<','<<x.queue<<','<<x.aux2<<','<<x.aux3<<','<<x.reason<<'\n';
  std::ofstream j(out+"/diagnostic-status.json");j<<"{\"enabled\":true,\"incomplete\":"<<(incomplete?"true":"false")<<",\"native_events\":"<<events<<",\"tail_overwrites\":"<<tailOverwrites<<",\"open_interval_keys\":"<<starts.size()<<",\"queue_observations_open\":"<<queueObservationCount<<",\"queue_observations_peak\":"<<queueObservationPeak<<",\"queue_unmatched\":"<<queueUnmatched<<",\"queue_order_errors\":"<<queueOrderErrors<<",\"queue_depth_errors\":"<<queueDepthErrors<<",\"grant_outcomes_unmatched\":"<<grantUnmatched<<",\"grant_start_overwrites\":"<<grantStartOverwrites<<",\"grant_starts_open\":"<<grantStarts.size()<<",\"last_weight_physical\":"<<lastWeightPhysical<<",\"last_weight_ready_ps\":"<<lastWeightPs<<",\"max_tasks\":"<<maxTasks<<",\"max_map_entries\":"<<maxEntries<<",\"max_tail_events\":"<<maxTail<<",\"poll_semantics\":\"observed upper bounds only; not continuous waiting and not additive across groups/reasons/ports\",\"metric_semantics\":\"0 VOQ packet residence ps;1 allocation select to commit ps;2 requested grant service ps;3 egress packet wait ps;4 TX serialization ps;5 TX bytes;6 RX bytes;7 explicit TX delay ps;8 rejected allocation elapsed ps;9 no-ingress allocation elapsed ps;10 committed allocation elapsed ps;1000+ unmatched end count. Class 0 stage2 weight,1 ACK or response,2 other. Sums are overlapping packet-times, not critical wall-clock decomposition.\"}\n";
 }
};
}
