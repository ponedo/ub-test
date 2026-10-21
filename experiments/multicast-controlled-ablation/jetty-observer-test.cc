// SPDX-License-Identifier: GPL-2.0-only
// Pure observer test: events supplied directly, no native mutation or schedules.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "diagnostic-recorder.h"
#include <cassert>
#include <filesystem>
#include <iostream>
using namespace ns3;
int main(){
 using K=UbReversalDiagnosticKind;reversal::Recorder r;r.enabled=true;r.criticalSource=0;r.criticalTarget=1;r.Register(7,0,1,0,0,1,0);r.Register(8,0,1,1,0,1,0);
 auto native0=Create<Packet>(8),native1=Create<Packet>(8);auto parent=Create<Packet>(16);auto frame0=parent->CreateFragment(0,8),frame1=parent->CreateFragment(8,8);assert(frame0->GetUid()==frame1->GetUid());
 r.taPacketIdentity=[&](Ptr<const Packet>p,uint32_t&task,uint32_t&jetty,uint32_t&ssn){jetty=9;if(p==native0){task=7;ssn=0;return true;}if(p==native1){task=8;ssn=1;return true;}return false;};
 auto jetty=[&](K kind,uint64_t time,uint32_t nxt,uint32_t una,uint32_t ssn=UINT32_MAX,uint32_t task=UINT32_MAX){UbReversalDiagnosticEvent e;e.kind=kind;e.timePs=time;e.node=0;e.port=1;e.tp=9;e.queue=123;e.aux0=nxt;e.aux1=una;e.aux2=2;e.aux3=ssn;e.task=task;e.reason=nxt-una>=2?UbReversalDiagnosticReason::Inflight:UbReversalDiagnosticReason::Eligible;r.Native(e);};
 auto packet=[&](K kind,uint64_t time,Ptr<const Packet>p){UbReversalDiagnosticEvent e;e.kind=kind;e.timePs=time;e.node=0;e.port=0;e.packet=p;r.Native(e);};
 jetty(K::JettyWindowTest,10,0,0);jetty(K::JettyAdmission,11,1,0,0,7);packet(K::TpPop,12,native0);r.BindSourceFrame(frame0,0,{7},12);packet(K::TxStart,13,frame0);
 r.PhaseStart(15);jetty(K::JettyAdmission,21,2,0,1,8);packet(K::TpPop,22,native1);r.BindSourceFrame(frame1,0,{8},22);packet(K::TxStart,23,frame1);jetty(K::JettyWindowTest,25,2,0);
 jetty(K::JettyTaAckBefore,35,2,0,1);jetty(K::JettyTaAckAfter,35,2,0,1);jetty(K::JettyTaAckBefore,36,2,0,1);jetty(K::JettyTaAckAfter,36,2,0,1);r.PhaseEnd(40);
 jetty(K::JettyTaAckBefore,45,2,0,0);jetty(K::JettyTaAckAfter,45,2,2,0);jetty(K::JettyTaAckRejected,46,2,2,0);
 r.AdvanceJetties(50);const auto&j=r.jettyObservations.at({0,9});assert(j.peak==2&&j.saturatedPs==24&&j.weightSaturatedPs==19&&j.weightOccupancyPs==44&&j.weightPs==25);assert(j.fullIntervals==1&&j.fullMaxPs==24);assert(j.admissions==2&&j.acks==3&&j.duplicates==1&&j.progress==2&&j.rejected==1);
 assert(j.sourceTxAck.count==2&&j.sourceTxAck.sum==44&&j.sourceTxAck.max==32);assert(j.nativePopAck.sum==46&&j.admissionAck.sum==48);assert(!j.weightMissingTx&&!j.weightMissingPop&&r.pendingTas.empty()&&r.sourceFrames.empty()&&r.ackedOutOfOrder.empty()&&!r.incomplete);
 // Concurrent source-frame instances sharing UID cannot overwrite or cross-bind.
 reversal::Recorder copies;copies.enabled=true;copies.lastPoppedTask[1]={{0,1,0},10};copies.lastPoppedTask[2]={{0,1,1},10};copies.pendingTas[{0,1,0}]={1,2,0,1,true};copies.pendingTas[{0,1,1}]={1,2,0,2,true};copies.BindSourceFrame(frame0,0,{1},10);copies.BindSourceFrame(frame1,0,{2},10);assert(copies.sourceFrames.size()==2);
 UbReversalDiagnosticEvent tx;tx.kind=K::TxStart;tx.node=0;tx.timePs=20;tx.packet=frame1;copies.ObserveTaPacket(tx);assert(copies.pendingTas.at({0,1,1}).tx==20&&copies.pendingTas.at({0,1,0}).tx==0&&copies.sourceFrames.size()==1);tx.timePs=21;tx.packet=frame0;copies.ObserveTaPacket(tx);assert(copies.pendingTas.at({0,1,0}).tx==21&&copies.sourceFrames.empty());
 // A second binding of the same live instance is rejected, never overwritten.
 reversal::Recorder bad;bad.enabled=true;bad.lastPoppedTask[1]={{0,1,0},10};bad.BindSourceFrame(frame0,0,{1},10);bool failed=false;try{bad.BindSourceFrame(frame0,0,{1},10);}catch(const std::runtime_error&){failed=true;}assert(failed&&bad.incomplete);
 std::cout<<"PASS Jetty observer exact occupancy/phase clipping, out-of-order/duplicate ACK, three RTT boundaries, same-UID distinct source-frame occurrences, collision fail-closed\n";
}
