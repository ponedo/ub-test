// Passive controlled-ablation extension, included inside Recorder.
// Physical RTT = first successful source TxStart -> accepted Jetty TAACK.
// Each source packet instance is bound to the native TAs already popped while constructing
// that exact frame. UID is a consistency check, not a key. This observer association
// never participates in forwarding.
using JettyKey=std::pair<uint32_t,uint32_t>; // source, Jetty ID
using TaKey=std::tuple<uint32_t,uint32_t,uint32_t>; // source, Jetty ID, full SSN
struct JettyObservation {
 uint32_t source=0,target=0,id=0,window=0,nxt=0,una=0,peak=0;
 uint64_t first=0,last=0,events=0,admissions=0,tests=0,limited=0,acks=0,rejected=0,duplicates=0,progress=0,cleanups=0;
 uint64_t fullIntervals=0,fullMaxPs=0,fullBegin=0;bool fullOpen=false;
 uint64_t observedPs=0,occupancyPs=0,saturatedPs=0,weightPs=0,weightOccupancyPs=0,weightSaturatedPs=0;
 std::array<uint64_t,6> histogram{},weightHistogram{};
 Stat admissionAck,nativePopAck,sourceTxAck,weightAdmissionAck;
 uint64_t weightAcks=0,weightMissingTx=0,weightMissingPop=0;
};
struct TaObservation {uint64_t admission=0,pop=0,tx=0;uint32_t task=UINT32_MAX;bool weight=false;};
std::map<JettyKey,JettyObservation> jettyObservations;
std::map<TaKey,TaObservation> pendingTas;
std::map<std::tuple<uint32_t,uint32_t,uint16_t>,TaKey> wireTas;
std::map<TaKey,uint64_t> ackedOutOfOrder;
std::map<uint32_t,std::pair<TaKey,uint64_t>> lastPoppedTask;
struct SourceFrame {Ptr<const Packet> packet;uint64_t uid;std::vector<TaKey> tas;};
std::map<std::pair<uint32_t,uintptr_t>,SourceFrame> sourceFrames;
std::function<bool(Ptr<const Packet>,uint32_t&,uint32_t&,uint32_t&)> taPacketIdentity;
struct JettyTail {uint64_t time;uint32_t kind,source,target,jetty,nxt,una,window,ssn,task,reason;};
std::deque<JettyTail> jettyTail,jettyWeightTail;
struct TaRttSample {uint32_t source,target,jetty,ssn,task;uint64_t admission,pop,tx,ack;};
std::deque<TaRttSample> taRttTail;uint64_t taRttTailOverwrites=0;
uint64_t jettyTailOverwrites=0,jettyOccupancyErrors=0,jettyUnmatchedAcks=0,jettyPendingPeak=0,jettyFramesPeak=0;
static constexpr size_t maxJetties=8192,maxPendingTas=131072,maxSourceFrames=8192;
void JettyFail(uint64_t&counter,const char*why){++counter;incomplete=true;throw std::runtime_error(why);}
static uint32_t OccupancyBin(uint32_t occupied,uint32_t window){if(!occupied)return 0;if(occupied>=window)return 5;return 1+std::min(3u,uint32_t(uint64_t(occupied)*4/window));}
void AdvanceJetty(JettyObservation&j,uint64_t now){
 if(now<j.last)JettyFail(jettyOccupancyErrors,"Jetty observer time reversed");
 const uint64_t dt=now-j.last,occupied=uint32_t(j.nxt-j.una);const auto bin=OccupancyBin(occupied,j.window);
 if(j.fullOpen)j.fullMaxPs=std::max(j.fullMaxPs,now-j.fullBegin);
 j.observedPs+=dt;j.occupancyPs+=occupied*dt;j.histogram[bin]+=dt;if(occupied>=j.window)j.saturatedPs+=dt;
 if(phase){j.weightPs+=dt;j.weightOccupancyPs+=occupied*dt;j.weightHistogram[bin]+=dt;if(occupied>=j.window)j.weightSaturatedPs+=dt;}j.last=now;
}
void AdvanceJetties(uint64_t now){for(auto&[key,j]:jettyObservations)AdvanceJetty(j,now);}
void ObserveJettyEvent(const UbReversalDiagnosticEvent&e){
 using K=UbReversalDiagnosticKind;const JettyKey key{e.node,e.tp};auto it=jettyObservations.find(key);
 if(it==jettyObservations.end()){Bound(jettyObservations.size(),maxJetties);JettyObservation j;j.source=e.node;j.target=e.port;j.id=e.tp;j.window=e.aux2;j.nxt=e.aux0;j.una=e.aux1;j.first=j.last=e.timePs;it=jettyObservations.emplace(key,j).first;}
 auto&j=it->second;AdvanceJetty(j,e.timePs);
 const uint32_t oldUna=j.una;j.nxt=e.aux0;j.una=e.aux1;
 if(!j.window||j.window!=e.aux2||j.target!=e.port||j.nxt<j.una||uint32_t(j.nxt-j.una)>j.window)JettyFail(jettyOccupancyErrors,"Jetty actual SSN occupancy/window invariant");
 const bool full=uint32_t(j.nxt-j.una)>=j.window;if(full&&!j.fullOpen){j.fullOpen=true;j.fullBegin=e.timePs;++j.fullIntervals;}else if(!full)j.fullOpen=false;
 j.peak=std::max(j.peak,uint32_t(j.nxt-j.una));++j.events;
 const bool selected=Selected(e.node,e.port)&&(selectedNodes.empty()||selectedNodes.count(e.node));
 if(e.kind==K::JettyWindowTest){++j.tests;if(e.reason==UbReversalDiagnosticReason::Inflight)++j.limited;}
 if(e.kind==K::JettyAdmission){++j.admissions;if(selected){
   TaKey ta{e.node,e.tp,uint32_t(e.aux3)};Bound(pendingTas.size(),maxPendingTas);const bool weight=tasks.count(e.task);
   if(!pendingTas.emplace(ta,TaObservation{uint64_t(e.timePs),0,0,e.task,weight}).second||!wireTas.emplace(std::make_tuple(e.node,e.tp,uint16_t(e.aux3)),ta).second)JettyFail(jettyOccupancyErrors,"Jetty duplicate live TA/16-bit SSN alias");jettyPendingPeak=std::max(jettyPendingPeak,uint64_t(pendingTas.size()));}}
 if(e.kind==K::JettyTaAckRejected)++j.rejected;
 if(e.kind==K::JettyTaAckAfter){++j.acks;j.progress+=uint32_t(j.una-oldUna);if(selected){
   TaKey ta{e.node,e.tp,uint32_t(e.aux3)};auto pending=pendingTas.find(ta);
   if(pending==pendingTas.end()){if(ackedOutOfOrder.count(ta))++j.duplicates;else JettyFail(jettyUnmatchedAcks,"Jetty accepted TAACK without admitted TA");}
   else {const auto x=pending->second;j.admissionAck.Add(e.timePs-x.admission);if(x.weight){++j.weightAcks;j.weightAdmissionAck.Add(e.timePs-x.admission);if(x.pop)j.nativePopAck.Add(e.timePs-x.pop);else ++j.weightMissingPop;if(x.tx)j.sourceTxAck.Add(e.timePs-x.tx);else ++j.weightMissingTx;
     if(taRttTail.size()==maxTail){taRttTail.pop_front();++taRttTailOverwrites;}taRttTail.push_back({e.node,e.port,e.tp,uint32_t(e.aux3),x.task,x.admission,x.pop,x.tx,uint64_t(e.timePs)});}
     pendingTas.erase(pending);wireTas.erase({e.node,e.tp,uint16_t(e.aux3)});if(uint32_t(e.aux3)>=j.una){Bound(ackedOutOfOrder.size(),maxPendingTas);ackedOutOfOrder[ta]=e.timePs;}}
   auto low=ackedOutOfOrder.lower_bound({e.node,e.tp,0});while(low!=ackedOutOfOrder.end()&&std::get<0>(low->first)==e.node&&std::get<1>(low->first)==e.tp&&std::get<2>(low->first)<j.una)low=ackedOutOfOrder.erase(low);
 }}
 if(e.kind==K::JettyCleanup){++j.cleanups;/* Cancellation is not successful ACK evidence. */if(selected)incomplete=true;}
 if(selected){if(jettyTail.size()==maxTail){jettyTail.pop_front();++jettyTailOverwrites;}jettyTail.push_back({uint64_t(e.timePs),uint32_t(e.kind),e.node,e.port,e.tp,uint32_t(e.aux0),uint32_t(e.aux1),uint32_t(e.aux2),uint32_t(e.aux3),e.task,uint32_t(e.reason)});}
}
void ObserveTaPacket(const UbReversalDiagnosticEvent&e){
 using K=UbReversalDiagnosticKind;if(!e.packet||(e.kind!=K::TpPop&&e.kind!=K::TxStart))return;
 if(e.kind==K::TxStart){auto frame=sourceFrames.find({e.node,reinterpret_cast<uintptr_t>(PeekPointer(e.packet))});if(frame!=sourceFrames.end()){
   if(frame->second.uid!=e.packet->GetUid())JettyFail(jettyOccupancyErrors,"source frame identity/UID changed");
   for(auto&key:frame->second.tas){if(std::get<0>(key)!=e.node)continue;auto it=pendingTas.find(key);if(it!=pendingTas.end()&&!it->second.tx)it->second.tx=e.timePs;}
   sourceFrames.erase(frame);return;
 }}
 if((criticalSource!=UINT32_MAX&&e.node!=criticalSource)||(!selectedNodes.empty()&&!selectedNodes.count(e.node))||!taPacketIdentity)return;uint32_t task,jetty,ssn;if(!taPacketIdentity(e.packet,task,jetty,ssn))return;
 auto t=tasks.find(task);if(t==tasks.end()||t->second.source!=e.node)return;
 auto wire=wireTas.find({e.node,jetty,uint16_t(ssn)});if(wire==wireTas.end())return;auto it=pendingTas.find(wire->second);if(it==pendingTas.end())return;
 if(e.kind==K::TpPop){if(!it->second.pop)it->second.pop=e.timePs;if(!lastPoppedTask.count(task))Bound(lastPoppedTask.size(),maxTasks);lastPoppedTask[task]={it->first,uint64_t(e.timePs)};}
 else if(!it->second.tx)it->second.tx=e.timePs;
}
void BindSourceFrame(Ptr<const Packet> packet,uint32_t source,const std::vector<uint32_t>&memberTasks,uint64_t now){
 if(!enabled)return;std::vector<TaKey> bound;for(auto task:memberTasks){auto it=lastPoppedTask.find(task);if(it!=lastPoppedTask.end()&&it->second.second==now&&std::get<0>(it->second.first)==source)bound.push_back(it->second.first);}
 if(bound.empty())return;Bound(sourceFrames.size(),maxSourceFrames);if(!sourceFrames.emplace(std::make_pair(source,reinterpret_cast<uintptr_t>(PeekPointer(packet))),SourceFrame{packet,packet->GetUid(),std::move(bound)}).second)JettyFail(jettyOccupancyErrors,"duplicate live source envelope instance");jettyFramesPeak=std::max(jettyFramesPeak,uint64_t(sourceFrames.size()));
}
void WriteJetties(const std::string&out,uint64_t now){
 AdvanceJetties(now);uint64_t nonzero=0,ackMarks=ackedOutOfOrder.size();for(auto&[key,j]:jettyObservations){if(j.nxt!=j.una)++nonzero;if(j.weightMissingTx||j.weightMissingPop||j.weightAcks!=j.sourceTxAck.count||j.weightAcks!=j.nativePopAck.count)incomplete=true;}
 if(nonzero||!pendingTas.empty()||ackMarks||!sourceFrames.empty())incomplete=true;
 std::ofstream f(out+"/diagnostic-jetty-aggregates.csv");
 f<<"source,target,jetty,window,first_observation_ps,last_observation_ps,ssn_next,ssn_una,terminal_outstanding,max_outstanding,events,admissions,window_tests,window_limited_tests,accepted_taacks,rejected_taacks,duplicate_taacks,ssn_progress,cleanup_events,observed_ps,outstanding_ta_ps,window_saturated_ps,weight_phase_observed_ps,weight_phase_outstanding_ta_ps,weight_phase_window_saturated_ps,admission_to_ack_count,admission_to_ack_sum_ps,admission_to_ack_max_ps,weight_admission_to_ack_count,weight_admission_to_ack_sum_ps,weight_admission_to_ack_max_ps,weight_native_pop_to_ack_count,weight_native_pop_to_ack_sum_ps,weight_native_pop_to_ack_max_ps,weight_source_tx_to_ack_count,weight_source_tx_to_ack_sum_ps,weight_source_tx_to_ack_max_ps,weight_ack_without_source_tx,weight_ack_without_native_pop,window_full_intervals,max_window_full_interval_ps\n";
 for(auto&[key,j]:jettyObservations)f<<j.source<<','<<j.target<<','<<j.id<<','<<j.window<<','<<j.first<<','<<j.last<<','<<j.nxt<<','<<j.una<<','<<uint32_t(j.nxt-j.una)<<','<<j.peak<<','<<j.events<<','<<j.admissions<<','<<j.tests<<','<<j.limited<<','<<j.acks<<','<<j.rejected<<','<<j.duplicates<<','<<j.progress<<','<<j.cleanups<<','<<j.observedPs<<','<<j.occupancyPs<<','<<j.saturatedPs<<','<<j.weightPs<<','<<j.weightOccupancyPs<<','<<j.weightSaturatedPs<<','<<j.admissionAck.count<<','<<j.admissionAck.sum<<','<<j.admissionAck.max<<','<<j.weightAdmissionAck.count<<','<<j.weightAdmissionAck.sum<<','<<j.weightAdmissionAck.max<<','<<j.nativePopAck.count<<','<<j.nativePopAck.sum<<','<<j.nativePopAck.max<<','<<j.sourceTxAck.count<<','<<j.sourceTxAck.sum<<','<<j.sourceTxAck.max<<','<<j.weightMissingTx<<','<<j.weightMissingPop<<','<<j.fullIntervals<<','<<j.fullMaxPs<<'\n';
 std::ofstream h(out+"/diagnostic-jetty-occupancy.csv");h<<"source,target,jetty,window,bin,all_observed_ps,weight_phase_ps\n";for(auto&[key,j]:jettyObservations)for(uint32_t b=0;b<6;++b)h<<j.source<<','<<j.target<<','<<j.id<<','<<j.window<<','<<b<<','<<j.histogram[b]<<','<<j.weightHistogram[b]<<'\n';
 std::ofstream t(out+"/diagnostic-jetty-tail.csv");t<<"time_ps,kind,source,target,jetty,ssn_next,ssn_una,window,ssn,task,reason\n";for(auto&x:jettyTail)t<<x.time<<','<<x.kind<<','<<x.source<<','<<x.target<<','<<x.jetty<<','<<x.nxt<<','<<x.una<<','<<x.window<<','<<x.ssn<<','<<x.task<<','<<x.reason<<'\n';
 std::ofstream wt(out+"/diagnostic-jetty-weight-tail.csv");wt<<"time_ps,kind,source,target,jetty,ssn_next,ssn_una,window,ssn,task,reason\n";for(auto&x:jettyWeightTail)wt<<x.time<<','<<x.kind<<','<<x.source<<','<<x.target<<','<<x.jetty<<','<<x.nxt<<','<<x.una<<','<<x.window<<','<<x.ssn<<','<<x.task<<','<<x.reason<<'\n';
 std::ofstream rt(out+"/diagnostic-ta-rtt-tail.csv");rt<<"source,target,jetty,ssn,task,admission_ps,first_native_pop_ps,first_source_tx_ps,accepted_taack_ps\n";for(auto&x:taRttTail)rt<<x.source<<','<<x.target<<','<<x.jetty<<','<<x.ssn<<','<<x.task<<','<<x.admission<<','<<x.pop<<','<<x.tx<<','<<x.ack<<'\n';
 std::ofstream s(out+"/diagnostic-jetty-status.json");s<<"{\"incomplete\":"<<(incomplete?"true":"false")<<",\"tracked_jetties\":"<<jettyObservations.size()<<",\"terminal_nonzero_jetties\":"<<nonzero<<",\"pending_ta_observations\":"<<pendingTas.size()<<",\"pending_ta_peak\":"<<jettyPendingPeak<<",\"pending_source_frames\":"<<sourceFrames.size()<<",\"source_frames_peak\":"<<jettyFramesPeak<<",\"pending_ack_marks\":"<<ackMarks<<",\"occupancy_errors\":"<<jettyOccupancyErrors<<",\"unmatched_accepted_taacks\":"<<jettyUnmatchedAcks<<",\"tail_overwrites\":"<<jettyTailOverwrites<<",\"rtt_tail_overwrites\":"<<taRttTailOverwrites<<",\"max_jetties\":"<<maxJetties<<",\"max_pending_tas\":"<<maxPendingTas<<",\"max_source_frames\":"<<maxSourceFrames<<",\"max_tail\":"<<maxTail<<",\"latency_semantics\":\"First source TxStart to accepted TAACK includes downstream network, receiver execution and return path; admission and native-pop boundaries are reported separately. Native-pop is not physical TX. RTT samples are selected weight TAs only, all-pair occupancy is global.\",\"occupancy_bin_semantics\":\"0 empty;1 (0,25%);2 [25%,50%);3 [50%,75%);4 [75%,100%);5 >=100%. Exact transition integration, no polling.\"}\n";
}
