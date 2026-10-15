#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
using std::min;using std::max;
#define __device__
#define __noinline__
#define __forceinline__ inline
#define EP_DEVICE_ASSERT(x) do {if(!(x))throw std::runtime_error("reference assertion");}while(0)
constexpr int MAX_GPUS_PER_NVL=72,QUOTA_FAST_REPLICA_LIMIT=8;
__device__ __noinline__ void build_rank_quota_prefix_slow(int expert_local,
                                                          int row_offset,
                                                          int C,
                                                          const int32_t* smem_my_loads,
                                                          const int32_t* smem_domain_loads,
                                                          int stride_elems,
                                                          int domain_start_rank,
                                                          int num_local_physical,
                                                          int my_rank,
                                                          int G,
                                                          bool locality_aware,
                                                          const int32_t* quota,
                                                          const int32_t* l2p_map,
                                                          int32_t* rank_quota_prefix) {
    int host_rank[MAX_GPUS_PER_NVL];
    int my_alloc[MAX_GPUS_PER_NVL];
    int64_t remainders[MAX_GPUS_PER_NVL];

    for (int j = 0; j < C; ++j) {
        host_rank[j] = l2p_map[row_offset + j] / num_local_physical;
        my_alloc[j] = 0;
        remainders[j] = -1;
    }

    if (!locality_aware) {
        const int rem_my = smem_my_loads[expert_local];
        int assigned = 0;
        int total_quota = 0;
        for (int j = 0; j < C; ++j) {
            total_quota += quota[row_offset + j];
        }
        if (rem_my > 0 && total_quota > 0) {
            for (int j = 0; j < C; ++j) {
                const int64_t scaled = static_cast<int64_t>(rem_my) * quota[row_offset + j];
                const int share = static_cast<int>(scaled / total_quota);
                my_alloc[j] = share;
                remainders[j] = scaled % total_quota;
                assigned += share;
            }
            int remaining = rem_my - assigned;
            while (remaining > 0) {
                int best_j = -1;
                for (int j = 0; j < C; ++j) {
                    if (best_j < 0 || remainders[j] > remainders[best_j] ||
                        (remainders[j] == remainders[best_j] && j < best_j)) {
                        best_j = j;
                    }
                }
                EP_DEVICE_ASSERT(best_j >= 0);
                my_alloc[best_j] += 1;
                remainders[best_j] = -1;
                --remaining;
            }
        }
    } else {
        int host_remaining[MAX_GPUS_PER_NVL];
        int remote_cap[MAX_GPUS_PER_NVL];

        for (int r = 0; r < G; ++r) {
            host_remaining[r] = smem_domain_loads[r * stride_elems + expert_local];
        }

        int rem_my = smem_my_loads[expert_local];
        int total_remote_cap = 0;
        for (int j = 0; j < C; ++j) {
            const int q = quota[row_offset + j];
            const int host_local = host_rank[j] - domain_start_rank;
            EP_DEVICE_ASSERT(host_local >= 0 && host_local < G);
            const int local_fill = min(host_remaining[host_local], q);
            host_remaining[host_local] -= local_fill;
            remote_cap[j] = q - local_fill;
            total_remote_cap += remote_cap[j];
            if (host_rank[j] == my_rank) {
                my_alloc[j] += local_fill;
                rem_my -= local_fill;
            }
        }
        rem_my = max(rem_my, 0);

        if (rem_my > 0 && total_remote_cap > 0) {
            int assigned = 0;
            for (int j = 0; j < C; ++j) {
                if (host_rank[j] == my_rank || remote_cap[j] <= 0) {
                    continue;
                }
                const int64_t scaled = static_cast<int64_t>(rem_my) * remote_cap[j];
                const int share = static_cast<int>(scaled / total_remote_cap);
                my_alloc[j] += share;
                remainders[j] = scaled % total_remote_cap;
                assigned += share;
            }
            int remaining = rem_my - assigned;
            while (remaining > 0) {
                int best_j = -1;
                for (int j = 0; j < C; ++j) {
                    if (host_rank[j] == my_rank || remote_cap[j] <= 0) {
                        continue;
                    }
                    if (best_j < 0 || remainders[j] > remainders[best_j] ||
                        (remainders[j] == remainders[best_j] &&
                         (host_rank[j] < host_rank[best_j] || (host_rank[j] == host_rank[best_j] && j < best_j)))) {
                        best_j = j;
                    }
                }
                EP_DEVICE_ASSERT(best_j >= 0);
                my_alloc[best_j] += 1;
                remainders[best_j] = -1;
                --remaining;
            }
        }
    }

    int prefix = 0;
    for (int j = 0; j < C; ++j) {
        prefix += my_alloc[j];
        rank_quota_prefix[row_offset + j] = prefix;
    }
}
__device__ __noinline__ void build_rank_quota_prefix_fast(int expert_local,
                                                          int row_offset,
                                                          int C,
                                                          const int32_t* smem_my_loads,
                                                          const int32_t* smem_domain_loads,
                                                          int stride_elems,
                                                          int domain_start_rank,
                                                          int num_local_physical,
                                                          int my_rank,
                                                          int G,
                                                          bool locality_aware,
                                                          const int32_t* quota,
                                                          const int32_t* l2p_map,
                                                          int32_t* rank_quota_prefix) {
            int host_rank[QUOTA_FAST_REPLICA_LIMIT];
            int my_alloc[QUOTA_FAST_REPLICA_LIMIT];
            int64_t remainders[QUOTA_FAST_REPLICA_LIMIT];
            for (int j = 0; j < C; ++j) {
                const int phys_idx = l2p_map[row_offset + j];
                host_rank[j] = phys_idx / num_local_physical;
                my_alloc[j] = 0;
                remainders[j] = -1;
            }

            if (!locality_aware) {
                const int rem_my = smem_my_loads[expert_local];
                int assigned = 0;
                int total_quota = 0;
                for (int j = 0; j < C; ++j) {
                    total_quota += quota[row_offset + j];
                }
                if (rem_my > 0 && total_quota > 0) {
                    for (int j = 0; j < C; ++j) {
                        const int64_t scaled = static_cast<int64_t>(rem_my) * quota[row_offset + j];
                        const int share = static_cast<int>(scaled / total_quota);
                        my_alloc[j] = share;
                        remainders[j] = scaled % total_quota;
                        assigned += share;
                    }
                    int remaining = rem_my - assigned;
                    while (remaining > 0) {
                        int best_j = -1;
                        for (int j = 0; j < C; ++j) {
                            if (best_j < 0 || remainders[j] > remainders[best_j] ||
                                (remainders[j] == remainders[best_j] && j < best_j)) {
                                best_j = j;
                            }
                        }
                        EP_DEVICE_ASSERT(best_j >= 0);
                        my_alloc[best_j] += 1;
                        remainders[best_j] = -1;
                        --remaining;
                    }
                }
            } else {
                int remote_cap[QUOTA_FAST_REPLICA_LIMIT];
                int host_local_ids[QUOTA_FAST_REPLICA_LIMIT];
                int host_remaining[QUOTA_FAST_REPLICA_LIMIT];
                int num_hosts = 0;

                int rem_my = smem_my_loads[expert_local];
                int total_remote_cap = 0;
                for (int j = 0; j < C; ++j) {
                    const int q = quota[row_offset + j];
                    const int host_local = host_rank[j] - domain_start_rank;
                    EP_DEVICE_ASSERT(host_local >= 0 && host_local < G);

                    int host_slot = -1;
                    for (int u = 0; u < num_hosts; ++u) {
                        if (host_local_ids[u] == host_local) {
                            host_slot = u;
                            break;
                        }
                    }
                    if (host_slot < 0) {
                        EP_DEVICE_ASSERT(num_hosts < QUOTA_FAST_REPLICA_LIMIT);
                        host_slot = num_hosts;
                        host_local_ids[num_hosts] = host_local;
                        host_remaining[num_hosts] = smem_domain_loads[host_local * stride_elems + expert_local];
                        ++num_hosts;
                    }

                    const int local_fill = min(host_remaining[host_slot], q);
                    host_remaining[host_slot] -= local_fill;
                    remote_cap[j] = q - local_fill;
                    total_remote_cap += remote_cap[j];
                    if (host_rank[j] == my_rank) {
                        my_alloc[j] += local_fill;
                        rem_my -= local_fill;
                    }
                }
                rem_my = max(rem_my, 0);

                if (rem_my > 0 && total_remote_cap > 0) {
                    int assigned = 0;
                    for (int j = 0; j < C; ++j) {
                        if (host_rank[j] == my_rank || remote_cap[j] <= 0) {
                            continue;
                        }
                        const int64_t scaled = static_cast<int64_t>(rem_my) * remote_cap[j];
                        const int share = static_cast<int>(scaled / total_remote_cap);
                        my_alloc[j] += share;
                        remainders[j] = scaled % total_remote_cap;
                        assigned += share;
                    }
                    int remaining = rem_my - assigned;
                    while (remaining > 0) {
                        int best_j = -1;
                        for (int j = 0; j < C; ++j) {
                            if (host_rank[j] == my_rank || remote_cap[j] <= 0) {
                                continue;
                            }
                            if (best_j < 0 || remainders[j] > remainders[best_j] ||
                                (remainders[j] == remainders[best_j] &&
                                 (host_rank[j] < host_rank[best_j] ||
                                  (host_rank[j] == host_rank[best_j] && j < best_j)))) {
                                best_j = j;
                            }
                        }
                        EP_DEVICE_ASSERT(best_j >= 0);
                        my_alloc[best_j] += 1;
                        remainders[best_j] = -1;
                        --remaining;
                    }
                }
            }

            int prefix = 0;
            for (int j = 0; j < C; ++j) {
                prefix += my_alloc[j];
                rank_quota_prefix[row_offset + j] = prefix;
            }
        }
__device__ __forceinline__ int sparse_quota_replica_index(const int local_ordinal,
                                                          const int logical_id,
                                                          const int replica_count,
                                                          const int max_replicas,
                                                          const int32_t* __restrict__ rank_quota_prefix) {
    constexpr int PREFETCH_REPLICAS = 8;
    const int row_offset = logical_id * max_replicas;
    const int prefetch_count = min(replica_count, PREFETCH_REPLICAS);
    int replica_idx = 0;
    int local_prefix[PREFETCH_REPLICAS];

#pragma unroll
    for (int j = 0; j < PREFETCH_REPLICAS; ++j) {
        local_prefix[j] = (j < prefetch_count) ? rank_quota_prefix[row_offset + j] : 0;
    }

#pragma unroll
    for (int j = 0; j < PREFETCH_REPLICAS; ++j) {
        if (j < prefetch_count) {
            replica_idx += (local_ordinal >= local_prefix[j]) ? 1 : 0;
        }
    }
    for (int j = PREFETCH_REPLICAS; j < replica_count; ++j) {
        replica_idx += (local_ordinal >= rank_quota_prefix[row_offset + j]) ? 1 : 0;
    }
    return min(replica_idx, max(replica_count - 1, 0));
}

int main(){int G,C,local;while(std::cin>>G>>C>>local){
 if(G<1||G>72||C<1||C>72)return 2;
 std::vector<int32_t>d(G),h(C),q(C);for(auto&x:d)std::cin>>x;for(auto&x:h)std::cin>>x;for(auto&x:q)std::cin>>x;
 for(int mode=0;mode<2;++mode){if(mode==1&&C>8)continue;
 for(int r=0;r<G;++r){std::vector<int32_t>out(C);
 auto fn=mode?build_rank_quota_prefix_fast:build_rank_quota_prefix_slow;
 fn(0,0,C,&d[r],d.data(),1,0,1,r,G,local,q.data(),h.data(),out.data());
 int prev=0;for(int j=0;j<C;++j){std::cout<<(out[j]-prev)<<' ';prev=out[j];}std::cout<<'\n';
 // Execute the exact upstream ordinal lookup too, checking it reproduces the row.
 std::vector<int>counts(C);for(int z=0;z<d[r];++z)++counts[sparse_quota_replica_index(z,0,C,C,out.data())];
 prev=0;for(int j=0;j<C;++j){if(counts[j]!=out[j]-prev)return 3;prev=out[j];}
 }}
}return 0;}
