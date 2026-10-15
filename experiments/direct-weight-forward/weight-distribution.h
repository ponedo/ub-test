// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <tuple>
#include <vector>
struct PhysicalExpert {
    uint32_t id, expert, rank, replica, quota, mainId, mainRank;
};
// GroupChunk waits for every main-to-relay edge in the same expert/range fan-out.
enum class WeightReadyScope { FullExpert, Chunk, GroupChunk };
struct WeightEdge { uint32_t sourcePhysical, targetPhysical, offset, bytes; WeightReadyScope sourceDependency; };
enum class WeightStrategyKind { Direct=0, TwoStageRelay=1, ChunkStreamingRelay=2 };
struct WeightDistributionOptions {
    uint32_t nodes=0, chunkBytes=262144, minReplicas=4, maxRelays=8, minFanoutGain=2;
    bool forceRelay=false;
    // Global offsets partitioning fused FC1 and FC2. Zero means one opaque shard.
    uint32_t shardCut=0;
    // One scale-up domain; all endpoint pairs reachable through the fixed switch.
    std::vector<uint32_t> domain;
};
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
// Port of fixed UltraEP weight_sync.cu selection/grouping, not a placement solver.
// Input replica order must be the accepted Planner's original l2p ordinal order.
class RelayWeightDistribution : public WeightDistributionStrategy {
protected:
    WeightDistributionOptions options;
    bool streaming;
    RelayWeightDistribution(WeightDistributionOptions o, bool s):options(std::move(o)),streaming(s) {}
public:
    std::vector<WeightEdge> Edges(const std::vector<PhysicalExpert>& physical, uint32_t bytes) const override {
        const auto& o=options;
        if(!o.nodes || !bytes || !o.chunkBytes || !o.maxRelays || o.shardCut>=bytes)
            throw std::invalid_argument("invalid weight graph parameters");
        if(!o.domain.empty() && (o.domain.size()!=o.nodes ||
           !std::all_of(o.domain.begin(),o.domain.end(),[&](auto d){return d==o.domain[0];})))
            throw std::invalid_argument("relay requires one connected scale-up domain");
        std::vector<PhysicalExpert> mains;
        std::map<uint32_t,std::vector<PhysicalExpert>> replicas;
        std::set<uint32_t> ids;
        for(auto p:physical) {
            if(p.rank>=o.nodes || !ids.insert(p.id).second) throw std::invalid_argument("graph identity");
            if(p.replica) replicas[p.expert].push_back(p); else mains.push_back(p);
        }
        std::sort(mains.begin(),mains.end(),[](auto a,auto b){return std::tie(a.rank,a.id)<std::tie(b.rank,b.id);});
        std::vector<uint64_t> load(o.nodes,0);
        std::vector<WeightEdge> result;
        for(auto main:mains) {
            auto& reps=replicas[main.expert];uint32_t count=reps.size();
            if(!count) continue;
            for(auto p:reps) if(p.mainId!=main.id || p.mainRank!=main.rank || p.rank==main.rank)
                throw std::invalid_argument("graph provenance");
            uint32_t nr=0;
            if(count>1) {while((nr+1)*(nr+1)<=count) ++nr;nr=std::min({nr,o.maxRelays,count-1});}
            bool relay=nr && (o.forceRelay || (count>=o.minReplicas &&
                count-std::max(nr,(count-nr+nr-1)/nr)>=o.minFanoutGain));
            if(!relay) {
                load[main.rank]+=uint64_t(count)*bytes;
                for(auto p:reps) result.push_back({main.id,p.id,0,bytes,WeightReadyScope::FullExpert});
                continue;
            }
            std::vector<uint32_t> selected,leaves,children(nr,0);
            std::set<uint32_t> usedRanks,usedIndices;
            for(uint32_t r=0;r<nr;++r) {
                uint32_t best=count;
                for(uint32_t i=0;i<count;++i) if(!usedIndices.count(i)) {
                    auto key=[&](uint32_t j){return std::tuple(usedRanks.count(reps[j].rank),load[reps[j].rank],reps[j].rank,j);};
                    if(best==count || key(i)<key(best)) best=i;
                }
                selected.push_back(best);usedIndices.insert(best);usedRanks.insert(reps[best].rank);
            }
            for(uint32_t i=0;i<count;++i) if(!usedIndices.count(i)) leaves.push_back(i);
            std::vector<uint64_t> projected;for(auto i:selected) projected.push_back(load[reps[i].rank]);
            std::vector<uint32_t> owners;
            for(uint32_t j=0;j<leaves.size();++j) {
                uint32_t owner=j;
                if(j>=nr) {
                    owner=0;
                    auto key=[&](uint32_t r){return std::tuple(projected[r],children[r],reps[selected[r]].rank,selected[r]);};
                    for(uint32_t r=1;r<nr;++r) if(key(r)<key(owner)) owner=r;
                }
                owners.push_back(owner);++children[owner];projected[owner]+=bytes;
            }
            load[main.rank]+=uint64_t(nr)*bytes;
            for(uint32_t r=0;r<nr;++r) load[reps[selected[r]].rank]+=uint64_t(children[r])*bytes;
            // Chunk-major fan-out; shards retain FC1 then FC2 order.
            std::vector<std::pair<uint32_t,uint32_t>> ranges;
            if(!streaming) ranges.push_back({0,bytes});
            else {
                std::vector<uint32_t> bounds{0};if(o.shardCut) bounds.push_back(o.shardCut);bounds.push_back(bytes);
                for(size_t s=1;s<bounds.size();++s)
                    for(uint32_t off=bounds[s-1];off<bounds[s];) {
                        uint32_t len=std::min(o.chunkBytes,bounds[s]-off);ranges.push_back({off,len});off+=len;
                    }
            }
            for(auto [off,len]:ranges) for(auto i:selected)
                result.push_back({main.id,reps[i].id,off,len,WeightReadyScope::FullExpert});
            for(uint32_t r=0;r<nr;++r) for(auto [off,len]:ranges)
                for(uint32_t j=0;j<leaves.size();++j) if(owners[j]==r)
                    result.push_back({reps[selected[r]].id,reps[leaves[j]].id,off,len,
                                      streaming?WeightReadyScope::GroupChunk:WeightReadyScope::FullExpert});
        }
        return result;
    }
};
class TwoStageRelay final : public RelayWeightDistribution {
public: explicit TwoStageRelay(WeightDistributionOptions o):RelayWeightDistribution(std::move(o),false) {}
};
class ChunkStreamingRelay final : public RelayWeightDistribution {
public: explicit ChunkStreamingRelay(WeightDistributionOptions o):RelayWeightDistribution(std::move(o),true) {}
};
