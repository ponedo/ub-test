// SPDX-License-Identifier: GPL-2.0-only
#include "ns3/unified-bus-module.h"
#include "ns3/ub-write-v2.h"
#include "ns3/internet-module.h"
#include <iostream>
using namespace ns3;
static void Require(bool b) { if(!b) throw std::runtime_error("test assertion"); }
#include "test-header.h"

int main() {
    unsigned positive=0,negative=0;
    auto reject=[&](std::vector<uint8_t>b){bool failed=false;try{(void)UbWriteV2::Decode(b);}catch(const std::runtime_error&){failed=true;}Require(failed);++negative;};
    for(unsigned n:{1,2,4,8,64}) {
        UbWriteV2 v;v.operation=42;v.sequence=3;v.payload={0,2,4,8,16,32};
        for(unsigned i=0;i<n;++i)v.headers.push_back(MakeNativeTestHeader(i,i%2,v.payload.size()));
        auto b=v.Encode();auto d=UbWriteV2::Decode(b);
        Require(d.headers==v.headers&&d.payload==v.payload&&d.operation==42&&d.sequence==3);
        Require(b.size()==20+2*n+v.payload.size()+74*n+4*(n/2));++positive;
        for(size_t size=0;size<b.size();++size)reject({b.begin(),b.begin()+size});
        for(unsigned offset:{0,4,5,6,7,16,17,18,19,20,21}){auto x=b;x[offset]^=0xff;reject(x);}
        auto x=b;x.push_back(0);reject(x);
    }
    UbWriteV2 v;v.payload={1};v.headers={MakeNativeTestHeader(1,false,1),MakeNativeTestHeader(1,true,1)};
    bool duplicate=false;try{v.Encode();}catch(const std::runtime_error&){duplicate=true;}Require(duplicate);++negative;
    v.headers={MakeNativeTestHeader(1,false,1),MakeNativeTestHeader(2,true,1)};auto dup=v.Encode();
    std::copy(dup.begin()+24+22,dup.begin()+24+26,dup.begin()+24+74+22);reject(dup);
    v.headers={MakeNativeTestHeader(1,false,1)};auto b=v.Encode();b[22+6+20+8+16]=uint8_t(UbTransactionOpcode::READ);reject(b);
    std::cout<<"{\"status\":\"PASS\",\"roundtrips\":"<<positive<<",\"rejected\":"<<negative<<"}\n";
}
