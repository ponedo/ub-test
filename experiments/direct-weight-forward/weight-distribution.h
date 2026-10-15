// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <cstdint>
#include <vector>
#include <stdexcept>
struct PhysicalExpert {
    uint32_t id, expert, rank, replica, quota, mainId, mainRank;
};
enum class WeightReadyScope { FullExpert, Chunk };
struct WeightEdge { uint32_t sourcePhysical, targetPhysical, offset, bytes; WeightReadyScope sourceDependency; };
enum class WeightStrategyKind { Direct=0, TwoStageRelay=1, ChunkStreamingRelay=2 };
class WeightDistributionStrategy {
public:
    virtual ~WeightDistributionStrategy()=default;
    virtual std::vector<WeightEdge> Edges(const std::vector<PhysicalExpert>& physical, uint32_t weightBytes) const=0;
};
class DirectWeightDistribution final : public WeightDistributionStrategy {
public:
    std::vector<WeightEdge> Edges(const std::vector<PhysicalExpert>& physical, uint32_t weightBytes) const override {
        std::vector<WeightEdge> result;
        for (const auto& p:physical) if(p.replica) result.push_back({p.mainId,p.id,0,weightBytes,WeightReadyScope::FullExpert});
        return result;
    }
};
// Future strategies must provide real forwarding/dependency behavior; unsupported
// enum values are rejected by this milestone, never aliased to Direct.
