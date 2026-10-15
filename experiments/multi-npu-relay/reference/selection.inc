// Extracted verbatim from Dots-Infra/UltraEP 94cab099b44fffa99a82fea99e7c12d89cf65e4f
            bool replica_selected[kMaxNvlDomainSize - 1] = {false};
            int relay_replica_indices[kMaxNvlDomainSize - 1] = {0};
            int relay_global_ranks[kMaxNvlDomainSize - 1] = {0};
            int relay_nvl_ranks[kMaxNvlDomainSize - 1] = {0};
            int relay_local_offsets[kMaxNvlDomainSize - 1] = {0};
            int relay_child_counts[kMaxNvlDomainSize - 1] = {0};
            int leaf_owner_relay[kMaxNvlDomainSize - 1];
            for (int replica_idx = 0; replica_idx < kMaxNvlDomainSize - 1; ++replica_idx) {
                leaf_owner_relay[replica_idx] = -1;
            }

            for (int relay_idx = 0; relay_idx < relay_count; ++relay_idx) {
                int best_replica_idx = -1;
                int best_rank_used_penalty = 2;
                int64_t best_sender_load = 0;
                int best_rank = 0;
                int best_nvl_rank = 0;
                int best_local_offset = 0;

                for (int replica_idx = 0; replica_idx < num_replicas; ++replica_idx) {
                    if (replica_selected[replica_idx]) {
                        continue;
                    }

                    const int replica_phy = l2p[logical_expert * max_rep_dim + replica_idx + 1];
                    const int replica_rank = replica_phy / num_local_physical;
                    const int replica_nvl_rank = replica_rank % num_nvl_ranks;
                    const int replica_local_offset = replica_phy % num_local_physical - num_local_master;

                    bool rank_used = false;
                    for (int prev = 0; prev < relay_idx; ++prev) {
                        if (relay_global_ranks[prev] == replica_rank) {
                            rank_used = true;
                            break;
                        }
                    }
                    const int rank_used_penalty = rank_used ? 1 : 0;
                    const int64_t candidate_sender_load = sender_load_bytes[replica_nvl_rank];

                    const bool is_better = best_replica_idx < 0 || rank_used_penalty < best_rank_used_penalty ||
                        (rank_used_penalty == best_rank_used_penalty &&
                         (candidate_sender_load < best_sender_load ||
                          (candidate_sender_load == best_sender_load &&
                           (replica_rank < best_rank ||
                            (replica_rank == best_rank && replica_idx < best_replica_idx)))));
                    if (!is_better) {
                        continue;
                    }

                    best_replica_idx = replica_idx;
                    best_rank_used_penalty = rank_used_penalty;
                    best_sender_load = candidate_sender_load;
                    best_rank = replica_rank;
                    best_nvl_rank = replica_nvl_rank;
                    best_local_offset = replica_local_offset;
                }

                if (best_replica_idx < 0) {
                    break;
                }

                replica_selected[best_replica_idx] = true;
                relay_replica_indices[relay_idx] = best_replica_idx;
                relay_global_ranks[relay_idx] = best_rank;
                relay_nvl_ranks[relay_idx] = best_nvl_rank;
                relay_local_offsets[relay_idx] = best_local_offset;
            }

            int leaf_replica_indices[kMaxNvlDomainSize - 1] = {0};
            int leaf_count = 0;
            for (int replica_idx = 0; replica_idx < num_replicas; ++replica_idx) {
                if (!replica_selected[replica_idx]) {
                    leaf_replica_indices[leaf_count++] = replica_idx;
                }
            }

            int64_t projected_relay_loads[kMaxNvlDomainSize - 1] = {0};
            for (int relay_idx = 0; relay_idx < relay_count; ++relay_idx) {
                projected_relay_loads[relay_idx] = sender_load_bytes[relay_nvl_ranks[relay_idx]];
            }

            for (int leaf_order = 0; leaf_order < leaf_count; ++leaf_order) {
                const int replica_idx = leaf_replica_indices[leaf_order];
                int owner_relay = -1;
                if (leaf_order < relay_count) {
                    owner_relay = leaf_order;
                } else {
                    for (int relay_idx = 0; relay_idx < relay_count; ++relay_idx) {
                        const bool is_better = owner_relay < 0 ||
                            projected_relay_loads[relay_idx] < projected_relay_loads[owner_relay] ||
                            (projected_relay_loads[relay_idx] == projected_relay_loads[owner_relay] &&
                             (relay_child_counts[relay_idx] < relay_child_counts[owner_relay] ||
                              (relay_child_counts[relay_idx] == relay_child_counts[owner_relay] &&
                               (relay_global_ranks[relay_idx] < relay_global_ranks[owner_relay] ||
                                (relay_global_ranks[relay_idx] == relay_global_ranks[owner_relay] &&
                                 relay_replica_indices[relay_idx] < relay_replica_indices[owner_relay])))));
                        if (is_better) {
                            owner_relay = relay_idx;
                        }
                    }
                }

                if (owner_relay < 0) {
                    continue;
                }

                leaf_owner_relay[replica_idx] = owner_relay;
                relay_child_counts[owner_relay] += 1;
                projected_relay_loads[owner_relay] += weight_bytes_per_expert;
            }

            sender_load_bytes[domain_nvl_rank] += static_cast<int64_t>(relay_count) * weight_bytes_per_expert;
            for (int relay_idx = 0; relay_idx < relay_count; ++relay_idx) {
                sender_load_bytes[relay_nvl_ranks[relay_idx]] +=
                    static_cast<int64_t>(relay_child_counts[relay_idx]) * weight_bytes_per_expert;
            }

