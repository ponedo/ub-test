// SPDX-License-Identifier: GPL-2.0-only
#include "adapter-v2.h"
#include "ns3/internet-module.h"
#include <iostream>
using namespace ns3;
#include "test-header.h"
int main(int argc,char**argv) {
    const std::string fault=argc>1?argv[1]:"";
    auto source=CreateObject<writev2::SharedSource>();
    auto h=MakeNativeTestHeader(1,false,1);auto p=Create<Packet>(h.data(),h.size());uint8_t payload=93;p->AddAtEnd(Create<Packet>(&payload,1));
    UbDatalinkPacketHeader dl;dl.SetPacketVL(7);p->AddHeader(dl);
    writev2::SharedSource::Metadata m; m.header=h;m.flow=UbFlowTag(42,1);
    source->pending[{42,0}]={fault=="expired"?NanoSeconds(-1):MilliSeconds(10),0,{m}};
    std::vector<uint8_t> before(p->GetSize());p->CopyData(before.data(),before.size());
    if(fault=="header") {before[15]^=1;p=Create<Packet>(before.data(),before.size());}
    source->Restore(fault=="missing"?43:42,0,fault=="member"?1:0,p);
    if(fault=="duplicate")source->Restore(42,0,0,p);
    std::vector<uint8_t> after(p->GetSize());p->CopyData(after.data(),after.size());
    NS_ABORT_MSG_IF(before!=after || !source->pending.empty(),"association wire/state mismatch");
    UbFlowTag flow;UbTransactionCorrelationTag correlation;UbExplicitPayloadTag marker;
    NS_ABORT_MSG_IF(!p->PeekPacketTag(flow)||flow.GetFlowId()!=42||!p->PeekPacketTag(correlation)||!p->PeekPacketTag(marker),"association tag mismatch");
    source->CheckDrained();std::cout<<"PASS metadata only; wire unchanged; association consumed\n";
}
