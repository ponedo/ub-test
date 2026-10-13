#include <nano/ub/fair_scheduler.h>
#include <cassert>
#include <iostream>
#include <vector>
using namespace nano_ub;

static Flit wr(unsigned jetty, unsigned bytes, unsigned marker) {
    Flit f=Flit::make_valid(); f.rc_id=jetty; f.mem_len=bytes; f.mem_addr=marker;
    f.ta_opcode=3; return f;
}
int main() {
    for (auto policy:{SchedulePolicy::Fifo,SchedulePolicy::RoundRobin,SchedulePolicy::DeficitRoundRobin}) {
        FairJettySchedulerCore s(3,policy,256);
        for (int j=0;j<3;++j) for (int i=0;i<30;++i)
            assert(s.enqueue(wr(j,(j==0)?4096:64, unsigned(j*100+i))));
        int next[3]={0,0,0}, seen[3]={0,0,0};
        for (int k=0;k<90;++k) {
            auto f=s.dequeue(); assert(f);
            int id=f->flit.rc_id;
            assert((int)f->flit.mem_addr==id*100+next[id]);
            ++next[id];++seen[id];
        }
        assert(!s.dequeue());
        for(int j=0;j<3;++j) assert(seen[j]==30);
    }
    // RR must alternate ready Jetties; blocked Jetty must not hold up others.
    {
        FairJettySchedulerCore s(2,SchedulePolicy::RoundRobin);
        s.enqueue(wr(0,4096,0));s.enqueue(wr(0,4096,1));
        s.enqueue(wr(1,64,2));s.enqueue(wr(1,64,3));
        assert(s.dequeue()->flit.rc_id==0);
        assert(s.dequeue()->flit.rc_id==1);
        s.set_blocked(0,true);
        assert(s.dequeue()->flit.rc_id==1);
        assert(!s.dequeue());
        s.set_blocked(0,false);
        assert(s.dequeue()->flit.rc_id==0);
    }
    // In FIFO, blocked global head holds up all Jetties (negative control).
    {
        FairJettySchedulerCore s(2,SchedulePolicy::Fifo);
        s.enqueue(wr(0,4096,0));s.enqueue(wr(1,64,1));
        s.set_blocked(0,true);assert(!s.dequeue());
        s.set_blocked(0,false);assert(s.dequeue()->flit.rc_id==0);
        assert(s.dequeue()->flit.rc_id==1);
    }
    // Limited capacity must fail cleanly without discarding queued WRs.
    {
        FairJettySchedulerCore s(1,SchedulePolicy::DeficitRoundRobin,128,1);
        assert(s.enqueue(wr(0,4096,0)));
        assert(!s.enqueue(wr(0,4096,1)));
        assert(s.dequeue()->flit.mem_addr==0);
    }
    std::cout << "PASS: 3 policies, per-Jetty FIFO, blocked isolation, queue overflow\n";
}
