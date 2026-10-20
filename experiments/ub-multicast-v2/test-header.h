// SPDX-License-Identifier: GPL-2.0-only
#pragma once
std::vector<uint8_t> MakeNativeTestHeader(uint32_t dest,bool user,uint32_t len) {
    auto p=Create<Packet>(); UbMAExtTah ma; ma.SetLength(len); p->AddHeader(ma);
    if(user) { UbTransactionExtensionHeader ext(UbTransactionHeaderKind::UDETAH); ext.SetRaw({1,2,3,4}); p->AddHeader(ext); }
    UbTransactionHeader ta; ta.SetUbTransactionOpcode(UbTransactionOpcode::WRITE);ta.SetUdFlg(user);p->AddHeader(ta);
    UbTransportHeader tp;tp.SetTPOpcode(1);tp.SetDestTpn(dest+100);p->AddHeader(tp);
    UdpHeader udp; p->AddHeader(udp); Ipv4Header ip;ip.SetSource(Ipv4Address("10.0.0.1"));
    ip.SetDestination(Ipv4Address(0x0a000100+dest));ip.SetProtocol(17);ip.SetPayloadSize(p->GetSize()+len);p->AddHeader(ip);
    UbIpBasedNetworkHeader net;p->AddHeader(net);std::vector<uint8_t>b(p->GetSize());p->CopyData(b.data(),b.size());return b;
}
