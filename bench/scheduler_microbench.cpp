// Standalone discrete-event *scheduler* microbenchmark. NOT SystemC.
// All three policies share the same virtual serialization link.
#include <nano/ub/fair_scheduler.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <vector>
using namespace nano_ub;

struct Stat { std::vector<double> latency; uint64_t payload=0; uint64_t wire=0; uint64_t count=0; };
static double percentile(std::vector<double> v, double fraction) {
    if(v.empty())return 0;
    std::sort(v.begin(),v.end());
    return v[std::min(v.size()-1,(size_t)std::ceil(fraction*v.size())-1)];
}
static const char* label(SchedulePolicy p) {
    return p==SchedulePolicy::Fifo?"FIFO":p==SchedulePolicy::RoundRobin?"RR":"DRR";
}
static void run(SchedulePolicy p, std::ofstream& csv) {
    constexpr uint64_t duration_ns=2'000'000; // arrival generation: 2ms
    constexpr uint64_t end_ns=3'000'000;  // allow backlogged tail to drain partly
    constexpr unsigned bytes[2]={4096,64};
    constexpr uint64_t interval[2]={12,30}; // deterministic heavy/small arrivals
    FairJettySchedulerCore s(2,p,512,300000);
    uint64_t next[2]={0,0}, now=0, link_free=0;
    Stat st[2];
    // Enqueue arrivals up to current virtual time, then transmit a full WR.
    while(now<end_ns) {
        for(int j=0;j<2;j++) {
            while(next[j] <= now && next[j]<duration_ns) {
                Flit f=Flit::make_valid(); f.ta_opcode=3; f.rc_id=j;f.mem_len=bytes[j];
                if (!s.enqueue(f,next[j])) throw std::runtime_error("queue exhausted");
                next[j]+=interval[j];
            }
        }
        auto item=s.dequeue();
        if (!item) {
            auto target=std::min(next[0],next[1]);
            if(target>=duration_ns) break;
            now=std::max(now+1,target);
            continue;
        }
        int j=item->flit.rc_id;
        const uint64_t wire_bytes=FairJettySchedulerCore::charge_bytes(item->flit);
        const uint64_t service_ns=(wire_bytes*8+99)/100; // 100 Gbps, ceil(ns)
        uint64_t start_ns=std::max(now,link_free);
        uint64_t complete=start_ns+service_ns;
        if(complete>end_ns) break;
        st[j].latency.push_back((double)(complete-item->arrival_ns));
        st[j].payload+=item->flit.mem_len;
        st[j].wire+=wire_bytes;
        st[j].count++;
        now=complete;link_free=complete;
    }
    for(int j=0;j<2;++j) {
        const auto& a=st[j];
        csv<<label(p)<<","<<j<<","<<bytes[j]<<","<<a.count<<","<<a.payload
           <<","<<a.wire<<","<<std::fixed<<std::setprecision(2)
           <<percentile(a.latency,.50)<<","<<percentile(a.latency,.99)<<"\n";
        std::cout<<label(p)<<" J"<<j<<" completed="<<a.count<<" p50="<<percentile(a.latency,.5)
                 <<" ns p99="<<percentile(a.latency,.99)<<" ns\n";
    }
    double a=double(st[0].wire), b=double(st[1].wire);
    std::cout<<label(p)<<" Jain(byte share)="<<(a+b)*(a+b)/(2*(a*a+b*b))<<"\n";
}
int main(int argc,char**argv) {
    const char* path=argc>1?argv[1]:"scheduler_microbench.csv";
    std::ofstream out(path);
    if(!out) throw std::runtime_error("cannot open results CSV");
    out<<"policy,jetty,payload_bytes,completed,payload_transmitted_bytes,wire_transmitted_bytes,p50_ns,p99_ns\n";
    for(auto p:{SchedulePolicy::Fifo,SchedulePolicy::RoundRobin,SchedulePolicy::DeficitRoundRobin})run(p,out);
}
