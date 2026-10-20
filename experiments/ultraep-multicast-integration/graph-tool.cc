#include "../direct-weight-forward/weight-distribution.h"
#include <iostream>
int main() {
    uint32_t kind,bytes,np;WeightDistributionOptions o;
    if(!(std::cin>>kind>>bytes>>o.nodes>>o.chunkBytes>>o.minReplicas>>o.maxRelays>>o.minFanoutGain>>o.forceRelay>>o.shardCut>>np)) return 2;
    std::vector<PhysicalExpert> ps(np);
    for(auto& p:ps) if(!(std::cin>>p.id>>p.expert>>p.rank>>p.replica>>p.quota>>p.mainId>>p.mainRank)) return 2;
    try {
        std::vector<WeightEdge> edges;
        if(kind==0||kind==3||kind==4) edges=DirectWeightDistribution().Edges(ps,bytes);
        else if(kind==1) edges=TwoStageRelay(o).Edges(ps,bytes);
        else if(kind==2) edges=ChunkStreamingRelay(o).Edges(ps,bytes);
        else return 2;
        std::cout<<"source_physical,physical,offset,bytes,scope\n";
        for(auto e:edges) std::cout<<e.sourcePhysical<<','<<e.targetPhysical<<','<<e.offset<<','<<e.bytes<<','<<int(e.sourceDependency)<<'\n';
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
