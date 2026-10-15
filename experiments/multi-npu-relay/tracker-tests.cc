#include "../no-balancing-layer/nb-tracker.h"
#include "../direct-weight-forward/weight-distribution.h"
#include <iostream>
void check(bool ok){if(!ok)throw std::runtime_error("tracker test failed");}
template<class F> void rejects(F fn){bool bad=false;try{fn();}catch(const std::exception&){bad=true;}check(bad);}
int main(){
 ChunkTracker c(2501);check(!c.Notify(2,2048,453));check(!c.Notify(0,0,1024));check(!c.Notify(0,0,1024));check(c.Notify(1,1024,1024));check(c.Covered()==2501);check(!c.Notify(1,1024,1024));
 rejects([&]{c.Notify(1,1024,1000);});rejects([&]{c.Notify(3,2501,1);});rejects([&]{c.Notify(4,2400,102);});rejects([&]{c.Notify(5,0,0);});
 ChunkTracker overlap(10);check(!overlap.Notify(0,0,7));check(overlap.Notify(1,5,5));check(overlap.Covered()==10);
 WeightDistributionOptions options;options.nodes=4;options.domain={0,0,1,1};
 rejects([&]{ChunkStreamingRelay(options).Edges({},100);});
 std::cout<<"PASS: out-of-order/tail, idempotent duplicate, conflicting duplicate, bounds, union coverage, unsupported domain\n";
}
