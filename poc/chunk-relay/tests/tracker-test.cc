#include "../tracker.h"
#include <cassert>
#include <iostream>
#include <limits>
template<class F> void Reject(F f) { bool rejected=false; try {f();} catch(const std::invalid_argument&) {rejected=true;} assert(rejected); }
int main() {
  ChunkTracker t(100);
  assert(!t.Notify(2,50,25)); // out of order
  assert(!t.Notify(2,50,25)); // exact repeat
  assert(t.Covered()==25);
  assert(!t.Notify(3,60,40)); // overlap is not double counted
  assert(t.Covered()==50 && !t.Complete());
  assert(!t.Notify(0,0,49)); // one-byte hole prevents forwarding
  assert(t.Covered()==99);
  assert(t.Notify(1,49,1));
  assert(!t.Notify(4,0,100)); // complete may fire only once
  assert(!t.Notify(1,49,1));
  Reject([&]{t.Notify(1,48,1);});
  Reject([&]{t.Notify(5,100,1);});
  Reject([&]{t.Notify(5,0,0);});
  Reject([&]{t.Notify(5,99,std::numeric_limits<uint64_t>::max());});
  Reject([]{ChunkTracker zero(0);});
  ChunkTracker missing(100); assert(!missing.Notify(0,0,99)); assert(!missing.Complete());
  ChunkTracker independent(2); assert(independent.Notify(0,0,2)); assert(!missing.Complete());
  std::cout << "PASS: reorder, dedup, overlap union, hole, exactly once, invalid ranges, overflow, independent chunks\n";
}
