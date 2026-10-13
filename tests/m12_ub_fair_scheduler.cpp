#include <nano/ub/fair_scheduler_sc.h>
#include <cassert>
#include <iostream>
#include <vector>

int sc_main(int, char*[]) {
    constexpr unsigned per_jetty = 80;
    sc_fifo<Flit> input("input", 2 * per_jetty + 16);
    sc_fifo<Flit> output("output", 2 * per_jetty + 16);
    sc_fifo<Flit> completion("completion", 8);
    JettyFairScheduler sched("sched", 2,
                             nano_ub::SchedulePolicy::DeficitRoundRobin, 512);
    sched.in.bind(input);
    sched.out.bind(output);
    sched.comp_in.bind(completion);
    for (unsigned i=0;i<per_jetty;++i) {
        Flit large=Flit::make_valid(); large.rc_id=1;large.ta_opcode=3;
        large.mem_len=4096; large.mem_addr=i;
        Flit small=Flit::make_valid(); small.rc_id=2;small.ta_opcode=3;
        small.mem_len=64; small.mem_addr=i;
        assert(input.nb_write(large));
        assert(input.nb_write(small));
    }
    sc_start(2000, SC_NS);
    unsigned next[2]={0,0};
    unsigned emitted[2]={0,0};
    Flit f;
    while (output.nb_read(f)) {
        assert(f.rc_id>=1 && f.rc_id<=2);
        assert(f.mem_addr==next[f.rc_id-1]);
        ++next[f.rc_id-1]; ++emitted[f.rc_id-1];
    }
    assert(emitted[0]==per_jetty && emitted[1]==per_jetty);
    std::cout << "PASS: SystemC DRR scheduler, per-Jetty FIFO, 160 WRs\n";
    return 0;
}
