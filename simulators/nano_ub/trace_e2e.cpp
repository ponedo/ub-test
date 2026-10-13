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
#include "input.h"

using nano_ub::SchedulePolicy;
static uint64_t ps() { return sc_time_stamp().value(); }
static void require(bool v, const char* msg) { if (!v) throw std::runtime_error(msg); }
static uint8_t pattern(unsigned id, unsigned offset) { return uint8_t(id * 37 + offset * 13 + 7); }
// Observation only: delegate every operation to the original sc_fifo. No waits,
// storage slots or notification events are added by these callbacks.
struct ObservedFifo : sc_fifo<Flit> {
    std::function<void(const char*,const Flit&)> observe;
    ObservedFifo(const char* name,int depth):sc_fifo<Flit>(name,depth){}
    void read(Flit& f) override {
        sc_fifo<Flit>::read(f); if(observe)observe("read",f);
    }
    Flit read() override { Flit f; read(f); return f; }
    void write(const Flit& f) override {
        if(observe)observe("write_offer",f);
        sc_fifo<Flit>::write(f);
        if(observe)observe("write_accept",f);
    }
};
struct Row {
    Flit f;
    uint64_t id, sequence;
    TraceSpec spec;
    bool ready_seen=false, eligible_seen=false, submitted=false, admitted=false;
    uint64_t eligible=0, enqueue=0, dequeue=0;
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
    ObservedFifo input;
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
    std::map<std::pair<uint32_t,uint64_t>, unsigned> by_addr;
    std::map<uint64_t,unsigned> by_id;
    std::map<uint32_t,std::vector<uint8_t>> targets;
    sc_event completed;
    std::ofstream events, timeline;
    std::string ingress_mode;
    unsigned batch_limit, source_depth, scheduler_depth;
    uint64_t observation_sequence=0, epoch=0;
    sc_event admitted_event, ready_changed;
    std::vector<TraceSpec> specs;
    unsigned done=0;
    SC_HAS_PROCESS(Experiment);
    Experiment(sc_module_name n, SchedulePolicy policy, const std::vector<TraceSpec>& load,
               const std::string& prefix, double rate, const std::string& mode, unsigned batch, unsigned source_capacity, unsigned scheduler_capacity)
        : sc_module(n), input("input", source_capacity), q("q"), door("door"),
          scheduler("scheduler", jetty_count(load), policy, 512, scheduler_capacity), order("order", true),
          ordered_tap("ordered_tap"), btah("btah"), tpg("tpg", 1, true),
          tp("tp"), congestion("congestion"), retransmit("retransmit", true),
          rtph("rtph"), nth("nth"), encap("encap"), link("link",rate),
          decap_b("decap_b"), nth_b("nth_b"), rtph_b("rtph_b"), tp_b("tp_b"),
          reorder_b("reorder_b"), btah_b("btah_b"), order_b("order_b"),
          dispatch_b("dispatch_b"), memory_b("memory_b"), completion_b("completion_b"),
          completion_order_b("completion_order_b"), taack("taack"), ack_stamp("ack_stamp"),
          response_btah("response_btah"), response_nth("response_nth"), response_encap("response_encap"),
          decap_a("decap_a"), nth_a("nth_a"), rtph_a("rtph_a"), btah_a("btah_a"),
          events(prefix+".events.csv"), timeline(prefix+".timeline.csv"), ingress_mode(mode),
          batch_limit(batch), source_depth(source_capacity), scheduler_depth(scheduler_capacity), specs(load) {
        require(bool(events), "cannot open events output");
        events << "time_ps,event,wr_id,jetty,psn,bytes,offset,src_node,dst_node,sequence\n";
        require(bool(timeline), "cannot open timeline output");
        timeline << "event_seq,delta,time_ps,event,wr_id,jetty,psn,epoch,gate_held,scheduler_queued,jetty_queued,input_available";
        for(unsigned i=0;i<12;++i)timeline << ",q" << i << "_available";
        timeline << '\n';
        q.init(55, [](const char* name, size_t) { return new ObservedFifo(name, 1); });
        if(ingress_mode=="epoch-rr")scheduler.admission_hold=true;
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
        input.observe=[&](const char* action,const Flit& f){observe(std::string("input_")+action,f);};
        for(unsigned i=0;i<12;++i) {
            static_cast<ObservedFifo&>(q[i]).observe=[&,i](const char* action,const Flit& f){observe("q"+std::to_string(i)+"_"+action,f);};
        }
        scheduler.on_enqueue = [&](const Flit& f) {
            auto& r=row(f); r.enqueue=ps();r.admitted=true;log("enqueue",f);
            if(ingress_mode=="epoch-rr")admitted_event.notify(SC_ZERO_TIME);
        };
        scheduler.on_dequeue = [&](const Flit& f) { row(f).dequeue=ps(); log("dequeue",f); };
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
        memory_b.external_write = [&](const Flit& f) {
            auto& mem=targets.at(f.dst_addr);
            auto& r=row(f); require(!r.memory, "duplicate target execution");
            require(f.mem_addr+f.mem_len <= mem.size(), "target memory bound");
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
        SC_THREAD(source); SC_THREAD(complete); SC_THREAD(watchdog); SC_THREAD(ready_clock);
    }
    Row& row(const Flit& f) {
        auto it=by_addr.find({f.is_response ? f.src_addr : f.dst_addr,f.mem_addr}); require(it!=by_addr.end(), "unknown WR address");
        auto& r=rows[it->second];
        require((f.is_response ? f.dst_addr : f.src_addr)==r.f.src_addr,"source identity changed");
        require(f.rc_id==r.f.rc_id, "Jetty identity changed");
        require(f.mem_len==r.f.mem_len, "WR length changed");
        return r;
    }
    void observe(const std::string& event,const Flit& f) {
        auto& r=row(f);
        timeline << observation_sequence++ << ',' << sc_delta_count() << ',' << ps() << ',' << event << ',' << r.id << ',' << r.spec.jetty << ',' << f.psn << ',' << epoch << ',' << scheduler.admission_hold << ',' << scheduler.core.queued_total() << ',' << scheduler.core.queued_for(f.rc_id-1) << ',' << input.num_available();
        for(unsigned i=0;i<12;++i)timeline << ',' << q[i].num_available();
        timeline << '\n';
    }
    void log(const char* event, const Flit& f, unsigned bytes=0, unsigned offset=0) {
        auto& r=row(f);
        events << ps() << ',' << event << ',' << r.id << ',' << r.spec.jetty << ',' << f.psn << ',' << bytes << ',' << offset << ',' << r.spec.src << ',' << r.spec.dst << ',' << r.sequence << '\n';
        if(std::string(event)!="tx_chunk" && std::string(event)!="ack_chunk")observe(event,f);
    }
    void make_workload() {
        for (const auto& s:specs) {
            Row r; r.spec=s; r.id=s.id; r.sequence=s.sequence; r.f=Flit::make_valid();
            r.f.rc_id=s.mapped_jetty; r.f.ta_opcode=3; r.f.src_addr=s.mapped_src; r.f.dst_addr=s.mapped_dst;
            r.f.mem_len=s.size; r.f.mem_addr=s.address;
            r.source.resize(s.size);
            for (unsigned k=0;k<s.size;++k) r.source[k]=pattern(r.id,k);
            r.f.inline_len=std::min<uint64_t>(16,s.size); std::copy_n(r.source.begin(),r.f.inline_len,r.f.inline_data);
            by_addr[{s.mapped_dst,s.address}]=rows.size(); by_id[s.id]=rows.size();
            targets[s.mapped_dst].resize(s.address+s.size);
            rows.push_back(std::move(r));
        }
    }
    void source() {
        if(ingress_mode=="epoch-rr") {source_epoch();return;}
        if(rows.empty()) { sc_stop(); return; }
        std::map<uint32_t,uint64_t> next_sequence;
        unsigned submitted=0;
        while(submitted<rows.size()) {
            uint64_t next_ready=UINT64_MAX;
            for(auto& r:rows) {
                if(r.spec.ready*1000<=ps()) {
                    if(!r.ready_seen) {r.ready_seen=true; log("ready",r.f,r.f.mem_len);}
                } else next_ready=std::min(next_ready,r.spec.ready*1000);
            }
            for(auto& r:rows) {
                if(r.submitted || !r.ready_seen || r.sequence!=next_sequence[r.f.rc_id]) continue;
                bool deps=true;
                for(auto id:r.spec.dependencies) deps=deps && rows.at(by_id.at(id)).complete!=0;
                if(!deps)continue;
                if(!r.eligible_seen) {r.eligible_seen=true;r.eligible=ps();log("eligible",r.f);}
                if(input.nb_write(r.f)) {
                    r.submitted=true;r.submit=ps();log("submit",r.f,r.f.mem_len);
                    ++next_sequence[r.f.rc_id];++submitted;
                }
            }
            if(submitted==rows.size()) return;
            auto wake=completed | input.data_read_event();
            if(next_ready!=UINT64_MAX) wait(sc_time::from_value(next_ready-ps()),wake);
            else wait(wake);
        }
    }
    void ready_clock() {
        if(ingress_mode!="epoch-rr")return;
        for(auto& r:rows) {
            const uint64_t t=r.spec.ready*1000;
            if(t>ps())wait(sc_time::from_value(t-ps()));
            r.ready_seen=true;log("ready",r.f,r.f.mem_len);
            ready_changed.notify(SC_ZERO_TIME);
        }
    }
    bool dependencies_complete(const Row& r) {
        for(auto id:r.spec.dependencies)if(!rows.at(by_id.at(id)).complete)return false;
        return true;
    }
    void source_epoch() {
        if(rows.empty()){sc_stop();return;}
        std::map<unsigned,std::vector<Row*>> jets;
        std::map<unsigned,unsigned> head;
        for(auto& r:rows)jets[r.f.rc_id].push_back(&r);
        unsigned submitted=0,cursor=1;
        while(submitted<rows.size()) {
            // Explicit deterministic snapshot boundary. Later delta-cycle
            // completions at this same physical time join the NEXT epoch.
            wait(SC_ZERO_TIME);wait(SC_ZERO_TIME);
            uint64_t earliest=UINT64_MAX;
            for(auto& [j,queue]:jets)if(head[j]<queue.size()) {
                auto& r=*queue[head[j]];
                if(r.ready_seen && dependencies_complete(r))earliest=std::min(earliest,r.spec.ready);
            }
            std::vector<Row*> batch;
            for(unsigned k=0;k<scheduler.core.jetty_count() && batch.size()<std::min(batch_limit,source_depth);++k) {
                unsigned j=(cursor-1+k)%scheduler.core.jetty_count()+1;
                if(head[j]>=jets[j].size())continue;
                auto& r=*jets[j][head[j]];
                if(!r.ready_seen || r.spec.ready!=earliest || !dependencies_complete(r))continue;
                if(!r.eligible_seen){r.eligible_seen=true;r.eligible=ps();log("eligible",r.f);}
                if(scheduler.core.queued_for(j-1)<scheduler_depth)batch.push_back(&r);
            }
            if(batch.empty()) {
                scheduler.hold_dispatch(false);
                wait(completed | ready_changed | scheduler.space_);
                continue;
            }
            scheduler.hold_dispatch(true);++epoch;
            observe("epoch_begin",batch.front()->f);
            require(input.num_available()==0,"previous epoch not fully admitted");
            for(auto* r:batch) {
                require(input.nb_write(r->f),"epoch source capacity violated");
                r->submitted=true;r->submit=ps();log("submit",r->f,r->f.mem_len);
                ++head[r->f.rc_id];++submitted;
            }
            cursor=batch.back()->f.rc_id%scheduler.core.jetty_count()+1;
            while(!std::all_of(batch.begin(),batch.end(),[](auto r){return r->admitted;}))wait(admitted_event);
            observe("epoch_admitted",batch.back()->f);
            scheduler.hold_dispatch(false);
            observe("epoch_release",batch.back()->f);
            // Next loop gives run() a delta-cycle opportunity, but cannot
            // retract a WR already selected or blocked on downstream output.
        }
    }
    void complete() {
        while (true) {
            Flit f=q[33].read(); auto& r=row(f);
            require(f.ta_opcode==0x11 && f.is_response && f.syndrome==0, "invalid TAACK");
            require(f.psn==r.psn, "ACK PSN mismatch");
            require(f.sim_wr_id==r.token && r.token, "ACK WR token mismatch");
            require(r.memory && !r.complete, "completion before memory or duplicate");
            r.complete=ps(); ++done; log("complete",f); completed.notify(SC_ZERO_TIME);
            q[46].write(f); q[44].write(f); q[45].write(f);
            if (done==rows.size()) { wait(10,SC_NS); sc_stop(); }
        }
    }
    void watchdog() { wait(sc_time(specs.empty()?0:specs.back().ready,SC_NS)+sc_time(100,SC_MS)); SC_REPORT_FATAL("timeout", "lost WR or deadlock"); }
    void validate(const std::string& prefix) {
        require(done==rows.size(), "lost WR");
        require(retransmit.buffer.empty(), "unretired packet copies");
        require(tp.next_psn==rows.size() && tp_b.expected_psn==rows.size(), "PSN continuity");
        require(scheduler.core.queued_total()==0, "scheduler not drained");
        for (auto& entry:scheduler.outstanding) require(entry.second.empty(), "unretired scheduler WR");
        std::set<uint32_t> psns;
        std::ofstream out(prefix+".wr.csv"); require(bool(out), "cannot open WR output");
        out << "wr_id,src_node,jetty_id,dst_node,sequence,payload_bytes,phase,psn,ready_ps,eligible_ps,submit_ps,enqueue_ps,dequeue_ps,dispatch_ps,ordered_ps,tx_start_ps,tx_end_ps,memory_ps,complete_ps\n";
        std::map<uint32_t,const Row*> prev;
        for (auto& r:rows) {
            require(psns.insert(r.psn).second, "duplicate PSN");
            require(r.spec.ready*1000<=r.eligible && r.eligible<=r.submit && r.submit<=r.enqueue && r.enqueue<=r.dequeue && r.dequeue<=r.dispatch && r.dispatch<=r.ordered && r.ordered<r.tx_start && r.tx_start<r.tx_end && r.tx_end<r.memory && r.memory<r.complete, "invalid timeline");
            auto last=prev[r.f.rc_id];
            if(last) require(last->submit<=r.submit && last->dispatch<r.dispatch && last->memory<r.memory && last->complete<r.complete, "illegal per-Jetty reorder");
            prev[r.f.rc_id]=&r;
            for(auto id:r.spec.dependencies) require(r.submit>=rows.at(by_id.at(id)).complete,"dependency escaped");
            for(unsigned i=0;i<r.f.mem_len;++i) require(targets.at(r.f.dst_addr)[r.f.mem_addr+i]==pattern(r.id,i), "target data mismatch");
            out << r.id << ',' << r.spec.src << ',' << r.spec.jetty << ',' << r.spec.dst << ',' << r.sequence << ',' << r.f.mem_len << ',' << r.spec.phase << ',' << r.psn << ',' << r.spec.ready*1000 << ',' << r.eligible << ',' << r.submit << ',' << r.enqueue << ',' << r.dequeue << ',' << r.dispatch << ',' << r.ordered << ',' << r.tx_start << ',' << r.tx_end << ',' << r.memory << ',' << r.complete << '\n';
        }
        for(unsigned i=34;i<q.size();++i) require(q[i].num_available()==0, "undrained or unexpected protocol path");
        std::cout << "PASS " << "generic trace" << ": " << done << " WRs, full payload, identity, PSN, no loss/duplicate/reorder, ACK retirement\n";
    }
};
int sc_main(int argc, char** argv) {
    try {
        require(argc>=4 && argc<=8,"usage: trace_e2e fifo|rr|drr INPUT.tsv PREFIX [csv|epoch-rr [BATCH [SOURCE_DEPTH [SCHEDULER_DEPTH]]]]");
        std::string p=argv[1];
        require(p=="fifo" || p=="rr" || p=="drr", "bad policy");
        std::string mode=argc>4 ? argv[4] : "csv";
        require(mode=="csv" || mode=="epoch-rr","bad ingress mode");
        uint64_t batch=argc>5 ? number(argv[5]) : 64;
        uint64_t source_depth=argc>6 ? number(argv[6]) : 4096;
        uint64_t scheduler_depth=argc>7 ? number(argv[7]) : 4096;
        require(batch>=1 && batch<=1024 && source_depth>=1 && source_depth<=4096 && scheduler_depth>=1 && scheduler_depth<=4096,"invalid ingress capacities");
        auto specs=read_specs(argv[2]);
        sc_set_time_resolution(1,SC_PS);
        auto policy=p=="fifo" ? SchedulePolicy::Fifo : p=="rr" ? SchedulePolicy::RoundRobin : SchedulePolicy::DeficitRoundRobin;
        auto e=std::make_unique<Experiment>("experiment",policy,specs,argv[3],100.,mode,batch,source_depth,scheduler_depth);
        sc_start(); e->validate(argv[3]); return 0;
    } catch(const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
