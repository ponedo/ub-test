#ifndef NANO_UB_FAIR_SCHEDULER_H
#define NANO_UB_FAIR_SCHEDULER_H

// Functional, SystemC-independent scheduling core. The SC adapter is in
// fair_scheduler_sc.h. This is an experimental WR scheduler, not UB silicon.
#include <nano/flit.h>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
#include <stdexcept>
#include <vector>

namespace nano_ub {

enum class SchedulePolicy { Fifo, RoundRobin, DeficitRoundRobin };

struct QueuedWr {
    Flit flit;
    uint64_t arrival_ns = 0;
    uint64_t ordinal = 0;
};

class FairJettySchedulerCore {
public:
    FairJettySchedulerCore(std::size_t n_jetties, SchedulePolicy policy,
                           uint32_t quantum_bytes = 512,
                           std::size_t queue_depth = 4096,
                           uint32_t first_rc_id = 0)
        : first_rc_id_(first_rc_id), policy_(policy), quantum_(quantum_bytes), capacity_(queue_depth),
          queues_(n_jetties), deficit_(n_jetties, 0), blocked_(n_jetties, false) {
        if (!n_jetties || !quantum_bytes || !queue_depth)
            throw std::invalid_argument("n_jetties, quantum, depth must be > 0");
    }

    // Charges each WR for a fixed 64 B framing estimate + actual payload.
    // This is a modeling choice; it is NOT a UB-spec wire-format calculation.
    static uint32_t charge_bytes(const Flit& f) {
        return 64u + f.mem_len;
    }

    const Flit* front(uint32_t id) const {
        const auto& q = queues_.at(map_id(id));
        return q.empty() ? nullptr : &q.front().flit;
    }
    std::size_t jetty_count() const { return queues_.size(); }
    std::size_t queued_total() const { return count_; }
    std::size_t queued_for(std::size_t id) const { return queues_.at(id).size(); }
    bool valid_rc_id(uint32_t id) const {
        return id >= first_rc_id_ && uint64_t(id - first_rc_id_) < queues_.size();
    }
    void set_blocked(uint32_t id, bool value) { blocked_.at(map_id(id)) = value; }

    // rc_id must be in [first_rc_id, first_rc_id + n_jetties).
    bool enqueue(const Flit& wr, uint64_t arrival_ns = 0) {
        std::size_t id = map_id(wr.rc_id);
        if (queues_[id].size() >= capacity_) return false;
        QueuedWr req{wr, arrival_ns, next_ordinal_++};
        queues_[id].push_back(req);
        if (policy_ == SchedulePolicy::Fifo) fifo_order_.push_back(id);
        ++count_;
        return true;
    }

    // Pick one complete WR; never split a WR across Jetties. All policies
    // preserve each Jetty's FIFO order. No packet preemption is performed.
    std::optional<QueuedWr> dequeue() {
        if (!count_) return std::nullopt;
        if (policy_ == SchedulePolicy::Fifo) {
            if (fifo_order_.empty() || blocked_[fifo_order_.front()])
                return std::nullopt;
            auto id = fifo_order_.front();
            fifo_order_.pop_front();
            return pop(id);
        }
        if (policy_ == SchedulePolicy::RoundRobin) {
            for (std::size_t k = 0; k < queues_.size(); ++k) {
                std::size_t id = (cursor_ + k) % queues_.size();
                if (!blocked_[id] && !queues_[id].empty()) {
                    cursor_ = (id + 1) % queues_.size();
                    return pop(id);
                }
            }
            return std::nullopt;
        }
        // DRR: add quantum on each new visit, accumulate deficit for a
        // head WR larger than quantum, keep serving same Jetty while it has
        // enough credit. A blocked Jetty does not consume service.
        uint32_t max_head = 0;
        for (std::size_t i = 0; i < queues_.size(); ++i)
            if (!blocked_[i] && !queues_[i].empty())
                max_head = std::max(max_head, charge_bytes(queues_[i].front().flit));
        if (!max_head) return std::nullopt;
        const uint64_t rounds = 2ull + (uint64_t(max_head) + quantum_ - 1) / quantum_;
        const uint64_t limit = rounds * queues_.size();
        for (uint64_t step = 0; step < limit; ++step) {
            std::size_t id = cursor_;
            if (blocked_[id] || queues_[id].empty()) {
                if (queues_[id].empty()) deficit_[id] = 0;
                visit_active_ = false;
                advance();
                continue;
            }
            if (!visit_active_) {
                deficit_[id] += quantum_;
                visit_active_ = true;
            }
            uint32_t cost = charge_bytes(queues_[id].front().flit);
            if (deficit_[id] >= cost) {
                deficit_[id] -= cost;
                auto result = pop(id);
                if (queues_[id].empty()) {
                    deficit_[id] = 0;
                    visit_active_ = false;
                    advance();
                } else if (blocked_[id] ||
                           deficit_[id] < charge_bytes(queues_[id].front().flit)) {
                    visit_active_ = false;
                    advance();
                }
                return result;
            }
            visit_active_ = false;
            advance();
        }
        throw std::runtime_error("DRR bounded search failed to find eligible WR");
    }

private:
    std::size_t map_id(uint32_t rc_id) const {
        if (!valid_rc_id(rc_id)) throw std::out_of_range("unknown Jetty rc_id");
        return rc_id - first_rc_id_;
    }
    std::optional<QueuedWr> pop(std::size_t id) {
        QueuedWr req = queues_[id].front();
        queues_[id].pop_front();
        --count_;
        return req;
    }
    void advance() { cursor_ = (cursor_ + 1) % queues_.size(); }

    uint32_t first_rc_id_;
    SchedulePolicy policy_;
    uint32_t quantum_;
    std::size_t capacity_;
    std::vector<std::deque<QueuedWr>> queues_;
    std::deque<std::size_t> fifo_order_;
    std::vector<uint64_t> deficit_;
    std::vector<bool> blocked_;
    std::size_t cursor_ = 0;
    std::size_t count_ = 0;
    uint64_t next_ordinal_ = 0;
    bool visit_active_ = false;
};
} // namespace nano_ub
#endif
