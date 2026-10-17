// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "ns3/unified-bus-module.h"
#include <functional>
#include <map>
#include <stdexcept>
#include <utility>

// Application ownership only. Never throttles, schedules, or serializes WQEs.
class PairJettyManager {
public:
    using Key = std::pair<uint32_t,uint32_t>;
    struct Entry { uint32_t id, tpn; ns3::Ptr<ns3::UbJetty> jetty; };
    using Controller = std::function<ns3::Ptr<ns3::UbController>(uint32_t)>;
    PairJettyManager(Controller controller, uint32_t nodes, uint32_t segment,
                     ns3::Callback<void,uint32_t,uint32_t> completion)
        : controller_(controller), nodes_(nodes), segment_(segment), completion_(completion) {}
    const Entry& Get(uint32_t source, uint32_t target, uint32_t tpn) {
        if(source==target || source>=nodes_ || target>=nodes_)
            throw std::runtime_error("Pair Jetty requires distinct valid ranks");
        Key key{source,target};
        auto it=entries_.find(key);
        if(it!=entries_.end()) {
            if(it->second.tpn!=tpn) throw std::runtime_error("Pair Jetty TP changed");
            return it->second;
        }
        // Separate ID namespace from task IDs: bounded by EP degree, stable per pair.
        uint32_t id=source*nodes_+target+1;
        auto c=controller_(source);auto fn=c->GetUbFunction();
        if(fn->GetJetty(id)) throw std::runtime_error("Pair Jetty ID collision");
        fn->CreateJetty(source,target,id);
        if(!c->GetUbTransaction()->JettyBindTp(source,target,id,false,{tpn}))
            throw std::runtime_error("Pair Jetty TP bind failed");
        auto jetty=fn->GetJetty(id);jetty->SetTaSegmentBytes(segment_);
        jetty->SetClientCallback(completion_);
        return entries_.emplace(key,Entry{id,tpn,jetty}).first->second;
    }
    size_t Size() const { return entries_.size(); }
    void CheckIdle() const {
        for(const auto& [key,e]:entries_)
            if(!e.jetty->IsIdle() || e.jetty->GetActiveWqeCount()!=0)
                throw std::runtime_error("Pair Jetty still has active WQEs");
    }
private:
    Controller controller_;uint32_t nodes_,segment_;
    ns3::Callback<void,uint32_t,uint32_t> completion_;
    std::map<Key,Entry> entries_;
};
