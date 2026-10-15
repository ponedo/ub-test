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
/*HELPERS*/
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
/*SHARED*/
 void run(int thread_id){
  cpu_tid=thread_id;const int tid=thread_id,warp_id=tid/32,lane_id=tid%32;
/*SEARCH*/
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
