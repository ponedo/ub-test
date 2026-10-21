// SPDX-License-Identifier: GPL-2.0-only
// Actual native Jetty admission/ACK/cleanup tests. No simulation schedules.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace ns3;
static uint64_t observed=0,admitted=0,acks=0,limited=0;
static void Sink(const UbReversalDiagnosticEvent&e){++observed;using K=UbReversalDiagnosticKind;
 if(e.kind==K::JettyAdmission)++admitted;
 if(e.kind==K::JettyTaAckAfter)++acks;
 if(e.kind==K::JettyWindowTest&&e.reason==UbReversalDiagnosticReason::Inflight)++limited;
 assert(e.aux0>=e.aux1&&e.aux0-e.aux1<=e.aux2);
}
static Ptr<UbJetty> Jetty(uint32_t window,uint32_t base){
 auto j=CreateObject<UbJetty>();j->SetAttribute("UbJettyInflightMax",UintegerValue(window));j->SetSrc(0);j->SetDest(1);j->SetJettyNum(9);j->SetNodeId(0);j->SetSport(0);j->SetDport(0);j->SetTaSegmentBytes(1);j->Init();
 UintegerValue ack;j->GetAttribute("JettyOooAckThreshold",ack);assert(ack.Get()==2048&&window<=ack.Get());j->SetTaSsnSendWindowForTest(base,base);return j;
}
static void Fill(Ptr<UbJetty>j,uint32_t window,uint32_t base){
 auto w=CreateObject<UbWqe>();w->SetWqeId(7);w->SetSrc(0);w->SetDest(1);w->SetSport(0);w->SetDport(0);w->SetType(UbTransactionOpcode::WRITE);w->SetSize(window+1);j->PushWqe(w);w->SetCanSend(true);
 for(uint32_t i=0;i<window;++i){assert(!j->IsLimited());auto s=j->GetNextWqeSegment();assert(s&&s->GetTaSsn()==base+i);assert(j->GetTaSsnSndNxtForTest()==base+i+1);}
 assert(j->IsLimited());assert(j->GetNextWqeSegment()==nullptr);assert(j->GetTaSsnSndNxtForTest()-j->GetTaSsnSndUnaForTest()==window);
}
static void Test(uint32_t window,uint32_t base,bool enabled){
 observed=admitted=acks=limited=0;UbReversalDiagnostic::SetSink(enabled?Sink:nullptr);
 auto j=Jetty(window,base);Fill(j,window,base);
 // Last bitmap slot (2047 in the largest treatment) ACKed before the base.
 assert(j->ProcessWqeSegmentComplete(base+window-1));assert(j->GetTaSsnSndUnaForTest()==base);assert(j->IsLimited());
 // Existing native in-window duplicate result, not a new completion sample.
 assert(j->ProcessWqeSegmentComplete(base+window-1));
 for(uint32_t i=1;i<window-1;++i)assert(j->ProcessWqeSegmentComplete(base+i));
 assert(j->GetTaSsnSndUnaForTest()==base);assert(j->ProcessWqeSegmentComplete(base));
 assert(j->GetTaSsnSndUnaForTest()==base+window&&!j->IsLimited());
 assert(!j->ProcessWqeSegmentComplete(base));assert(!j->ProcessWqeSegmentComplete(base+window));
 // The extra never-admitted byte keeps this unit out of transaction callbacks.
 j->ApplyWqeTerminal(7,UbWorkOutcome::FLUSHED);assert(j->GetActiveWqeCount()==0&&j->IsIdle());
 if(enabled)assert(admitted==window&&acks==window+1&&limited>=2&&observed>admitted+acks);else assert(observed==0);
 j->Dispose();
 // Failure cleanup must release the same full enlarged window without ACKs.
 auto failed=Jetty(window,base);Fill(failed,window,base);std::vector<uint32_t> tail;
 for(uint32_t i=1;i<window;++i)tail.push_back(base+i);
 failed->AdvanceTaSsnForWqeCleanup(tail);assert(failed->GetTaSsnSndUnaForTest()==base&&failed->IsLimited());
 failed->AdvanceTaSsnForWqeCleanup({base});assert(failed->GetTaSsnSndUnaForTest()==base+window);
 failed->ApplyWqeTerminal(7,UbWorkOutcome::FLUSHED);assert(failed->GetActiveWqeCount()==0&&failed->IsIdle());failed->Dispose();
 UbReversalDiagnostic::SetSink(nullptr);
}
int main(){Time::SetResolution(Time::PS);for(uint32_t window:{512u,1024u,2048u})for(uint32_t base:{0u,65530u})for(bool enabled:{false,true})Test(window,base,enabled);
 std::cout<<"PASS native TA windows 512/1024/2048: real admissions reach cap and block, out-of-order last ACK slot, duplicate/rejected ACKs, full release, terminal cleanup, logical SSN across 16-bit boundary, observer OFF/ON\n";}
