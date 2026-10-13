#ifndef NANO_UB_FAIR_SCHEDULER_SC_H
#define NANO_UB_FAIR_SCHEDULER_SC_H

// Drop-in work-request scheduler for Nano-UB's tx.h pipeline.
// The legacy JettyScheduler remains separate. Completions must echo the
// emitted sim_wr_id and rc_id; the token is simulator metadata, not a wire field.
#include <nano/ub/fair_scheduler.h>
#include <systemc.h>
#include <optional>
#include <functional>
#include <map>
#include <set>

SC_MODULE(JettyFairScheduler) {
    sc_fifo_in<Flit> in;
    sc_fifo_out<Flit> out;
    sc_fifo_in<Flit> comp_in;

    nano_ub::FairJettySchedulerCore core;
    sc_event released_, available_, space_;
    uint64_t next_wr_id_ = 1;
    // Optional experiment admission barrier. It never changes core policy or
    // retracts an already selected WR, and is disabled by default.
    bool admission_hold = false;
    sc_event admission_changed;
    void hold_dispatch(bool value) {
        if (admission_hold != value) {
            admission_hold = value;
            admission_changed.notify(SC_ZERO_TIME);
        }
    }
    // Experimental conservative per-Jetty barrier: wait for all prior WRs,
    // then gate followers until this exact fenced WR completes. Stronger than
    // the spec's Read/Atomic fence example; not a general dependency engine.
    std::map<uint32_t, std::set<uint64_t>> outstanding;
    std::map<uint32_t, uint64_t> fence_wr;
    std::function<void(const Flit&)> on_dispatch, on_enqueue, on_dequeue;
    void refresh_gates() {
        for (uint32_t id = 1; id <= core.jetty_count(); ++id) {
            const Flit* head = core.front(id);
            core.set_blocked(id, fence_wr.count(id) ||
                (head && head->fence && !outstanding[id].empty()));
        }
    }

    SC_HAS_PROCESS(JettyFairScheduler);
    JettyFairScheduler(sc_module_name name, unsigned n_jetties = 4,
                       nano_ub::SchedulePolicy policy = nano_ub::SchedulePolicy::DeficitRoundRobin,
                       unsigned quantum_bytes = 512, unsigned queue_depth = 4096)
        : sc_module(name), core(n_jetties, policy, quantum_bytes, queue_depth, 1) {
        SC_THREAD(ingress);
        SC_THREAD(run);
        SC_THREAD(completions);
    }

    void ingress() {
        while (true) {
            Flit f = in.read();
            while (!core.enqueue(f, sc_time_stamp().to_seconds() * 1e9))
                wait(space_);
            if (on_enqueue) on_enqueue(f);
            available_.notify(SC_ZERO_TIME);
        }
    }

    void run() {
        while (true) {
            if (admission_hold) { wait(admission_changed); continue; }
            refresh_gates();
            auto req = core.dequeue();
            if (req) {
                space_.notify(SC_ZERO_TIME);
                Flit& wr = req->flit;
                wr.sim_wr_id = next_wr_id_++;
                if (on_dequeue) on_dequeue(wr);
                outstanding[wr.rc_id].insert(wr.sim_wr_id);
                if (wr.fence) fence_wr[wr.rc_id] = wr.sim_wr_id;
                wait(1, SC_NS);  // legacy scheduler's nominal service cost
                if (on_dispatch) on_dispatch(wr);
                out.write(wr);
                continue;
            }
            wait(available_ | released_);
        }
    }

    void completions() {
        while (true) {
            Flit f = comp_in.read();
            if (core.valid_rc_id(f.rc_id)) {
                outstanding[f.rc_id].erase(f.sim_wr_id);
                auto it = fence_wr.find(f.rc_id);
                if (it != fence_wr.end() && it->second == f.sim_wr_id)
                    fence_wr.erase(it);
            }
            released_.notify(SC_ZERO_TIME);
        }
    }
};
#endif
