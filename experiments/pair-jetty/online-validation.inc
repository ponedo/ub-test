    // Observer state is independent of persistence. Every mode executes these checks.
    struct SegmentAudit {uint8_t state=0;uint64_t admitted=0,received=0,verified=0,completed=0;};
    struct TaskAudit {bool sent=false,ready=false,sender=false,local=false,relayRead=false;uint64_t send=0,finish=0,latest=0;std::vector<SegmentAudit> segments;};
    std::vector<TaskAudit> taskAudit;
    std::map<std::string,std::array<uint64_t,3>> spans;
    std::map<std::tuple<std::string,int,int,uint64_t,uint64_t>,uint64_t> uniqueEvents;
    std::vector<uint64_t> txBytes,rxBytes,txPackets,rxPackets,computeBegin,computeEnd,expertCursor;
    std::vector<bool> tokenAudit;
    uint64_t lastAuditTime=0,verificationNs=0,verifiedSegments=0,combineHash=14695981039346656037ULL;
    std::array<uint64_t,3> verifiedBytes{},remoteBytes{},localBytes{},stageReadyCounts{};
    std::array<std::array<uint64_t,2>,3> stageIntervals{};
    static uint64_t Hash(uint64_t hash,const char* data,size_t size){for(size_t i=0;i<size;++i){hash^=static_cast<uint8_t>(data[i]);hash*=1099511628211ULL;}return hash;}
    static std::string Hex(uint64_t value){std::ostringstream s;s<<std::hex<<std::setfill('0')<<std::setw(16)<<value;return s.str();}
    uint64_t At(const std::string& key)const{auto it=spans.find(key);Require(it!=spans.end(),"missing audit event "+key);return it->second[0];}
    // Built before any events; audit reads never change these membership vectors.
    std::map<uint32_t,std::vector<size_t>> auditReplicaMembers;
    std::map<std::tuple<uint32_t,uint64_t,uint64_t>,std::vector<size_t>> auditGroupMembers;
    void InitAudit(){
        if(onlineMembershipMode=="index")for(size_t i=2*assignments.size();i<transfers.size();++i){
            const auto& x=transfers[i];auditReplicaMembers[x.physical].push_back(i);
            if(!P(x.sourcePhysical).replica)auditGroupMembers[{P(x.physical).expert,x.offset,x.bytes}].push_back(i);
        }
        taskAudit.resize(transfers.size());for(size_t i=0;i<transfers.size();++i)if(transfers[i].source!=transfers[i].target)taskAudit[i].segments.resize((transfers[i].bytes+segment-1)/segment);tokenAudit.assign(t,false);computeBegin.assign(n,0);computeEnd.assign(n,0);expertCursor.assign(n,0);}
    bool KeyEvent(const std::string& name,int stage,int task)const{
        static const std::set<std::string> keys={"layer_start","layer_end","planning_start","planning_end","reroute_start","reroute_end","weights_start","weights_end","dispatch_gate","compute_start","compute_end","compute_idle","expert_start","expert_end","weight_ready","group_chunk_ready"};
        return keys.count(name)||(name=="edge_ready")||(name=="send"&&stage==2&&task>=0&&!transfers[task].dependencies.empty());
    }
    void Audit(const std::string& name,int stage,int id,int node,uint64_t off,uint64_t len,int task){
        auto wall=std::chrono::steady_clock::now();const uint64_t now=Simulator::Now().GetPicoSeconds();
        Require(now>=lastAuditTime,"audit clock reversed");lastAuditTime=now;
        auto [sp,newSpan]=spans.try_emplace(name,std::array<uint64_t,3>{now,now,0});sp->second[1]=now;++sp->second[2];
        if(name=="error")return;
        if(task>=0){
            Require(size_t(task)<transfers.size(),"audit unknown task");auto& x=transfers[task];auto& a=taskAudit[task];
            Require(stage==int(x.stage)&&id==int(x.id),"audit task metadata");
            if(name=="send"){
                Require(!a.sent&&node==int(x.source)&&off==0&&len==x.bytes,"audit duplicate/invalid send");
                uint64_t gate=At("planning_end");if(x.stage==0)gate=At("dispatch_gate");else if(x.stage==1){Require(computeEnd[x.source]!=0,"audit combine before compute");gate=computeEnd[x.source];}else for(auto parent:x.dependencies){Require(taskAudit[parent].ready,"audit relay dependency");gate=std::max(gate,taskAudit[parent].finish);}
                Require(now==gate,"audit non-immediate send/gate");a.sent=true;a.send=now;
                if(!stageIntervals[x.stage][0])stageIntervals[x.stage][0]=now;
            }else if(name=="ta_admitted"||name=="target_received"||name=="payload_verified"||name=="target_complete"){
                Require(a.sent&&x.source!=x.target&&off<x.bytes&&off%segment==0&&len==std::min<uint64_t>(segment,x.bytes-off),"audit segment range");
                auto& seg=a.segments.at(off/segment);uint8_t want=name=="ta_admitted"?0:name=="target_received"?1:name=="payload_verified"?2:3;
                Require(seg.state==want,"audit duplicate/missing/out-of-order segment event "+name);
                Require(node==int(want==0?x.source:x.target),"audit segment endpoint");++seg.state;
                if(want==0){Require(now>=a.send,"audit admission before send");seg.admitted=now;}
                if(want==1){Require(now>=seg.admitted,"audit receive before admission");seg.received=now;}
                if(want==2){Require(now>=seg.received,"audit verify before receive");seg.verified=now;}
                if(want==3){uint64_t delay=0;if(x.stage==2){delay=weightCompleteNs;if(!P(x.sourcePhysical).replica&&x.offset==0)delay+=reorderNs;if(!P(x.sourcePhysical).replica&&x.target==slowRelayRank)delay+=slowRelayNs;}
                    Require(now>=seg.verified&&now-seg.verified==delay*1000,"audit target service delay");seg.completed=now;a.latest=std::max(a.latest,now);++verifiedSegments;}
            }else if(name=="local_verified"){
                Require(a.sent&&!a.local&&x.source==x.target&&node==int(x.target)&&off==0&&len==x.bytes,"audit local verification");a.local=true;a.latest=now;
            }else if(name=="data_ready"||name=="edge_ready"){
                Require(a.sent&&!a.ready&&node==int(x.target)&&len==x.bytes&&off==0,"audit ready identity/duplicate");
                Require(name==(x.stage==2?"edge_ready":"data_ready"),"audit ready kind");
                if(x.source==x.target)Require(a.local,"audit local payload missing");else for(auto& seg:a.segments)Require(seg.state==4,"audit ready before all TA completion");
                Require(now==a.latest,"audit ready aggregation time");a.ready=true;a.finish=now;stageIntervals[x.stage][1]=std::max(stageIntervals[x.stage][1],now);
                ++stageReadyCounts[x.stage];verifiedBytes[x.stage]+=x.bytes;(x.source==x.target?localBytes:remoteBytes)[x.stage]+=x.bytes;
            }else if(name=="sender_complete"){
                Require(a.ready&&!a.sender&&x.source!=x.target&&node==int(x.source)&&now>=a.finish,"audit premature/duplicate sender completion");a.sender=true;
            }else if(name=="relay_buffer_read"){
                Require(!a.relayRead&&!x.dependencies.empty()&&a.sent&&now==a.send&&node==int(x.source)&&off==x.offset&&len==x.bytes,"audit relay buffer provenance");a.relayRead=true;
            }
        }else{
            if(name=="token_complete"){
                Require(id>=0&&uint32_t(id)<t&&!tokenAudit[id],"audit duplicate token");uint64_t end=0;
                for(uint32_t rank=0;rank<k;++rank){auto aid=uint32_t(id)*k+rank;Require(taskAudit[assignments.size()+aid].ready,"audit missing top-k contribution");Require(node==int(assignments[aid].source),"audit token source");end=std::max(end,taskAudit[assignments.size()+aid].finish);}
                Require(now==end,"audit token completion time");tokenAudit[id]=true;
            }else{
                auto key=std::make_tuple(name,id,node,off,len);Require(uniqueEvents.emplace(key,now).second,"audit duplicate global event "+name);
                if(name=="planning_end")Require(now-At("planning_start")==uint64_t(planningNs)*1000,"audit planning duration");
                if(name=="reroute_start"||name=="weights_start")Require(now==At("planning_end"),"audit overlap start");
                if(name=="reroute_end")Require(now-At("reroute_start")==uint64_t(rerouteNs)*1000,"audit reroute duration");
                if(name=="weights_end"){uint64_t end=At("planning_end");for(auto& p:physical)if(p.replica){auto key=std::make_tuple(std::string("weight_ready"),int(p.id),int(p.rank),uint64_t(0),uint64_t(weightBytes));Require(uniqueEvents.count(key),"audit missing replica ready");end=std::max(end,uniqueEvents.at(key));}Require(now==end,"audit global weights completion");}
                if(name=="dispatch_gate")Require(now==std::max(At("reroute_end"),At("weights_end")),"audit dispatch gate");
                if(name=="main_weight_ready"){auto& p=P(id);Require(!p.replica&&p.rank==uint32_t(node)&&off==0&&len==weightBytes&&now==At("layer_start"),"audit main resident weight");}
                if(name=="weight_ready"){auto& p=P(id);Require(p.replica&&p.rank==uint32_t(node)&&off==0&&len==weightBytes,"audit replica ready identity");
                    uint64_t end=0;
                    auto check=[&](size_t i){Require(taskAudit[i].ready,"audit premature weight ready");end=std::max(end,taskAudit[i].finish);};
                    if(onlineMembershipMode=="scan"){
                        for(size_t i=2*assignments.size();i<transfers.size();++i)if(transfers[i].physical==uint32_t(id))check(i);
                    }else{
                        auto it=auditReplicaMembers.find(uint32_t(id));if(it!=auditReplicaMembers.end())for(auto i:it->second)check(i);
                    }
                    Require(now==end,"audit final weight aggregation");
                }
                if(name=="group_chunk_ready"){
                    uint64_t end=0;
                    auto check=[&](size_t i){Require(taskAudit[i].ready,"audit premature group");end=std::max(end,taskAudit[i].finish);};
                    if(onlineMembershipMode=="scan"){
                        for(size_t i=2*assignments.size();i<transfers.size();++i){auto& x=transfers[i];if(!P(x.sourcePhysical).replica&&P(x.physical).expert==uint32_t(id)&&x.offset==off&&x.bytes==len)check(i);}
                    }else{
                        auto it=auditGroupMembers.find({uint32_t(id),off,len});if(it!=auditGroupMembers.end())for(auto i:it->second)check(i);
                    }
                    Require(now==end,"audit group timing");
                }
                if(name=="compute_idle")Require(node>=0&&uint32_t(node)<n&&!expected[node]&&now==At("dispatch_gate"),"audit invalid idle compute");
                if(name=="compute_start"){Require(node>=0&&uint32_t(node)<n&&expected[node]>0&&!computeBegin[node],"audit compute identity");Require(now>=At("dispatch_gate"),"audit compute gate");for(size_t i=0;i<assignments.size();++i)if(assignments[i].target==uint32_t(node))Require(taskAudit[i].ready,"audit compute data dependency");computeBegin[node]=now;expertCursor[node]=now;}
                if(name=="expert_start"){auto& p=P(id);Require(p.rank==uint32_t(node)&&p.quota==len&&now==expertCursor[node],"audit expert serialization start");}
                if(name=="expert_end"){auto& p=P(id);Require(p.rank==uint32_t(node)&&p.quota==len&&now==expertCursor[node]+Duration(p.quota),"audit expert duration");expertCursor[node]=now;}
                if(name=="compute_end"){Require(computeBegin.at(node)&&now==expertCursor[node],"audit compute end");computeEnd[node]=now;}
                if(name=="layer_end"){uint64_t end=At("dispatch_gate");for(uint32_t i=0;i<t;++i)Require(tokenAudit[i],"audit unfinished token");if(t)end=std::max(end,spans.at("token_complete")[1]);Require(now==end,"audit layer end");}
            }
        }
        verificationNs+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-wall).count();
    }
    void FinalAudit(){
        auto wall=std::chrono::steady_clock::now();
        for(size_t task=0;task<transfers.size();++task){auto& x=transfers[task];auto& a=taskAudit[task];Require(a.sent&&a.ready&&a.sender==(x.source!=x.target)&&a.relayRead==(!x.dependencies.empty()),"audit terminal task state");
            for(size_t i=0;i<x.data.size();++i)Require(x.data[i]==ExpectedByte(task,i),"audit final payload corruption");
            if(x.stage==1)combineHash=Hash(combineHash,reinterpret_cast<const char*>(x.data.data()),x.data.size());
            if(x.stage==2&&!x.dependencies.empty())for(size_t i=0;i<x.data.size();++i)Require(x.data[i]==weightData[pIndex.at(x.sourcePhysical)][x.offset+i],"audit relay final buffer provenance");
        }
        for(size_t i=0;i<physical.size();++i)if(physical[i].replica)for(uint32_t off=0;off<weightBytes;++off)Require(weightData[i][off]==WeightByte(physical[i].id,off),"audit final weight corruption");
        Require(verifiedSegments==taCount,"audit TA conservation");Require(verifiedBytes[0]==uint64_t(assignments.size())*bytes&&verifiedBytes[1]==verifiedBytes[0],"audit assignment bytes");
        for(auto name:{"layer_start","layer_end","planning_start","planning_end","reroute_start","reroute_end","weights_start","weights_end","dispatch_gate"})Require(spans.count(name)&&spans.at(name)[2]==1,"audit global cardinality");
        Require(At("planning_start")==At("layer_start"),"audit planning start");
        auto count=[this](const std::string& key){return spans.count(key)?spans.at(key)[2]:0;};
        Require(count("main_weight_ready")==e&&count("weight_ready")==physical.size()-e&&count("group_chunk_ready")==readyGroups.size(),"audit weight event cardinality");
        uint32_t active=0,nonzero=0;for(uint32_t node=0;node<n;++node)if(expected[node]){++active;Require(computeBegin[node]&&computeEnd[node],"audit missing compute");for(auto name:{"compute_start","compute_end"})Require(uniqueEvents.count(std::make_tuple(std::string(name),-1,int(node),uint64_t(0),uint64_t(expected[node]))),"audit compute metadata");}else Require(uniqueEvents.count(std::make_tuple(std::string("compute_idle"),-1,int(node),uint64_t(0),uint64_t(0))),"audit missing idle node");
        Require(count("compute_start")==active&&count("compute_end")==active&&count("compute_idle")==n-active,"audit compute cardinality");
        for(auto& p:physical)if(p.quota){++nonzero;for(auto name:{"expert_start","expert_end"})Require(uniqueEvents.count(std::make_tuple(std::string(name),int(p.id),int(p.rank),uint64_t(0),uint64_t(p.quota))),"audit missing expert event");}
        Require(count("expert_start")==nonzero&&count("expert_end")==nonzero&&count("token_complete")==t,"audit expert/token cardinality");
        verificationNs+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-wall).count();
    }
    template<class Range> static void JsonArray(std::ostream& out,const Range& range){out<<'[';bool comma=false;for(auto v:range){if(comma)out<<',';comma=true;out<<v;}out<<']';}
    void WriteSummary(const std::string& out){
        std::ofstream s(out+"/online-summary.json");Require(bool(s),"summary output");
        s<<"{\"schema\":1,\"log_level\":\""<<logLevel<<"\",\"layer_latency_ps\":"<<At("layer_end")-At("layer_start")<<",\"remote_WQEs\":"<<remoteCount<<",\"TA_count\":"<<taCount<<",\"target_segments\":"<<verifiedSegments<<",\"sender_completions\":"<<senderCount<<",\"completed_tokens\":"<<receivedTokens<<",\"assignments\":"<<assignments.size()<<",\"replicas\":"<<physical.size()-e<<",\"jettys\":"<<jettyCount<<",\"simulator_events\":"<<Simulator::GetEventCount()<<",\"verification_wall_ns\":"<<verificationNs<<",\"combine_fnv1a64\":\""<<Hex(combineHash)<<"\",\"executed_graph_fnv1a64\":\""<<GraphHash()<<"\"";
        s<<",\"max_npu_load\":"<<*std::max_element(expected.begin(),expected.end())<<",\"per_npu_load\":";JsonArray(s,expected);
        s<<",\"verified_bytes\":";JsonArray(s,verifiedBytes);s<<",\"remote_bytes\":";JsonArray(s,remoteBytes);s<<",\"local_bytes\":";JsonArray(s,localBytes);
        s<<",\"packet_tx_per_node\":";JsonArray(s,txPackets);s<<",\"packet_rx_per_node\":";JsonArray(s,rxPackets);s<<",\"byte_tx_per_node\":";JsonArray(s,txBytes);s<<",\"byte_rx_per_node\":";JsonArray(s,rxBytes);
        s<<",\"timeline\":{";bool comma=false;for(auto key:{"layer_start","planning_end","reroute_end","weights_end","dispatch_gate","layer_end"}){if(comma)s<<',';comma=true;s<<'"'<<key<<"\":"<<At(key);}s<<"},\"event_spans\":{";comma=false;for(auto& [key,span]:spans){if(comma)s<<',';comma=true;s<<'"'<<key<<"\":";JsonArray(s,span);}s<<"},\"stage_intervals\":[";for(int i=0;i<3;++i){if(i)s<<',';JsonArray(s,stageIntervals[i]);}s<<"],\"compute_intervals\":[";comma=false;for(uint32_t i=0;i<n;++i)if(expected[i]){if(comma)s<<',';comma=true;s<<"{\"node\":"<<i<<",\"start_ps\":"<<computeBegin[i]<<",\"end_ps\":"<<computeEnd[i]<<'}';}s<<"]}\n";
        std::ofstream v(out+"/validation.json");v<<"{\"status\":\"PASS\",\"checks\":[\"per_task_state\",\"per_segment_exact_once_order_delay\",\"actual_payload_every_byte\",\"terminal_payload_every_byte\",\"quota_and_routing\",\"relay_buffer_and_dependencies\",\"weight_coverage\",\"compute_duration_and_order\",\"topk_conservation\",\"wqe_completion\",\"pair_idle\"],\"checked_tasks\":"<<transfers.size()<<",\"checked_TAs\":"<<verifiedSegments<<",\"verification_wall_ns\":"<<verificationNs<<"}\n";
    }
