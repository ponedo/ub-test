#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <sys/resource.h>
struct Counter { uint64_t calls,inclusive,exclusive,cpu_inclusive,cpu_exclusive,rss_highwater_kib; };
struct Frame { unsigned id; uint64_t begin,children,cpu_begin,cpu_children; };
static Counter counters[128];
static thread_local Frame frames[512];
static thread_local unsigned depth;
static uint64_t now(){timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static bool coarse(unsigned id){return id==0||id==1||id==2||id==8||id==9||id==10||id==11;}
static uint64_t cpuNow(){timespec t;clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
extern "C" void cpu_scope_enter(unsigned id){if(id>=128||depth>=512)std::abort();frames[depth++]={id,now(),0,coarse(id)?cpuNow():0,0};}
extern "C" void cpu_scope_leave(){auto end=now();auto f=frames[--depth];auto dt=end-f.begin;auto& c=counters[f.id];++c.calls;c.inclusive+=dt;c.exclusive+=dt-f.children;if(coarse(f.id)){rusage r;getrusage(RUSAGE_SELF,&r);if(uint64_t(r.ru_maxrss)>c.rss_highwater_kib)c.rss_highwater_kib=r.ru_maxrss;auto cpu=cpuNow()-f.cpu_begin;c.cpu_inclusive+=cpu;c.cpu_exclusive+=cpu-f.cpu_children;for(unsigned i=depth;i>0;--i)if(coarse(frames[i-1].id)){frames[i-1].cpu_children+=cpu;break;}}if(depth)frames[depth-1].children+=dt;}
__attribute__((destructor)) static void dump(){auto path=std::getenv("CPU_SCOPE_OUTPUT");if(!path)return;auto f=std::fopen(path,"w");if(!f)std::abort();std::fprintf(f,"id,calls,inclusive_ns,exclusive_ns,cpu_inclusive_ns,cpu_exclusive_ns,rss_highwater_kib\n");for(unsigned i=0;i<128;++i)if(counters[i].calls)std::fprintf(f,"%u,%lu,%lu,%lu,%lu,%lu,%lu\n",i,counters[i].calls,counters[i].inclusive,counters[i].exclusive,counters[i].cpu_inclusive,counters[i].cpu_exclusive,counters[i].rss_highwater_kib);std::fclose(f);}
