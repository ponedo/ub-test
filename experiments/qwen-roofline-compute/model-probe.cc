#include "compute-model.h"
#include <iostream>
#include <string>
int main(int argc,char** argv){try{
 if(argc!=8&&argc!=9)return 2;
 uint64_t v[7];for(int k=0;k<7;++k){std::string s(argv[k+1]);if(s.empty()||s.find_first_not_of("0123456789")!=std::string::npos)return 2;size_t used;v[k]=std::stoull(s,&used);if(used!=s.size())return 2;if(k<5&&v[k]>UINT32_MAX)return 2;}
 uint64_t overrideBytes=0;if(argc==9){std::string s(argv[8]);if(s.empty()||s.find_first_not_of("0123456789")!=std::string::npos)return 2;overrideBytes=std::stoull(s);}
 auto x=expert_roofline::Calculate(v[0],v[1],v[2],v[3],v[4],v[5],v[6],overrideBytes);
 std::cout<<x.flops<<','<<x.weights<<','<<x.input<<','<<x.intermediate<<','<<x.output<<','<<x.activations<<','<<x.hbm<<','<<x.computePs<<','<<x.memoryPs<<','<<x.totalPs<<'\n';
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
