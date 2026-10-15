// CPU semantic adapter for pinned CUDA source, NOT a GPU timing model.
// Each CUDA lane gets one CPU thread. All exercised collectives have full masks.
#include <algorithm>
#include <array>
#include <barrier>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
using std::min; using std::max;
#define __device__
#define __forceinline__ inline
#define __shared__
#define EP_DEVICE_ASSERT(x) do { if (!(x)) std::abort(); } while(0)
struct CpuWarp {std::barrier<> sync{32}; int values[32]{};};
CpuWarp warps[4]; std::barrier<> block_sync{128};
thread_local int cpu_tid;
void __syncwarp(){warps[cpu_tid/32].sync.arrive_and_wait();}
void __syncthreads(){block_sync.arrive_and_wait();}
int __shfl_sync(unsigned mask,int value,int lane){
 if(mask!=0xffffffffu || lane<0 || lane>=32)std::abort();
 auto& w=warps[cpu_tid/32]; w.values[cpu_tid%32]=value;
 w.sync.arrive_and_wait(); int result=w.values[lane];
 w.sync.arrive_and_wait(); return result;
}
int __shfl_xor_sync(unsigned mask,int value,int delta){return __shfl_sync(mask,value,(cpu_tid%32)^delta);}
struct Floor {int threshold,configured,effective,need,feasible_slots;};
std::vector<Floor> floors;
struct Probe {int threshold;bool dynamic,store;};
std::mutex trace_mutex;std::vector<Probe> trace;
void record_probe(int t,bool d,bool s){std::lock_guard<std::mutex> l(trace_mutex);trace.push_back({t,d,s});}
void record_floor(int t,int c,int e,int n,int f){std::lock_guard<std::mutex> l(trace_mutex);floors.push_back({t,c,e,n,f});}
struct {int x=128;} blockDim;
static constexpr int MAX_EXPERTS_PER_NVL = 512;
static constexpr int MAX_GPUS_PER_NVL = 72;
static constexpr int MAX_REPLICAS_PER_NVL = 512;
static constexpr int QUOTA_SOLVER_THREADS = 128;
static constexpr int QUOTA_SOLVER_WARPS = QUOTA_SOLVER_THREADS / 32;
static constexpr unsigned FULL_WARP_MASK = 0xFFFFFFFFu;
static constexpr int QUOTA_FAST_REPLICA_LIMIT = 8;
static constexpr int QUOTA_ORACLE_MAX_BATCH_K = 8;
static constexpr int QUOTA_ORACLE_FAST_MAX_RETRY = 2;

static_assert(QUOTA_SOLVER_THREADS % 32 == 0);
static_assert(QUOTA_FAST_REPLICA_LIMIT <= MAX_GPUS_PER_NVL);

struct ExportPlanEntry {
    int expert_local;
    int target_rank_local;
    int quota;
};

__device__ __forceinline__ bool occ_has(uint64_t low, uint64_t high, int rank_local) {
    if (rank_local < 64) {
        return ((low >> rank_local) & 1ULL) != 0ULL;
    }
    return ((high >> (rank_local - 64)) & 1ULL) != 0ULL;
}

__device__ __forceinline__ void occ_set(uint64_t& low, uint64_t& high, int rank_local) {
    if (rank_local < 64) {
        low |= (1ULL << rank_local);
    } else {
        high |= (1ULL << (rank_local - 64));
    }
}

__device__ __forceinline__ int warp_reduce_sum(int value) {
#pragma unroll
    for (int delta = 16; delta > 0; delta >>= 1) {
        value += __shfl_xor_sync(FULL_WARP_MASK, value, delta);
    }
    return value;
}

__device__ void warp_sort_source_ranks_by_load(int* source_order, const int32_t* rank_load, int G, int lane_id) {
    for (int i = lane_id; i < G; i += 32) {
        const int my_load = rank_load[i];
        int pos = 0;
        for (int j = 0; j < G; ++j) {
            const int other_load = rank_load[j];
            pos += ((other_load > my_load) || (other_load == my_load && j < i)) ? 1 : 0;
        }
        source_order[pos] = i;
    }
}

__device__ bool warp_capacity_feasible(const int32_t* rank_load, int threshold, int G, int lane_id) {
    int local_excess = 0;
    int local_slack = 0;
    for (int r = lane_id; r < G; r += 32) {
        local_excess += max(rank_load[r] - threshold, 0);
        local_slack += max(threshold - rank_load[r], 0);
    }
    return warp_reduce_sum(local_excess) <= warp_reduce_sum(local_slack);
}

__device__ void warp_init_oracle_state_parallel(int32_t* export_sum,
                                                uint64_t* occ_lo,
                                                uint64_t* occ_hi,
                                                int32_t* excess,
                                                int32_t* slack,
                                                int32_t* slots_used,
                                                const int32_t* rank_load,
                                                int threshold,
                                                int E,
                                                int G,
                                                int num_local_master,
                                                int lane_id) {
    for (int l = lane_id; l < E; l += 32) {
        export_sum[l] = 0;
        occ_lo[l] = 0ULL;
        occ_hi[l] = 0ULL;
        occ_set(occ_lo[l], occ_hi[l], l / num_local_master);
    }
    for (int r = lane_id; r < G; r += 32) {
        excess[r] = max(rank_load[r] - threshold, 0);
        slack[r] = max(threshold - rank_load[r], 0);
        slots_used[r] = 0;
    }
}

__device__ int warp_find_best_target(const int32_t* slack,
                                     const int32_t* slots_used,
                                     const uint64_t* occ_lo,
                                     const uint64_t* occ_hi,
                                     int expert_local,
                                     int need,
                                     int available,
                                     int min_tokens_per_replica,
                                     int num_local_redundant,
                                     int G,
                                     int lane_id) {
    int my_best_target = -1;
    int my_best_cap = -1;

    for (int target_rank_local = lane_id; target_rank_local < G; target_rank_local += 32) {
        if (slack[target_rank_local] <= 0 || slots_used[target_rank_local] >= num_local_redundant ||
            occ_has(occ_lo[expert_local], occ_hi[expert_local], target_rank_local)) {
            continue;
        }

        const int q = min(min(need, slack[target_rank_local]), available);
        if (q < min_tokens_per_replica) {
            continue;
        }

        if (slack[target_rank_local] > my_best_cap ||
            (slack[target_rank_local] == my_best_cap && (my_best_target < 0 || target_rank_local < my_best_target))) {
            my_best_target = target_rank_local;
            my_best_cap = slack[target_rank_local];
        }
    }

#pragma unroll
    for (int delta = 16; delta > 0; delta >>= 1) {
        const int other_target = __shfl_xor_sync(FULL_WARP_MASK, my_best_target, delta);
        const int other_cap = __shfl_xor_sync(FULL_WARP_MASK, my_best_cap, delta);
        const bool other_better = (other_target >= 0) &&
            ((my_best_target < 0) || (other_cap > my_best_cap) ||
             (other_cap == my_best_cap && other_target < my_best_target));
        if (other_better) {
            my_best_target = other_target;
            my_best_cap = other_cap;
        }
    }

    return my_best_target;
}

__device__ int warp_find_best_target_reg(int reg_slack_0,
                                         int reg_slack_1,
                                         int reg_slots_0,
                                         int reg_slots_1,
                                         uint64_t occ_lo,
                                         uint64_t occ_hi,
                                         int need,
                                         int available,
                                         int min_tokens_per_replica,
                                         int num_local_redundant,
                                         int G,
                                         int lane_id) {
    int my_best_target = -1;
    int my_best_cap = -1;

    const int target_0 = lane_id;
    if (target_0 < G && reg_slack_0 > 0 && reg_slots_0 < num_local_redundant && !occ_has(occ_lo, occ_hi, target_0)) {
        const int q0 = min(min(need, reg_slack_0), available);
        if (q0 >= min_tokens_per_replica) {
            my_best_target = target_0;
            my_best_cap = reg_slack_0;
        }
    }

    const int target_1 = lane_id + 32;
    if (target_1 < G && reg_slack_1 > 0 && reg_slots_1 < num_local_redundant && !occ_has(occ_lo, occ_hi, target_1)) {
        const int q1 = min(min(need, reg_slack_1), available);
        if (q1 >= min_tokens_per_replica &&
            (reg_slack_1 > my_best_cap ||
             (reg_slack_1 == my_best_cap && (my_best_target < 0 || target_1 < my_best_target)))) {
            my_best_target = target_1;
            my_best_cap = reg_slack_1;
        }
    }

#pragma unroll
    for (int delta = 16; delta > 0; delta >>= 1) {
        const int other_target = __shfl_xor_sync(FULL_WARP_MASK, my_best_target, delta);
        const int other_cap = __shfl_xor_sync(FULL_WARP_MASK, my_best_cap, delta);
        const bool other_better = (other_target >= 0) &&
            ((my_best_target < 0) || (other_cap > my_best_cap) ||
             (other_cap == my_best_cap && other_target < my_best_target));
        if (other_better) {
            my_best_target = other_target;
            my_best_cap = other_cap;
        }
    }

    return my_best_target;
}

__device__ int warp_collect_topk_targets_reg(int reg_slack_0,
                                             int reg_slack_1,
                                             int reg_slots_0,
                                             int reg_slots_1,
                                             uint64_t occ_lo,
                                             uint64_t occ_hi,
                                             int need,
                                             int available,
                                             int min_tokens_per_replica,
                                             int num_local_redundant,
                                             int G,
                                             int lane_id,
                                             int batch_k,
                                             int* out_targets,
                                             int* out_quota) {
    int cand_rank_0 = -1;
    int cand_cap_0 = -1;
    int cand_rank_1 = -1;
    int cand_cap_1 = -1;

    const int rank_0 = lane_id;
    if (rank_0 < G && reg_slack_0 > 0 && reg_slots_0 < num_local_redundant && !occ_has(occ_lo, occ_hi, rank_0)) {
        const int cap = min(min(need, reg_slack_0), available);
        if (cap >= min_tokens_per_replica) {
            cand_rank_0 = rank_0;
            cand_cap_0 = cap;
        }
    }

    const int rank_1 = lane_id + 32;
    if (rank_1 < G && reg_slack_1 > 0 && reg_slots_1 < num_local_redundant && !occ_has(occ_lo, occ_hi, rank_1)) {
        const int cap = min(min(need, reg_slack_1), available);
        if (cap >= min_tokens_per_replica) {
            cand_rank_1 = rank_1;
            cand_cap_1 = cap;
        }
    }

    int selected = 0;
    int sel_rank[QUOTA_ORACLE_MAX_BATCH_K];
    int sel_quota[QUOTA_ORACLE_MAX_BATCH_K];
    int top_rank[QUOTA_ORACLE_MAX_BATCH_K];
    int top_cap[QUOTA_ORACLE_MAX_BATCH_K];
    int top_n = 0;
    const int picks = min(batch_k, QUOTA_ORACLE_MAX_BATCH_K);
    for (int src = 0; src < 32; ++src) {
        const int r0 = __shfl_sync(FULL_WARP_MASK, cand_rank_0, src);
        const int c0 = __shfl_sync(FULL_WARP_MASK, cand_cap_0, src);
        if (lane_id == 0 && r0 >= 0 && c0 > 0 && picks > 0) {
            int idx = top_n;
            if (top_n < picks) {
                top_rank[idx] = r0;
                top_cap[idx] = c0;
                ++top_n;
            } else if (c0 > top_cap[picks - 1] || (c0 == top_cap[picks - 1] && r0 < top_rank[picks - 1])) {
                idx = picks - 1;
                top_rank[idx] = r0;
                top_cap[idx] = c0;
            } else {
                idx = -1;
            }
            while (idx > 0 &&
                   (top_cap[idx] > top_cap[idx - 1] ||
                    (top_cap[idx] == top_cap[idx - 1] && top_rank[idx] < top_rank[idx - 1]))) {
                const int tmp_rank = top_rank[idx - 1];
                const int tmp_cap = top_cap[idx - 1];
                top_rank[idx - 1] = top_rank[idx];
                top_cap[idx - 1] = top_cap[idx];
                top_rank[idx] = tmp_rank;
                top_cap[idx] = tmp_cap;
                --idx;
            }
        }
        const int r1 = __shfl_sync(FULL_WARP_MASK, cand_rank_1, src);
        const int c1 = __shfl_sync(FULL_WARP_MASK, cand_cap_1, src);
        if (lane_id == 0 && r1 >= 0 && c1 > 0 && picks > 0) {
            int idx = top_n;
            if (top_n < picks) {
                top_rank[idx] = r1;
                top_cap[idx] = c1;
                ++top_n;
            } else if (c1 > top_cap[picks - 1] || (c1 == top_cap[picks - 1] && r1 < top_rank[picks - 1])) {
                idx = picks - 1;
                top_rank[idx] = r1;
                top_cap[idx] = c1;
            } else {
                idx = -1;
            }
            while (idx > 0 &&
                   (top_cap[idx] > top_cap[idx - 1] ||
                    (top_cap[idx] == top_cap[idx - 1] && top_rank[idx] < top_rank[idx - 1]))) {
                const int tmp_rank = top_rank[idx - 1];
                const int tmp_cap = top_cap[idx - 1];
                top_rank[idx - 1] = top_rank[idx];
                top_cap[idx - 1] = top_cap[idx];
                top_rank[idx] = tmp_rank;
                top_cap[idx] = tmp_cap;
                --idx;
            }
        }
    }

    if (lane_id == 0) {
        int need_left = need;
        int available_left = available;
        for (int pick = 0; pick < top_n && need_left > 0 && available_left > 0; ++pick) {
            const int q = min(min(need_left, top_cap[pick]), available_left);
            if (q < min_tokens_per_replica) {
                break;
            }
            sel_rank[selected] = top_rank[pick];
            sel_quota[selected] = q;
            ++selected;

            need_left -= q;
            available_left -= q;
        }
    }

    selected = __shfl_sync(FULL_WARP_MASK, selected, 0);
    for (int i = 0; i < selected; ++i) {
        out_targets[i] = __shfl_sync(FULL_WARP_MASK, sel_rank[i], 0);
        out_quota[i] = __shfl_sync(FULL_WARP_MASK, sel_quota[i], 0);
    }
    return selected;
}

template <bool STORE_PLAN>
__device__ bool warp_build_export_plan(const int32_t* loads,
                                       const int* sorted_experts,
                                       int32_t* export_sum,
                                       int32_t* excess,
                                       int32_t* slack,
                                       int32_t* slots_used,
                                       const int32_t* rank_load,
                                       const int* source_order,
                                       uint64_t* occ_lo,
                                       uint64_t* occ_hi,
                                       ExportPlanEntry* export_plan,
                                       int& num_exports,
                                       int threshold,
                                       int G,
                                       int num_local_master,
                                       int num_local_redundant,
                                       int min_tokens_per_replica,
                                       bool allow_zero_master_quota,
                                       int lane_id,
                                       bool use_dynamic_q_floor = false,
                                       int batch_k = 1) {
    if (lane_id == 0) record_probe(threshold, use_dynamic_q_floor, STORE_PLAN);
    if (lane_id == 0) {
        num_exports = 0;
    }
    __syncwarp();

    int local_excess = 0;
    int local_slack = 0;
    for (int r = lane_id; r < G; r += 32) {
        local_excess += excess[r];
        local_slack += slack[r];
    }
    const int total_excess = warp_reduce_sum(local_excess);
    const int total_slack = warp_reduce_sum(local_slack);
    if (total_excess == 0) {
        return true;
    }
    if (total_excess > total_slack) {
        return false;
    }

    const bool use_register_state = (G <= 64);
    const int my_rank_0 = lane_id;
    const int my_rank_1 = lane_id + 32;
    int reg_slack_0 = 0;
    int reg_slack_1 = 0;
    int reg_slots_0 = 0;
    int reg_slots_1 = 0;
    if (use_register_state) {
        if (my_rank_0 < G) {
            reg_slack_0 = max(threshold - rank_load[my_rank_0], 0);
        }
        if (my_rank_1 < G) {
            reg_slack_1 = max(threshold - rank_load[my_rank_1], 0);
        }
    }

    int running_excess = total_excess;
    int running_slack = total_slack;
    for (int ord = 0; ord < G; ++ord) {
        const int source_rank_local = source_order[ord];
        int need = excess[source_rank_local];
        if (need <= 0) {
            continue;
        }
        int source_impossible = 0;
        if (lane_id == 0 && need > running_slack) {
            source_impossible = 1;
        }
        source_impossible = __shfl_sync(FULL_WARP_MASK, source_impossible, 0);
        if (source_impossible) {
            return false;
        }

        for (int pos = 0; pos < num_local_master; ++pos) {
            const int expert_local = sorted_experts[source_rank_local * num_local_master + pos];
            const int keep_on_master = (!allow_zero_master_quota && loads[expert_local] > 0) ? 1 : 0;
            if (use_register_state) {
                uint64_t local_occ_lo = occ_lo[expert_local];
                uint64_t local_occ_hi = occ_hi[expert_local];
                int local_export_sum = export_sum[expert_local];
                int available = max(loads[expert_local] - keep_on_master - local_export_sum, 0);
                const int batch_k_local = min(max(batch_k, 1), QUOTA_ORACLE_MAX_BATCH_K);

                while (need > 0 && available > 0) {
                    int effective_min_tokens = min_tokens_per_replica;
                    if (use_dynamic_q_floor) {
                        int local_feasible = 0;
                        const int rank0 = lane_id;
                        if (rank0 < G && reg_slack_0 > 0 && reg_slots_0 < num_local_redundant &&
                            !occ_has(local_occ_lo, local_occ_hi, rank0) && min(min(need, reg_slack_0), available) > 0) {
                            local_feasible += 1;
                        }
                        const int rank1 = lane_id + 32;
                        if (rank1 < G && reg_slack_1 > 0 && reg_slots_1 < num_local_redundant &&
                            !occ_has(local_occ_lo, local_occ_hi, rank1) && min(min(need, reg_slack_1), available) > 0) {
                            local_feasible += 1;
                        }
                        const int feasible_slots = warp_reduce_sum(local_feasible);
                        if (feasible_slots <= 0) {
                            break;
                        }
                        effective_min_tokens = max(1, (need + feasible_slots - 1) / feasible_slots);
                        if (lane_id == 0) record_floor(threshold, min_tokens_per_replica, effective_min_tokens, need, feasible_slots);
                    }

                    if (batch_k_local > 1) {
                        int selected_targets[QUOTA_ORACLE_MAX_BATCH_K];
                        int selected_quota[QUOTA_ORACLE_MAX_BATCH_K];
                        const int selected = warp_collect_topk_targets_reg(reg_slack_0,
                                                                           reg_slack_1,
                                                                           reg_slots_0,
                                                                           reg_slots_1,
                                                                           local_occ_lo,
                                                                           local_occ_hi,
                                                                           need,
                                                                           available,
                                                                           effective_min_tokens,
                                                                           num_local_redundant,
                                                                           G,
                                                                           lane_id,
                                                                           batch_k_local,
                                                                           selected_targets,
                                                                           selected_quota);
                        if (selected <= 0) {
                            break;
                        }

                        if constexpr (STORE_PLAN) {
                            int can_store = 1;
                            if (lane_id == 0 && num_exports + selected > MAX_REPLICAS_PER_NVL) {
                                can_store = 0;
                            }
                            can_store = __shfl_sync(FULL_WARP_MASK, can_store, 0);
                            if (!can_store) {
                                return false;
                            }
                        }

                        for (int idx = 0; idx < selected; ++idx) {
                            const int target = selected_targets[idx];
                            const int q = selected_quota[idx];

                            if constexpr (STORE_PLAN) {
                                if (lane_id == 0) {
                                    export_plan[num_exports++] = {expert_local, target, q};
                                }
                            }
                            if (my_rank_0 == target) {
                                reg_slack_0 -= q;
                                reg_slots_0 += 1;
                            }
                            if (my_rank_1 == target) {
                                reg_slack_1 -= q;
                                reg_slots_1 += 1;
                            }
                            occ_set(local_occ_lo, local_occ_hi, target);
                            if (lane_id == 0) {
                                local_export_sum += q;
                                running_excess -= q;
                                running_slack -= q;
                            }
                            need -= q;
                            available -= q;
                        }
                    } else {
                        const int best_target = warp_find_best_target_reg(reg_slack_0,
                                                                          reg_slack_1,
                                                                          reg_slots_0,
                                                                          reg_slots_1,
                                                                          local_occ_lo,
                                                                          local_occ_hi,
                                                                          need,
                                                                          available,
                                                                          effective_min_tokens,
                                                                          num_local_redundant,
                                                                          G,
                                                                          lane_id);
                        if (best_target < 0) {
                            break;
                        }

                        if constexpr (STORE_PLAN) {
                            int can_store = 1;
                            if (lane_id == 0 && num_exports >= MAX_REPLICAS_PER_NVL) {
                                can_store = 0;
                            }
                            can_store = __shfl_sync(FULL_WARP_MASK, can_store, 0);
                            if (!can_store) {
                                return false;
                            }
                        }

                        int my_best_slack = 0;
                        if (my_rank_0 == best_target) {
                            my_best_slack = reg_slack_0;
                        }
                        if (my_rank_1 == best_target) {
                            my_best_slack = reg_slack_1;
                        }
                        const int owner_lane = best_target & 31;
                        const int best_slack = __shfl_sync(FULL_WARP_MASK, my_best_slack, owner_lane);
                        int q = 0;
                        if (lane_id == 0) {
                            q = min(min(need, best_slack), available);
                        }
                        q = __shfl_sync(FULL_WARP_MASK, q, 0);
                        if (q < effective_min_tokens) {
                            break;
                        }

                        if constexpr (STORE_PLAN) {
                            if (lane_id == 0) {
                                export_plan[num_exports++] = {expert_local, best_target, q};
                            }
                        }
                        if (my_rank_0 == best_target) {
                            reg_slack_0 -= q;
                            reg_slots_0 += 1;
                        }
                        if (my_rank_1 == best_target) {
                            reg_slack_1 -= q;
                            reg_slots_1 += 1;
                        }
                        occ_set(local_occ_lo, local_occ_hi, best_target);
                        if (lane_id == 0) {
                            local_export_sum += q;
                            running_excess -= q;
                            running_slack -= q;
                        }

                        need -= q;
                        available -= q;
                    }
                }

                if (lane_id == 0) {
                    occ_lo[expert_local] = local_occ_lo;
                    occ_hi[expert_local] = local_occ_hi;
                    export_sum[expert_local] = local_export_sum;
                }
                __syncwarp();
            } else {
                int available = max(loads[expert_local] - keep_on_master - export_sum[expert_local], 0);

                while (need > 0 && available > 0) {
                    int effective_min_tokens = min_tokens_per_replica;
                    if (use_dynamic_q_floor) {
                        int local_feasible = 0;
                        for (int target_rank_local = lane_id; target_rank_local < G; target_rank_local += 32) {
                            if (slack[target_rank_local] > 0 && slots_used[target_rank_local] < num_local_redundant &&
                                !occ_has(occ_lo[expert_local], occ_hi[expert_local], target_rank_local) &&
                                min(min(need, slack[target_rank_local]), available) > 0) {
                                local_feasible += 1;
                            }
                        }
                        const int feasible_slots = warp_reduce_sum(local_feasible);
                        if (feasible_slots <= 0) {
                            break;
                        }
                        effective_min_tokens = max(1, (need + feasible_slots - 1) / feasible_slots);
                        if (lane_id == 0) record_floor(threshold, min_tokens_per_replica, effective_min_tokens, need, feasible_slots);
                    }

                    const int best_target = warp_find_best_target(slack,
                                                                  slots_used,
                                                                  occ_lo,
                                                                  occ_hi,
                                                                  expert_local,
                                                                  need,
                                                                  available,
                                                                  effective_min_tokens,
                                                                  num_local_redundant,
                                                                  G,
                                                                  lane_id);
                    if (best_target < 0) {
                        break;
                    }

                    if constexpr (STORE_PLAN) {
                        int can_store = 1;
                        if (lane_id == 0 && num_exports >= MAX_REPLICAS_PER_NVL) {
                            can_store = 0;
                        }
                        can_store = __shfl_sync(FULL_WARP_MASK, can_store, 0);
                        if (!can_store) {
                            return false;
                        }
                    }

                    const int q = min(min(need, slack[best_target]), available);
                    if (q < effective_min_tokens) {
                        break;
                    }
                    if (lane_id == 0) {
                        if constexpr (STORE_PLAN) {
                            export_plan[num_exports++] = {expert_local, best_target, q};
                        }
                        export_sum[expert_local] += q;
                        slack[best_target] -= q;
                        slots_used[best_target] += 1;
                        occ_set(occ_lo[expert_local], occ_hi[expert_local], best_target);
                        running_excess -= q;
                        running_slack -= q;
                    }
                    __syncwarp();

                    need -= q;
                    available -= q;
                }
            }

            if (need == 0) {
                break;
            }
        }

        if (need > 0) {
            return false;
        }
        int early_exit = 0;
        if (lane_id == 0 && running_excess > running_slack) {
            early_exit = 1;
        }
        early_exit = __shfl_sync(FULL_WARP_MASK, early_exit, 0);
        if (early_exit) {
            return false;
        }
    }

    return true;
}


struct Solver {
 int G,E,num_local_master,num_local_redundant,num_local_physical;
 int domain_start_rank=0,domain_start_log=0,max_replicas_dim=72;
 float balance_threshold,oracle_eps;
 int min_tokens_per_replica;
 bool allow_zero_master_quota,enable_v4a=true;
 bool use_fast_t_oracle=true,use_dynamic_q_floor=true;
 int oracle_batch_k=1;
 uint64_t smem_warp_occ_lo_base[4*512]{},smem_warp_occ_hi_base[4*512]{};
 int p2l_map[512+72*512]{},l2p_map[512*72]{},quota[512*72]{},quota_prefix[512*72]{},lcnts[512]{};
    __shared__ int32_t smem_loads[MAX_EXPERTS_PER_NVL];
    __shared__ int32_t smem_c[MAX_EXPERTS_PER_NVL];
    __shared__ int32_t smem_rank_load[MAX_GPUS_PER_NVL];
    __shared__ int32_t smem_rank_phys_base[MAX_GPUS_PER_NVL];
    __shared__ int32_t smem_my_loads[MAX_EXPERTS_PER_NVL];
    __shared__ int smem_sorted_experts[MAX_EXPERTS_PER_NVL];
    __shared__ int smem_presorted_source[MAX_GPUS_PER_NVL];
    __shared__ ExportPlanEntry smem_export_plan[MAX_REPLICAS_PER_NVL];
    __shared__ int smem_num_exports;
    __shared__ volatile int smem_tma_wait_done;
    __shared__ int smem_next_slot[MAX_GPUS_PER_NVL];
    __shared__ int smem_expert_slot[MAX_EXPERTS_PER_NVL];

    __shared__ int smem_bs_lo;
    __shared__ int smem_bs_hi;
    __shared__ bool smem_precheck_done;
    __shared__ int smem_fast_plan_done;
    __shared__ int smem_probes[QUOTA_SOLVER_WARPS];
    __shared__ int smem_probe_valid[QUOTA_SOLVER_WARPS];
    __shared__ int smem_probe_feasible[QUOTA_SOLVER_WARPS];
    __shared__ int smem_probe_small_range;

    __shared__ int32_t smem_warp_export_sum[QUOTA_SOLVER_WARPS][MAX_EXPERTS_PER_NVL];
    __shared__ int32_t smem_warp_excess[QUOTA_SOLVER_WARPS][MAX_GPUS_PER_NVL];
    __shared__ int32_t smem_warp_slack[QUOTA_SOLVER_WARPS][MAX_GPUS_PER_NVL];
    __shared__ int32_t smem_warp_slots_used[QUOTA_SOLVER_WARPS][MAX_GPUS_PER_NVL];

 void run(int thread_id){
  cpu_tid=thread_id;const int tid=thread_id,warp_id=tid/32,lane_id=tid%32;
    const bool do_binary_search = (num_local_redundant > 0 && G > 1);
    if (enable_v4a) {
        if (tid == 0) {
            smem_num_exports = 0;
            if (do_binary_search) {
                smem_fast_plan_done = 0;
                int total_rank_load = 0;
                int max_rank_load = 0;
                for (int r = 0; r < G; ++r) {
                    total_rank_load += smem_rank_load[r];
                    max_rank_load = max(max_rank_load, static_cast<int>(smem_rank_load[r]));
                }
                const float bt = fmaxf(balance_threshold, 1.0f);
                smem_bs_lo = static_cast<int>(ceilf((static_cast<float>(total_rank_load) / G) * bt));
                smem_bs_hi = max(max_rank_load, smem_bs_lo);
                smem_precheck_done = false;
            }
        }
        __syncthreads();
    } else {
        __syncthreads();
        if (tid == 0) {
            smem_num_exports = 0;
        }
        __syncthreads();
    }

    if (do_binary_search) {
        if (!enable_v4a) {
            if (tid == 0) {
                smem_fast_plan_done = 0;
                int total_rank_load = 0;
                int max_rank_load = 0;
                for (int r = 0; r < G; ++r) {
                    total_rank_load += smem_rank_load[r];
                    max_rank_load = max(max_rank_load, static_cast<int>(smem_rank_load[r]));
                }
                const float bt = fmaxf(balance_threshold, 1.0f);
                smem_bs_lo = static_cast<int>(ceilf((static_cast<float>(total_rank_load) / G) * bt));
                smem_bs_hi = max(max_rank_load, smem_bs_lo);
                smem_precheck_done = false;
            }
            __syncthreads();
        }

        if (use_fast_t_oracle) {
            int fast_threshold = smem_bs_lo;
            if (warp_id == 0) {
                if (lane_id == 0) {
                    const float eps = fmaxf(oracle_eps, 0.0f);
                    fast_threshold = static_cast<int>(ceilf(static_cast<float>(smem_bs_lo) * (1.0f + eps)));
                    fast_threshold = max(fast_threshold, smem_bs_lo);
                }
                fast_threshold = __shfl_sync(FULL_WARP_MASK, fast_threshold, 0);
            }
            if (warp_id == 0) {
                const int fast_step = max(1, (smem_bs_hi + 99) / 100);
                bool feasible_fast = false;
                for (int retry = 0; retry <= QUOTA_ORACLE_FAST_MAX_RETRY && !feasible_fast; ++retry) {
                    warp_init_oracle_state_parallel(smem_warp_export_sum[0],
                                                    smem_warp_occ_lo_base,
                                                    smem_warp_occ_hi_base,
                                                    smem_warp_excess[0],
                                                    smem_warp_slack[0],
                                                    smem_warp_slots_used[0],
                                                    smem_rank_load,
                                                    fast_threshold,
                                                    E,
                                                    G,
                                                    num_local_master,
                                                    lane_id);
                    __syncwarp();

                    int fast_exports = 0;
                    feasible_fast = warp_build_export_plan<true>(smem_loads,
                                                                 smem_sorted_experts,
                                                                 smem_warp_export_sum[0],
                                                                 smem_warp_excess[0],
                                                                 smem_warp_slack[0],
                                                                 smem_warp_slots_used[0],
                                                                 smem_rank_load,
                                                                 smem_presorted_source,
                                                                 smem_warp_occ_lo_base,
                                                                 smem_warp_occ_hi_base,
                                                                 smem_export_plan,
                                                                 fast_exports,
                                                                 fast_threshold,
                                                                 G,
                                                                 num_local_master,
                                                                 num_local_redundant,
                                                                 min_tokens_per_replica,
                                                                 allow_zero_master_quota,
                                                                 lane_id,
                                                                 use_dynamic_q_floor,
                                                                 oracle_batch_k);
                    if (lane_id == 0) {
                        if (feasible_fast) {
                            smem_num_exports = fast_exports;
                            smem_fast_plan_done = 1;
                            smem_bs_lo = fast_threshold;
                        } else {
                            fast_threshold = min(smem_bs_hi, fast_threshold + fast_step);
                        }
                    }
                    fast_threshold = __shfl_sync(FULL_WARP_MASK, fast_threshold, 0);
                }
            }
            __syncthreads();
        }
        if (!smem_fast_plan_done) {
            if (warp_id == 0) {
                int coarse_lo = smem_bs_lo;
                int coarse_hi = smem_bs_hi;
                while (coarse_lo < coarse_hi) {
                    const int probe = coarse_lo + ((coarse_hi - coarse_lo) >> 1);
                    const bool feasible = warp_capacity_feasible(smem_rank_load, probe, G, lane_id);
                    if (lane_id == 0) {
                        if (feasible) {
                            coarse_hi = probe;
                        } else {
                            coarse_lo = probe + 1;
                        }
                    }
                    coarse_lo = __shfl_sync(FULL_WARP_MASK, coarse_lo, 0);
                    coarse_hi = __shfl_sync(FULL_WARP_MASK, coarse_hi, 0);
                }
                if (lane_id == 0) {
                    smem_bs_lo = coarse_lo;
                }
                __syncwarp();

                warp_init_oracle_state_parallel(smem_warp_export_sum[0],
                                                smem_warp_occ_lo_base,
                                                smem_warp_occ_hi_base,
                                                smem_warp_excess[0],
                                                smem_warp_slack[0],
                                                smem_warp_slots_used[0],
                                                smem_rank_load,
                                                smem_bs_lo,
                                                E,
                                                G,
                                                num_local_master,
                                                lane_id);
                __syncwarp();

                int precheck_exports = 0;
                const bool precheck_feasible = warp_build_export_plan<true>(smem_loads,
                                                                            smem_sorted_experts,
                                                                            smem_warp_export_sum[0],
                                                                            smem_warp_excess[0],
                                                                            smem_warp_slack[0],
                                                                            smem_warp_slots_used[0],
                                                                            smem_rank_load,
                                                                            smem_presorted_source,
                                                                            smem_warp_occ_lo_base,
                                                                            smem_warp_occ_hi_base,
                                                                            smem_export_plan,
                                                                            precheck_exports,
                                                                            smem_bs_lo,
                                                                            G,
                                                                            num_local_master,
                                                                            num_local_redundant,
                                                                            min_tokens_per_replica,
                                                                            allow_zero_master_quota,
                                                                            lane_id,
                                                                            false,
                                                                            1);
                if (lane_id == 0) {
                    smem_precheck_done = precheck_feasible;
                    if (precheck_feasible) {
                        smem_num_exports = precheck_exports;
                    } else {
                        smem_bs_lo = min(smem_bs_lo + 1, smem_bs_hi);
                    }
                }
            }
            __syncthreads();

            while (true) {
                if (smem_precheck_done || smem_bs_lo >= smem_bs_hi) {
                    break;
                }

                if (tid == 0) {
                    const int range = smem_bs_hi - smem_bs_lo;
                    smem_probe_small_range = (range <= QUOTA_SOLVER_WARPS) ? 1 : 0;
                    if (smem_probe_small_range) {
                        for (int w = 0; w < QUOTA_SOLVER_WARPS; ++w) {
                            smem_probes[w] = smem_bs_lo + w;
                            smem_probe_valid[w] = (smem_probes[w] < smem_bs_hi) ? 1 : 0;
                            smem_probe_feasible[w] = 0;
                        }
                    } else {
                        for (int w = 0; w < QUOTA_SOLVER_WARPS; ++w) {
                            smem_probes[w] = smem_bs_lo +
                                static_cast<int>((static_cast<int64_t>(range) * (w + 1)) / (QUOTA_SOLVER_WARPS + 1));
                            smem_probe_valid[w] = 1;
                            smem_probe_feasible[w] = 0;
                        }
                    }
                }
                __syncthreads();

                bool feasible = false;
                if (smem_probe_valid[warp_id]) {
                    warp_init_oracle_state_parallel(smem_warp_export_sum[warp_id],
                                                    smem_warp_occ_lo_base + warp_id * E,
                                                    smem_warp_occ_hi_base + warp_id * E,
                                                    smem_warp_excess[warp_id],
                                                    smem_warp_slack[warp_id],
                                                    smem_warp_slots_used[warp_id],
                                                    smem_rank_load,
                                                    smem_probes[warp_id],
                                                    E,
                                                    G,
                                                    num_local_master,
                                                    lane_id);
                    __syncwarp();

                    int dummy_exports = 0;
                    feasible = warp_build_export_plan<false>(smem_loads,
                                                             smem_sorted_experts,
                                                             smem_warp_export_sum[warp_id],
                                                             smem_warp_excess[warp_id],
                                                             smem_warp_slack[warp_id],
                                                             smem_warp_slots_used[warp_id],
                                                             smem_rank_load,
                                                             smem_presorted_source,
                                                             smem_warp_occ_lo_base + warp_id * E,
                                                             smem_warp_occ_hi_base + warp_id * E,
                                                             nullptr,
                                                             dummy_exports,
                                                             smem_probes[warp_id],
                                                             G,
                                                             num_local_master,
                                                             num_local_redundant,
                                                             min_tokens_per_replica,
                                                             allow_zero_master_quota,
                                                             lane_id,
                                                             false,
                                                             1);
                }
                if (lane_id == 0) {
                    smem_probe_feasible[warp_id] = feasible ? 1 : 0;
                }
                __syncthreads();

                if (tid == 0) {
                    if (smem_probe_small_range) {
                        int best_probe = -1;
                        for (int w = 0; w < QUOTA_SOLVER_WARPS; ++w) {
                            if (smem_probe_valid[w] && smem_probe_feasible[w]) {
                                best_probe = smem_probes[w];
                                break;
                            }
                        }
                        if (best_probe >= 0) {
                            smem_bs_lo = best_probe;
                            smem_bs_hi = best_probe;
                        } else {
                            smem_bs_lo = smem_bs_hi;
                        }
                    } else {
                        int first_feasible = -1;
                        for (int w = 0; w < QUOTA_SOLVER_WARPS; ++w) {
                            if (smem_probe_feasible[w]) {
                                first_feasible = w;
                                break;
                            }
                        }
                        if (first_feasible >= 0) {
                            smem_bs_hi = smem_probes[first_feasible];
                            if (first_feasible > 0) {
                                smem_bs_lo = smem_probes[first_feasible - 1] + 1;
                            }
                        } else {
                            smem_bs_lo = smem_probes[QUOTA_SOLVER_WARPS - 1] + 1;
                        }
                    }
                }
                __syncthreads();
            }

            if (!smem_precheck_done) {
                if (warp_id == 0) {
                    warp_init_oracle_state_parallel(smem_warp_export_sum[0],
                                                    smem_warp_occ_lo_base,
                                                    smem_warp_occ_hi_base,
                                                    smem_warp_excess[0],
                                                    smem_warp_slack[0],
                                                    smem_warp_slots_used[0],
                                                    smem_rank_load,
                                                    smem_bs_lo,
                                                    E,
                                                    G,
                                                    num_local_master,
                                                    lane_id);
                    __syncwarp();

                    int final_exports = 0;
                    const bool final_feasible = warp_build_export_plan<true>(smem_loads,
                                                                             smem_sorted_experts,
                                                                             smem_warp_export_sum[0],
                                                                             smem_warp_excess[0],
                                                                             smem_warp_slack[0],
                                                                             smem_warp_slots_used[0],
                                                                             smem_rank_load,
                                                                             smem_presorted_source,
                                                                             smem_warp_occ_lo_base,
                                                                             smem_warp_occ_hi_base,
                                                                             smem_export_plan,
                                                                             final_exports,
                                                                             smem_bs_lo,
                                                                             G,
                                                                             num_local_master,
                                                                             num_local_redundant,
                                                                             min_tokens_per_replica,
                                                                             allow_zero_master_quota,
                                                                             lane_id,
                                                                             false,
                                                                             1);
                    if (lane_id == 0) {
                        EP_DEVICE_ASSERT(final_feasible);
                        smem_num_exports = final_exports;
                    }
                }
                __syncthreads();
            }
        }
    }

    const int32_t* final_export_sum = smem_warp_export_sum[0];
    for (int r = tid; r < G; r += blockDim.x) {
        smem_next_slot[r] = 0;
    }
    for (int expert_local = tid; expert_local < E; expert_local += blockDim.x) {
        const int l_global = domain_start_log + expert_local;
        const int row_offset = l_global * max_replicas_dim;
        const int master_quota =
            do_binary_search ? (smem_loads[expert_local] - final_export_sum[expert_local]) : smem_loads[expert_local];
        quota[row_offset] = master_quota;
        smem_expert_slot[expert_local] = 1;
    }
    __syncthreads();

    if (tid == 0) {
        for (int plan_idx = 0; plan_idx < smem_num_exports; ++plan_idx) {
            const ExportPlanEntry entry = smem_export_plan[plan_idx];
            const int expert_local = entry.expert_local;
            const int l_global = domain_start_log + expert_local;
            const int row_offset = l_global * max_replicas_dim;
            const int slot = smem_expert_slot[expert_local]++;
            const int target_local = entry.target_rank_local;
            const int phys_base = enable_v4a
                ? smem_rank_phys_base[target_local]
                : ((domain_start_rank + target_local) * num_local_physical + num_local_master);
            const int phys_idx = phys_base + smem_next_slot[target_local]++;
            p2l_map[phys_idx] = l_global;
            l2p_map[row_offset + slot] = phys_idx;
            quota[row_offset + slot] = entry.quota;
        }
    }
    __syncthreads();

    for (int expert_local = tid; expert_local < E; expert_local += blockDim.x) {
        const int l_global = domain_start_log + expert_local;
        const int row_offset = l_global * max_replicas_dim;
        const int C = smem_expert_slot[expert_local];
        smem_c[expert_local] = C;
        lcnts[l_global] = C;

        int prefix = 0;
        for (int j = 0; j < C; ++j) {
            prefix += quota[row_offset + j];
            quota_prefix[row_offset + j] = prefix;
        }
    }
    __syncthreads();


 }
};
int main(){
 Solver s{};
 int zero,stage;
 if(!(std::cin>>s.G>>s.num_local_master>>s.num_local_redundant>>s.balance_threshold>>s.min_tokens_per_replica>>zero>>s.oracle_eps>>stage))return 2;
 s.E=s.G*s.num_local_master;s.num_local_physical=s.num_local_master+s.num_local_redundant;
 if(s.G<1||s.G>72||s.E<1||s.E>512||s.num_local_redundant<0||s.num_local_redundant>512||s.min_tokens_per_replica<1)return 2;
 s.allow_zero_master_quota=zero;s.enable_v4a=stage>=1;
 // Host input setup only. Expert and rank orders exactly follow the original
 // descending-load, ascending-ID comparisons at placement.cu:63-75,897-923.
 for(int e=0;e<s.E;++e){std::cin>>s.smem_loads[e];if(s.smem_loads[e]<0)return 2;s.smem_c[e]=1;s.smem_rank_load[e/s.num_local_master]+=s.smem_loads[e];
  int p=(e/s.num_local_master)*s.num_local_physical+e%s.num_local_master;s.p2l_map[p]=e;s.l2p_map[e*72]=p;
 }
 for(int r=0;r<s.G;++r){
  s.smem_presorted_source[r]=r;s.smem_rank_phys_base[r]=r*s.num_local_physical+s.num_local_master;
  auto start=s.smem_sorted_experts+r*s.num_local_master;
  for(int m=0;m<s.num_local_master;++m)start[m]=r*s.num_local_master+m;
  std::sort(start,start+s.num_local_master,[&](int a,int b){return s.smem_loads[a]!=s.smem_loads[b]?s.smem_loads[a]>s.smem_loads[b]:a<b;});
 }
 std::sort(s.smem_presorted_source,s.smem_presorted_source+s.G,[&](int a,int b){return s.smem_rank_load[a]!=s.smem_rank_load[b]?s.smem_rank_load[a]>s.smem_rank_load[b]:a<b;});
 std::vector<std::thread> threads;
 for(int t=0;t<128;++t)threads.emplace_back([&,t]{s.run(t);});
 for(auto& t:threads)t.join();
 std::cout<<"{\"threshold\":"<<s.smem_bs_lo<<",\"fast_success\":"<<s.smem_fast_plan_done<<",\"precheck_success\":"<<s.smem_precheck_done<<",\"replica_count\":"<<s.smem_num_exports<<",\"physical\":[";
 bool first=true;
 for(int e=0;e<s.E;++e)for(int j=0;j<s.lcnts[e];++j){
  if(!first)std::cout<<',';first=false;int pid=s.l2p_map[e*72+j];
  std::cout<<"{\"expert\":"<<e<<",\"id\":"<<pid<<",\"rank\":"<<pid/s.num_local_physical<<",\"quota\":"<<s.quota[e*72+j]<<",\"kind\":\""<<(j==0?"main":"replica")<<"\"}";
 }
 std::cout<<"],\"probes\":[";first=true;
 // Probe order within a parallel four-warp round is nondeterministic; retain
 // values and phase, and canonicalize in the Python evidence consumer.
 for(auto p:trace){if(!first)std::cout<<',';first=false;std::cout<<"{\"threshold\":"<<p.threshold<<",\"dynamic\":"<<p.dynamic<<",\"store\":"<<p.store<<"}";}
 std::cout<<"],\"dynamic_floors\":[";first=true;
 for(auto f:floors){if(!first)std::cout<<',';first=false;std::cout<<"{\"threshold\":"<<f.threshold<<",\"configured\":"<<f.configured<<",\"effective\":"<<f.effective<<",\"need\":"<<f.need<<",\"feasible_slots\":"<<f.feasible_slots<<"}";}
 std::cout<<"]}\n";
}
