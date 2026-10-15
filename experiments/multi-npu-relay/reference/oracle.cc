// Wrapper for the verbatim public selection block; independent of production header.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>
struct P {int id,expert,rank,replica,quota,main,mainrank;};
int main(){
 int mode,bytes,n,chunk,minrep,maxrelay,gain,force,cut,np;
 if(!(std::cin>>mode>>bytes>>n>>chunk>>minrep>>maxrelay>>gain>>force>>cut>>np))return 2;
 std::vector<P> ps(np),mains;std::map<int,std::vector<P>> groups;
 for(auto& p:ps){std::cin>>p.id>>p.expert>>p.rank>>p.replica>>p.quota>>p.main>>p.mainrank;if(p.replica)groups[p.expert].push_back(p);else mains.push_back(p);}
 std::sort(mains.begin(),mains.end(),[](auto a,auto b){return a.id<b.id;});
 constexpr int kMaxNvlDomainSize=72;int64_t sender_load_bytes[kMaxNvlDomainSize]={0};
 for(auto main:mains){auto reps=groups[main.expert];int num_replicas=reps.size();if(!num_replicas)continue;
  int relay_count=0;while((relay_count+1)*(relay_count+1)<=num_replicas)++relay_count;
  relay_count=std::min({relay_count,maxrelay,num_replicas-1});
  bool use=mode && relay_count>0 && (force || (num_replicas>=minrep && num_replicas-std::max(relay_count,(num_replicas-relay_count+relay_count-1)/relay_count)>=gain));
  if(!use){sender_load_bytes[main.rank]+=int64_t(num_replicas)*bytes;for(auto p:reps)std::cout<<main.id<<','<<p.id<<'\n';continue;}
  int domain_nvl_rank=main.rank,num_nvl_ranks=n,num_local_physical=1024,num_local_master=0;
  int max_rep_dim=num_replicas+1,logical_expert=0;std::vector<int> l2p(max_rep_dim);
  for(int i=0;i<num_replicas;++i)l2p[i+1]=reps[i].rank*num_local_physical+i;
  int64_t weight_bytes_per_expert=bytes;
#include "selection.inc"
  for(int r=0;r<relay_count;++r)std::cout<<main.id<<','<<reps[relay_replica_indices[r]].id<<'\n';
  for(int i=0;i<num_replicas;++i)if(leaf_owner_relay[i]>=0)std::cout<<reps[relay_replica_indices[leaf_owner_relay[i]]].id<<','<<reps[i].id<<'\n';
 }
}
