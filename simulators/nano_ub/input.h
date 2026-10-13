#ifndef NANO_TRACE_INPUT_H
#define NANO_TRACE_INPUT_H
#include <cstdint>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <stdexcept>
#include <cctype>
#include <algorithm>
struct TraceSpec {
    uint64_t id,src,jetty,dst,address,size,ready,sequence;
    uint32_t mapped_src,mapped_jetty,mapped_dst;
    std::vector<uint64_t> dependencies;
    std::string phase;
};
static std::vector<std::string> split(const std::string& s,char delimiter) {
    std::vector<std::string> v;size_t a=0,b;
    while((b=s.find(delimiter,a))!=std::string::npos){v.push_back(s.substr(a,b-a));a=b+1;}
    v.push_back(s.substr(a));return v;
}
static uint64_t number(const std::string& s) {
    if(s.empty()||s.size()>19||!std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isdigit(c);}))
        throw std::runtime_error("invalid prepared integer");
    auto n=std::stoull(s);if(n>uint64_t(INT64_MAX))throw std::runtime_error("integer range");return n;
}
static std::vector<TraceSpec> read_specs(const std::string& path) {
    std::ifstream f(path);std::string line;
    if(!f||!std::getline(f,line)||line!="nano-ub-adapter-v1")throw std::runtime_error("invalid prepared version");
    std::getline(f,line);
    if(line!="wr_id\tsrc_node\tjetty_id\tdst_node\tmapped_src\tmapped_jetty\tmapped_dst\tmem_addr\tpayload_bytes\tready_ns\tsequence\tdepends_on\tphase")throw std::runtime_error("invalid prepared header");
    std::vector<TraceSpec> rows;std::set<uint64_t> ids;std::map<uint64_t,uint64_t> seq,addr;
    std::map<uint64_t,uint32_t> jets,nodes;std::map<uint32_t,uint64_t> inverse_jets,inverse_nodes;
    uint64_t total=0,last_ready=0;
    while(std::getline(f,line)) {
        auto v=split(line,'\t');if(v.size()!=13)throw std::runtime_error("prepared column count");
        std::vector<uint64_t> n;for(int i=0;i<11;++i)n.push_back(number(v[i]));
        if(n[4]!=1||n[5]<1||n[5]>1024||n[6]<2||n[6]>0xffffff||n[8]<1||n[8]>16*1024*1024||n[9]>1000000000ULL)
            throw std::runtime_error("backend limits exceeded");
        TraceSpec r{n[0],n[1],n[2],n[3],n[7],n[8],n[9],n[10],uint32_t(n[4]),uint32_t(n[5]),uint32_t(n[6]),{},v[12]};
        if((!rows.empty()&&r.src!=rows[0].src)||r.src==r.dst||ids.count(r.id)||r.ready<last_ready||r.sequence!=seq[r.jetty]++)
            throw std::runtime_error("prepared source/identity/order violation");
        if((jets.count(r.jetty)&&jets[r.jetty]!=r.mapped_jetty)||(inverse_jets.count(r.mapped_jetty)&&inverse_jets[r.mapped_jetty]!=r.jetty)||
           (nodes.count(r.dst)&&nodes[r.dst]!=r.mapped_dst)||(inverse_nodes.count(r.mapped_dst)&&inverse_nodes[r.mapped_dst]!=r.dst))throw std::runtime_error("inconsistent mapping");
        jets[r.jetty]=r.mapped_jetty;inverse_jets[r.mapped_jetty]=r.jetty;nodes[r.dst]=r.mapped_dst;inverse_nodes[r.mapped_dst]=r.dst;
        if(r.address!=addr[r.dst])throw std::runtime_error("noncontiguous or overlapping destination memory");
        addr[r.dst]+=r.size;total+=r.size;
        if(total>128*1024*1024||rows.size()>=60000)throw std::runtime_error("trace capacity exceeded");
        if(v[11]!="-")for(const auto& d:split(v[11],';')){
            auto id=number(d);if(!ids.count(id)||std::find(r.dependencies.begin(),r.dependencies.end(),id)!=r.dependencies.end())throw std::runtime_error("invalid dependency");r.dependencies.push_back(id);
        }
        if(r.phase.size()>64||!std::all_of(r.phase.begin(),r.phase.end(),[](unsigned char c){return std::isalnum(c)||c=='_'||c=='-'||c=='.';}))throw std::runtime_error("invalid phase");
        ids.insert(r.id);last_ready=r.ready;rows.push_back(r);
    }
    for(uint32_t i=1;i<=jets.size();++i)if(!inverse_jets.count(i))throw std::runtime_error("mapped Jetties not dense");
    return rows;
}
static unsigned jetty_count(const std::vector<TraceSpec>& specs) {
    unsigned n=1;for(auto& r:specs)n=std::max(n,r.mapped_jetty);return n;
}
#endif
