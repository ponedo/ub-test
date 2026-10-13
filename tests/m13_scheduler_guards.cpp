#include <nano/ub/fair_scheduler_sc.h>
#include <nano/ub/tx.h>
#include <iostream>
#include <stdexcept>
static void check(bool ok, const char* what) { if(!ok) throw std::runtime_error(what); }
SC_MODULE(Guards) {
    sc_fifo<Flit> input, output, comp, sent, forwarded, ack;
    JettyFairScheduler sched;
    RetransmitBuffer retx;
    SC_HAS_PROCESS(Guards);
    Guards(sc_module_name n) : sc_module(n), input("input",32), output("output",1), comp("comp",8),
        sent("sent",8), forwarded("forwarded",8), ack("ack",8),
        sched("sched",2,nano_ub::SchedulePolicy::RoundRobin,128,1), retx("retx",true) {
        sched.in(input); sched.out(output); sched.comp_in(comp);
        retx.in(sent); retx.out(forwarded); retx.ack_in(ack);
        SC_THREAD(run);
    }
    Flit wr(bool fence=false) { auto f=Flit::make_valid(); f.rc_id=1; f.mem_addr=42; f.mem_len=64; f.fence=fence; return f; }
    void run() {
        // Reused target address must NOT alias completion identity.
        input.write(wr()); input.write(wr(true)); input.write(wr());
        wait(10,SC_NS);
        check(output.num_available()==1,"first dispatch missing");
        Flit first=output.read(); wait(5,SC_NS);
        check(output.num_available()==0,"fence did not wait for prior WR");
        auto wrong=first; wrong.rc_id=2; comp.write(wrong); wait(5,SC_NS);
        check(output.num_available()==0,"wrong Jetty released fence");
        wrong=first; wrong.sim_wr_id+=100; comp.write(wrong); wait(5,SC_NS);
        check(output.num_available()==0,"unknown token released fence");
        comp.write(first); wait(5,SC_NS);
        check(output.num_available()==1,"fence not released");
        Flit fenced=output.read(); check(fenced.sim_wr_id!=first.sim_wr_id,"address reused token");
        comp.write(first); wait(5,SC_NS);
        check(output.num_available()==0,"stale completion released follower");
        comp.write(fenced); wait(5,SC_NS);
        check(output.num_available()==1,"follower not released");
        comp.write(output.read()); wait(5,SC_NS);
        // Fill small queues and stall output: every WR must survive backpressure.
        for(unsigned i=0;i<20;++i) { auto f=wr(); f.rc_id=1+i%2; f.mem_addr=i; input.write(f); }
        wait(50,SC_NS);
        unsigned next[2]={0,1};
        for(unsigned i=0;i<20;++i) {
            auto f=output.read(); auto j=f.rc_id-1;
            check(f.mem_addr==next[j],"overflow lost/reordered WR"); next[j]+=2;
            comp.write(f); wait(2,SC_NS);
        }
        wait(10,SC_NS); check(output.num_available()==0,"duplicate WR");
        check(next[0]==20 && next[1]==21,"wrong WR count");
        // ACK must retire only its exact packet, never all outstanding copies.
        auto f=wr(); f.psn=0; sent.write(f); f.psn=1; sent.write(f); wait(10,SC_NS);
        check(retx.buffer.size()==2,"retx missing packet");
        f.psn=99; ack.write(f); wait(3,SC_NS); check(retx.buffer.size()==2,"unknown ACK retired packets");
        f.psn=0; ack.write(f); wait(3,SC_NS); check(retx.buffer.size()==1 && retx.buffer[0].psn==1,"ACK retired unrelated PSN");
        ack.write(f); wait(3,SC_NS); check(retx.buffer.size()==1,"duplicate ACK retired packet");
        f.psn=1; ack.write(f); wait(3,SC_NS); check(retx.buffer.empty(),"final ACK failed");
        std::cout << "PASS: exact Fence token, repeated address, stale/wrong completion, depth-1 backpressure, exact ACK retirement\n";
        sc_stop();
    }
};
int sc_main(int, char**) { Guards g("guards"); sc_start(10,SC_US); check(sc_end_of_simulation_invoked(),"guard timeout"); return 0; }
