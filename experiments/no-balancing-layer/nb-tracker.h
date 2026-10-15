// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <cstdint>
#include <iterator>
#include <map>
#include <stdexcept>
#include <utility>

// Application metadata coverage, not a payload store. A unique notification ID
// must always describe the same range. Overlapping distinct ranges are unioned.
class ChunkTracker {
  uint64_t total;
  std::map<uint64_t, std::pair<uint64_t,uint64_t>> ids;
  std::map<uint64_t,uint64_t> ranges;
  bool emitted = false;
public:
  explicit ChunkTracker(uint64_t n): total(n) {
    if (!n) throw std::invalid_argument("empty chunk");
  }
  uint64_t Covered() const {
    uint64_t n=0; for(auto [a,b]:ranges) n+=b-a; return n;
  }
  bool Complete() const { return emitted; }
  bool Notify(uint64_t id, uint64_t offset, uint64_t length) {
    if (!length || offset>=total || length>total-offset)
      throw std::invalid_argument("range outside chunk");
    auto value=std::make_pair(offset,length);
    auto old=ids.find(id);
    if(old!=ids.end()) {
      if(old->second!=value) throw std::invalid_argument("conflicting duplicate");
      return false;
    }
    ids.emplace(id,value);
    uint64_t end=offset+length;
    auto it=ranges.lower_bound(offset);
    if(it!=ranges.begin()) { auto p=std::prev(it); if(p->second>=offset) it=p; }
    while(it!=ranges.end() && it->first<=end) {
      if(it->second<offset) { ++it; continue; }
      offset=std::min(offset,it->first); end=std::max(end,it->second);
      it=ranges.erase(it);
    }
    ranges.emplace(offset,end);
    if(!emitted && Covered()==total) { emitted=true; return true; }
    return false;
  }
};
