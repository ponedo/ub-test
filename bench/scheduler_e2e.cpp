#include <nano/ub/tx.h>
#include <nano/ub/rx.h>
#include <nano/ub/fair_scheduler_sc.h>
#include <nano/experimental/serialized_link.h>
#include <fstream>
#include <iomanip>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <set>

using nano_ub::SchedulePolicy;
static uint64_t ps() { return sc_time_stamp().value(); }
static void require(bool v, const char* msg) { if (!v) throw std::runtime_error(msg); }
static uint8_t pattern(unsigned id, unsigned offset) { return uint8_t(id * 37 + offset * 13 + 7); }
struct Row {
    Flit f;
    unsigned id, sequence;
    uint64_t submit=0, dispatch=0, ordered=0, tx_start=0, tx_end=0, memory=0, complete=0;
    uint32_t psn=0;
    uint64_t token=0;
    std::vector<uint8_t> source, received;
};
SC_MODULE(Tap) {
    sc_fifo_in<Flit> in; sc_fifo_out<Flit> out;
    std::function<void(Flit&)> action;
    SC_HAS_PROCESS(Tap);
    Tap(sc_module_name n) : sc_module(n) { SC_THREAD(run); }
    void run() { while (true) { Flit f=in.read(); action(f); out.write(f); } }
};
SC_MODULE(Experiment) {
    sc_fifo<Flit> input;
    sc_vector<sc_fifo<Flit>> q;
    UbDoorbell door;
    JettyFairScheduler scheduler;
    OrderTrackerIni order;
    Tap ordered_tap;
    BtahBuilder btah;
    TpgGroup tpg;
    TpChannelTx tp;
    CongestionWindow congestion;
    RetransmitBuffer retransmit;
    RtphBuilder rtph;
    NthBuilder nth;
    UbEncap encap;
    nano_ub_experiment::SerializedLink link;
    UbDecap decap_b;
    NthParser nth_b;
    RtphParser rtph_b;
    TpChannelRx tp_b;
    PsnReorder reorder_b;
    BtahParser btah_b;
    OrderTrackerTgt order_b;
    TransDispatch dispatch_b;
    UbMemory memory_b;
    UbCompletionGen completion_b;
    UbCompletionReorder completion_order_b;
    TaackGen taack;
    Tap ack_stamp;
    BtahBuilder response_btah;
    NthBuilder response_nth;
    UbEncap response_encap;
    UbDecap decap_a;
    NthParser nth_a;
    RtphParser rtph_a;
    BtahParser btah_a;
    std::vector<Row> rows;
    std::unordered_map<uint64_t, unsigned> by_addr;
    std::ofstream events;
    std::string workload;
    unsigned done=0;
    SC_HAS_PROCESS(Experiment);
    Experiment(sc_module_name n, SchedulePolicy policy, const std::string& load,
               const std::string& prefix, double rate)
        : sc_module(n), input("input", 4096), q("q"), door("door"),
          scheduler("scheduler", 3, policy, 512), order("order", true),
          ordered_tap("ordered_tap"), btah("btah"), tpg("tpg", 1, true),
          tp("tp"), congestion("congestion"), retransmit("retransmit", true),
          rtph("rtph"), nth("nth"), encap("encap"), link("link",rate),
          decap_b("decap_b"), nth_b("nth_b"), rtph_b("rtph_b"), tp_b("tp_b"),
          reorder_b("reorder_b"), btah_b("btah_b"), order_b("order_b"),
          dispatch_b("dispatch_b"), memory_b("memory_b"), completion_b("completion_b"),
          completion_order_b("completion_order_b"), taack("taack"), ack_stamp("ack_stamp"),
          response_btah("response_btah"), response_nth("response_nth"), response_encap("response_encap"),
          decap_a("decap_a"), nth_a("nth_a"), rtph_a("rtph_a"), btah_a("btah_a"),
          events(prefix+".events.csv"), workload(load) {
        require(bool(events), "cannot open events output");
        events << "time_ps,event,wr_id,jetty,psn,bytes,offset\n";
        q.init(55, [](const char* name, size_t) { return new sc_fifo<Flit>(name, 1); });
        door.wr_in(input); door.wr_out(q[0]);
        scheduler.in(q[0]); scheduler.out(q[1]); scheduler.comp_in(q[44]);
        order.in(q[1]); order.out(q[2]); order.comp_in(q[45]);
        ordered_tap.in(q[2]); ordered_tap.out(q[3]);
        btah.in(q[3]); btah.out(q[4]); tpg.in(q[4]); tpg.out(q[5]);
        tp.in(q[5]); tp.out(q[6]); congestion.in(q[6]); congestion.out(q[7]);
        retransmit.in(q[7]); retransmit.out(q[8]); retransmit.ack_in(q[46]);
        rtph.in(q[8]); rtph.out(q[9]); nth.in(q[9]); nth.out(q[10]);
        encap.in(q[10]); encap.out(q[11]); link.a_in(q[11]); link.b_out(q[12]);
        decap_b.in(q[12]); decap_b.out(q[13]); nth_b.in(q[13]); nth_b.tp_out(q[14]); nth_b.bypass_out(q[47]);
        rtph_b.in(q[14]); rtph_b.data_out(q[15]); rtph_b.ack_out(q[48]);
        tp_b.in(q[15]); tp_b.out(q[16]); reorder_b.in(q[16]); reorder_b.out(q[17]);
        btah_b.in(q[17]); btah_b.req_out(q[18]); btah_b.resp_out(q[49]);
        order_b.in(q[18]); order_b.out(q[19]); dispatch_b.in(q[19]); dispatch_b.write_out(q[20]);
        dispatch_b.read_out(q[50]); dispatch_b.atomic_out(q[51]); dispatch_b.send_out(q[52]);
        memory_b.req_in(q[20]); memory_b.resp_out(q[21]); completion_b.in(q[21]); completion_b.cqe_out(q[22]);
        completion_order_b.in(q[22]); completion_order_b.out(q[23]); taack.in(q[23]); taack.taack_out(q[24]);
        ack_stamp.in(q[24]); ack_stamp.out(q[25]); response_btah.in(q[25]); response_btah.out(q[26]);
        response_nth.in(q[26]); response_nth.out(q[27]); response_encap.in(q[27]); response_encap.out(q[28]);
        link.b_in(q[28]); link.a_out(q[29]); decap_a.in(q[29]); decap_a.out(q[30]);
        nth_a.in(q[30]); nth_a.tp_out(q[31]); nth_a.bypass_out(q[53]);
        rtph_a.in(q[31]); rtph_a.ack_out(q[32]); rtph_a.data_out(q[54]);
        btah_a.in(q[32]); btah_a.resp_out(q[33]); btah_a.req_out(q[34]);
        make_workload();
        scheduler.on_enqueue = [&](const Flit& f) { log("enqueue",f); };
        scheduler.on_dequeue = [&](const Flit& f) { log("dequeue",f); };
        scheduler.on_dispatch = [&](const Flit& f) {
            auto& r=row(f); require(!r.dispatch, "duplicate dispatch"); r.dispatch=ps(); r.token=f.sim_wr_id; log("dispatch",f);
        };
        ordered_tap.action = [&](Flit& f) { row(f).ordered=ps(); log("ordered",f); };
        link.source_payload = [&](const Flit& f) { return row(f).source; };
        link.received_payload = [&](const Flit& f, const std::vector<uint8_t>& bytes) {
            auto& r=row(f); require(r.received.empty(), "duplicate payload delivery"); r.received=bytes;
        };
        link.trace = [&](const char* event, const Flit& f, unsigned bytes, unsigned offset) {
            auto& r=row(f);
            if (std::string(event)=="tx_start") { r.tx_start=ps(); r.psn=f.psn; }
            if (std::string(event)=="tx_end") r.tx_end=ps();
            log(event,f,bytes,offset);
        };
        memory_b.complete_writes=true;
        memory_b.bulk_write = [&](const Flit& f, uint8_t* mem) {
            auto& r=row(f); require(!r.memory, "duplicate target execution");
            require(f.mem_addr+f.mem_len <= sizeof(memory_b.mem), "target memory bound");
            require(r.received.size()==f.mem_len, "payload length");
            for (unsigned i=0;i<f.mem_len;++i) {
                require(r.received[i]==pattern(r.id,i), "payload corruption");
                mem[f.mem_addr+i]=r.received[i];
            }
            r.memory=ps(); log("memory_commit",f);
        };
        // Experiment ACK combines successful transaction completion and packet
        // acknowledgement. No claim of complete independent TPACK machinery.
        ack_stamp.action = [&](Flit& f) { f.tp_opcode=0x02; };
        SC_THREAD(source); SC_THREAD(complete); SC_THREAD(watchdog);
    }
    Row& row(const Flit& f) {
        auto it=by_addr.find(f.mem_addr); require(it!=by_addr.end(), "unknown WR address");
        auto& r=rows[it->second];
        require(f.rc_id==r.f.rc_id, "Jetty identity changed");
        require(f.mem_len==r.f.mem_len, "WR length changed");
        return r;
    }
    void log(const char* event, const Flit& f, unsigned bytes=0, unsigned offset=0) {
        auto& r=row(f);
        events << ps() << ',' << event << ',' << r.id << ',' << f.rc_id << ',' << f.psn << ',' << bytes << ',' << offset << '\n';
    }
    void make_workload() {
        unsigned count=(workload=="mixed" || workload=="equal") ? 256 : 8;
        uint64_t address=0;
        // Eight-WR bursts per Jetty, all submitted at t=0. This is a fixed finite
        // batch, not a claim of steady state. Every Jetty keeps FIFO sequence.
        for (unsigned base=0;base<count;base+=8) for (unsigned j=1;j<=3;++j)
            for (unsigned i=base;i<std::min(base+8,count);++i) {
                Row r; r.id=rows.size(); r.sequence=i; r.f=Flit::make_valid();
                r.f.rc_id=j; r.f.ta_opcode=3; r.f.src_addr=1; r.f.dst_addr=2;
                r.f.mem_len=(workload=="equal") ? 256 : (j==1 ? 64 : j==2 ? 256 : 1024);
                r.f.mem_addr=address; address+=r.f.mem_len;
                r.f.service_mode=(workload=="rot") ? 2 : 0;
                if (workload=="fence") r.f.fence=(i==1 || i==4);
                if (workload=="ordering") r.f.odr=(i==0 || i==4) ? 1 : (i==1 || i==2 || i==5) ? 2 : 0;
                for (unsigned k=0;k<r.f.mem_len;++k) r.source.push_back(pattern(r.id,k));
                r.f.inline_len=16; std::copy_n(r.source.begin(),16,r.f.inline_data);
                by_addr[r.f.mem_addr]=r.id; rows.push_back(std::move(r));
            }
        require(address<=sizeof(memory_b.mem), "workload exceeds target memory");
    }
    void source() {
        for (auto& r:rows) { r.submit=ps(); input.write(r.f); log("submit",r.f,r.f.mem_len); }
    }
    void complete() {
        while (true) {
            Flit f=q[33].read(); auto& r=row(f);
            require(f.ta_opcode==0x11 && f.is_response && f.syndrome==0, "invalid TAACK");
            require(f.psn==r.psn, "ACK PSN mismatch");
            require(f.sim_wr_id==r.token && r.token, "ACK WR token mismatch");
            require(r.memory && !r.complete, "completion before memory or duplicate");
            r.complete=ps(); ++done; log("complete",f);
            q[46].write(f); q[44].write(f); q[45].write(f);
            if (done==rows.size()) { wait(10,SC_NS); sc_stop(); }
        }
    }
    void watchdog() { wait(5,SC_MS); SC_REPORT_FATAL("timeout", "lost WR or deadlock"); }
    void validate(const std::string& prefix) {
        require(done==rows.size(), "lost WR");
        require(retransmit.buffer.empty(), "unretired packet copies");
        require(tp.next_psn==rows.size() && tp_b.expected_psn==rows.size(), "PSN continuity");
        require(scheduler.core.queued_total()==0, "scheduler not drained");
        for (auto& entry:scheduler.outstanding) require(entry.second.empty(), "unretired scheduler WR");
        std::set<uint32_t> psns;
        std::ofstream out(prefix+".wr.csv"); require(bool(out), "cannot open WR output");
        out << "wr_id,jetty,sequence,payload_bytes,psn,submit_ps,dispatch_ps,ordered_ps,tx_start_ps,tx_end_ps,memory_ps,complete_ps\n";
        const Row* prev[3]={};
        for (auto& r:rows) {
            require(psns.insert(r.psn).second, "duplicate PSN");
            require(r.submit<=r.dispatch && r.dispatch<=r.ordered && r.ordered<r.tx_start && r.tx_start<r.tx_end && r.tx_end<r.memory && r.memory<r.complete, "invalid timeline");
            auto last=prev[r.f.rc_id-1];
            if(last) require(last->dispatch<r.dispatch && last->memory<r.memory && last->complete<r.complete, "illegal per-Jetty reorder");
            if(r.f.fence && last) require(r.dispatch>=last->complete, "Fence passed unfinished predecessor");
            if(last && last->f.fence) require(r.dispatch>=last->complete, "Fence follower escaped");
            prev[r.f.rc_id-1]=&r;
            for(unsigned i=0;i<r.f.mem_len;++i) require(memory_b.mem[r.f.mem_addr+i]==pattern(r.id,i), "target data mismatch");
            out << r.id << ',' << r.f.rc_id << ',' << r.sequence << ',' << r.f.mem_len << ',' << r.psn << ',' << r.submit << ',' << r.dispatch << ',' << r.ordered << ',' << r.tx_start << ',' << r.tx_end << ',' << r.memory << ',' << r.complete << '\n';
        }
        // Initiator safe_ordering is a conservative global domain. Check actual
        // entrance order, not original submission order across Jetties.
        std::vector<const Row*> ordered;
        for(auto& r:rows) ordered.push_back(&r);
        std::sort(ordered.begin(),ordered.end(),[](auto a,auto b){return a->ordered<b->ordered;});
        uint64_t prior_ordered_completion=0;
        for(auto r:ordered) {
            if(r->f.odr==2) require(r->ordered>=prior_ordered_completion, "SO passed incomplete RO/SO");
            if(r->f.odr==1 || r->f.odr==2) prior_ordered_completion=std::max(prior_ordered_completion,r->complete);
        }
        for(unsigned i=34;i<q.size();++i) require(q[i].num_available()==0, "undrained or unexpected protocol path");
        std::cout << "PASS " << workload << ": " << done << " WRs, full payload, identity, PSN, no loss/duplicate/reorder, ACK retirement\n";
    }
};
int sc_main(int argc, char** argv) {
    try {
        require(argc>=4,"usage: scheduler_e2e fifo|rr|drr mixed|equal|fence|ordering|rot PREFIX [Gbps]");
        std::string p=argv[1],load=argv[2];
        require(p=="fifo" || p=="rr" || p=="drr", "bad policy");
        require(load=="mixed" || load=="equal" || load=="fence" || load=="ordering" || load=="rot", "bad workload");
        double rate=argc==5 ? std::stod(argv[4]) : 100.; require(rate>0 && rate<=1000,"bad rate");
        sc_set_time_resolution(1,SC_PS);
        auto policy=p=="fifo" ? SchedulePolicy::Fifo : p=="rr" ? SchedulePolicy::RoundRobin : SchedulePolicy::DeficitRoundRobin;
        auto e=std::make_unique<Experiment>("experiment",policy,load,argv[3],rate);
        sc_start(); e->validate(argv[3]); return 0;
    } catch(const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
