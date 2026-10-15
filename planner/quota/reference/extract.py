#!/usr/bin/env python3
"""Mechanically compile exact scalar blocks of pinned CUDA source on CPU.
No warp/GPU simulation and no handwritten replacement reference algorithm.
"""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent
PINNED_SHA256 = {
    'placement.cu': '195637d9d9b0ce37656dcccbd7f487202699fbda0f11c41c431f71b38f01983f',
    'reroute.cu': '19033250379282cb856df7656d5a56111f1ceb77057e9a12315e55494f632fad',
    'weight_sync.cu': '0c5a8bf91df78f83ac82016730642219fdbb52b9394511485346b08ee8c62a83',
}
for name, expected in PINNED_SHA256.items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
        raise RuntimeError('Pinned upstream source hash mismatch: ' + name)
s=(ROOT/'placement.cu').read_text();reroute=(ROOT/'reroute.cu').read_text()
def function(text,start):
 a=text.index(start);b=text.index('{',a);depth=1;i=b+1
 while depth:
  depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[a:i]
slow=function(s,'__device__ __noinline__ void build_rank_quota_prefix_slow(')
fast_container=function(s,'if (C <= QUOTA_FAST_REPLICA_LIMIT) {')
fast_body=fast_container[fast_container.index('{')+1:-1]
fast_signature=slow[:slow.index('{')].replace('build_rank_quota_prefix_slow','build_rank_quota_prefix_fast')
lookup=function(reroute,'__device__ __forceinline__ int sparse_quota_replica_index(')
header='''#include <algorithm>
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
'''
main='''
int main(){int G,C,local;while(std::cin>>G>>C>>local){
 if(G<1||G>72||C<1||C>72)return 2;
 std::vector<int32_t>d(G),h(C),q(C);for(auto&x:d)std::cin>>x;for(auto&x:h)std::cin>>x;for(auto&x:q)std::cin>>x;
 for(int mode=0;mode<2;++mode){if(mode==1&&C>8)continue;
 for(int r=0;r<G;++r){std::vector<int32_t>out(C);
 auto fn=mode?build_rank_quota_prefix_fast:build_rank_quota_prefix_slow;
 fn(0,0,C,&d[r],d.data(),1,0,1,r,G,local,q.data(),h.data(),out.data());
 int prev=0;for(int j=0;j<C;++j){std::cout<<(out[j]-prev)<<' ';prev=out[j];}std::cout<<'\\n';
 // Execute the exact upstream ordinal lookup too, checking it reproduces the row.
 std::vector<int>counts(C);for(int z=0;z<d[r];++z)++counts[sparse_quota_replica_index(z,0,C,C,out.data())];
 prev=0;for(int j=0;j<C;++j){if(counts[j]!=out[j]-prev)return 3;prev=out[j];}
 }}
}return 0;}
'''
(ROOT/'generated_reference.cpp').write_text(header+slow+'\n'+fast_signature+'{'+fast_body+'}\n'+lookup+'\n'+main)
subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'generated_reference.cpp'),'-o',str(ROOT/'reference_cpu')],check=True)
manifest={'commit':'94cab099b44fffa99a82fea99e7c12d89cf65e4f','tag':'v1.0.0','method':'verbatim slow function + verbatim fast branch body + verbatim sparse ordinal lookup; CUDA attributes removed via macros only','gpu_execution':False,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['placement.cu','reroute.cu','weight_sync.cu']},'extracted_block_sha256':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in [('slow',slow),('fast_body',fast_body),('lookup',lookup)]}}
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
