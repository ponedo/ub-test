// SPDX-License-Identifier: GPL-2.0-only
// Synthetic observer-only unit test. No Simulator::Run, model calls, or schedules.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "diagnostic-recorder.h"
#include <cassert>
#include <iostream>
int main(){
 using namespace ns3;using K=UbReversalDiagnosticKind;
 reversal::Recorder r;r.enabled=true;r.criticalSource=3;r.classify=[](Ptr<const Packet>){return std::make_pair(0u,7u);};
 auto parent=Create<Packet>(128);auto first=parent->CreateFragment(0,64);auto second=parent->CreateFragment(64,64);assert(first->GetUid()==second->GetUid());
 auto emit=[&](K kind,uint64_t time,uintptr_t queue,Ptr<const Packet> packet,uint64_t depth=0,uint32_t node=64,uint32_t port=59){UbReversalDiagnosticEvent e;e.kind=kind;e.timePs=time;e.queue=queue;e.packet=packet;e.aux0=depth;e.node=node;e.port=port;r.Native(e);};
 r.PhaseStart(10);
 emit(K::QueueBind,10,111,nullptr);
 emit(K::VoqPush,11,111,first,1);emit(K::VoqPush,13,111,second,2);
 emit(K::VoqPop,17,111,first,1);emit(K::VoqPop,23,111,second,0);
 auto v=r.metrics.at({0,64,59,0});assert(v.count==2&&v.sum==16&&v.max==10);
 emit(K::EgressEnqueue,24,222,first);emit(K::EgressEnqueue,25,222,second);
 emit(K::EgressSend,29,222,first);emit(K::EgressSend,35,222,second);
 auto e=r.metrics.at({3,64,59,0});assert(e.count==2&&e.sum==15&&e.max==10);
 // FIFO instance separation: identical UID in separate VOQs must not interact.
 emit(K::VoqPush,36,111,first,1);emit(K::VoqPush,37,333,second,1);
 emit(K::VoqPop,39,333,second,0);emit(K::VoqPop,40,111,first,0);
 // Retain switch resource starts even when criticalSource is 3.
 emit(K::TxStart,40,222,first);assert(r.tail.back().kind==uint32_t(K::TxStart));
 emit(K::GrantStart,41,111,nullptr,4);assert(r.tail.back().kind==uint32_t(K::GrantStart));
 emit(K::GrantRejected,45,111,nullptr);emit(K::GrantStart,46,111,nullptr,3);emit(K::GrantNoIngress,49,0,nullptr);
 assert(r.metrics.at({8,64,59,2}).sum==4&&r.metrics.at({9,64,59,2}).sum==3);
 r.PhaseEnd(50);auto row=r.activity.at({64,59});assert(row.tx+row.allocationOnly+row.idle==40);assert(row.allocationOnly==7);
 const auto rows=r.activity.size();emit(K::GrantStart,60,444,nullptr,3,27,0);emit(K::GrantNoIngress,63,0,nullptr,0,27,0);assert(r.activity.size()==rows);assert(r.activity.at({64,59}).cursor==50);
 assert(r.grantStarts.empty()&&r.grantUnmatched==0&&r.grantStartOverwrites==0);
 assert(r.queueObservationCount==0&&r.queueObservations.empty());assert(r.queueUnmatched==0&&r.queueOrderErrors==0&&r.queueDepthErrors==0&&!r.incomplete);
 for(auto&[key,stat]:r.metrics)assert(std::get<0>(key)<1000);
 // Negative controls must flag incomplete, not invent residence.
 reversal::Recorder bad;bad.enabled=true;bool rejected=false;try{bad.QueuePop(1,0,1,10,0,0,0);}catch(const std::runtime_error&){rejected=true;}assert(rejected&&bad.incomplete&&bad.queueUnmatched==1);
 reversal::Recorder wrong;wrong.enabled=true;wrong.QueuePush(1,0,10,1,0,1);rejected=false;try{wrong.QueuePop(1,0,11,2,0,0,0);}catch(const std::runtime_error&){rejected=true;}assert(rejected&&wrong.incomplete&&wrong.queueOrderErrors==1);
 std::cout<<"PASS duplicate UID VOQ and egress FIFO residence; independent queues; zero unmatched/open records; fail-closed negative controls; phase boundary; selected resource GrantStart/TxStart; exact rejection/no-ingress grant intervals\n";
}
