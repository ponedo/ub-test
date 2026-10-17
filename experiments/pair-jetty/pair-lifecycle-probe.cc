// SPDX-License-Identifier: GPL-2.0-only
// Gate A: independent real-network PairJetty lifecycle and 16-bit wrap oracle.
// Application-only test. Payload identity/offset is decoded independently of SSN.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "pair-jetty-manager.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <vector>
using namespace ns3;

class LifecycleProbe {
    using Key = std::pair<uint32_t,uint32_t>;
    static constexpr uint32_t segment=64, bytes=160, magic=0x50524a54;
    struct Work {
        uint32_t src=0,dst=0,jetty=0,sent=0,received=0,executed=0,terminal=0,client=0;
        uint32_t nextOffset=0;
        bool submitted=false;
        UbWorkOutcome expectedOutcome=UbWorkOutcome::COMPLETED;
        std::vector<uint8_t> payload,covered;
        std::map<uint32_t,uint32_t> logicalOffsets;
    };
public:
    uint32_t nodes=2, count=22000;
    std::string mode="directional", output="pair-lifecycle";
    std::vector<Ptr<Node>> hosts;
    std::map<Key,Ptr<UbTransportChannel>> tps;
    std::map<Key,PairJettyManager::Entry> entries;
    std::unique_ptr<PairJettyManager> manager;
    std::map<uint32_t,Work> works;
    std::map<Key,uint32_t> logicalNext;
    std::map<std::pair<Key,uint32_t>,uint32_t> logicalOwners;
    std::map<Key,uint32_t> active,peak;
    std::vector<std::string> failures;
    std::ofstream events;
    uint32_t terminalCount=0,clientCount=0,localCopies=0,localRejections=0;
    uint64_t requestTAs=0,responseTAs=0,verifiedBytes=0,duplicateDoneCalls=0,wireWraps=0;
    bool busyRejected=false, idleChecked=false, managerDestroyed=false;
    Ptr<UbController> Ctrl(uint32_t i) {return hosts.at(i)->GetObject<UbController>();}
    uint32_t Tpn(uint32_t src,uint32_t dst) const {return 100+src*nodes+dst;}
    uint32_t Port(uint32_t src,uint32_t dst) const {return dst<src?dst:dst-1;}
    void Event(const std::string& kind,uint32_t id=0,uint32_t logical=0,uint32_t wire=0,
               uint32_t off=0,const std::string& detail="") {
        events<<Simulator::Now().GetNanoSeconds()<<','<<kind<<','<<id<<','<<logical<<','
              <<wire<<','<<off<<','<<detail<<'\n';
        if(kind=="FAIL" || logical>=65530 || id%1024==0)events.flush();
    }
    void Fail(const std::string& why,uint32_t id=0,uint32_t logical=0) {
        if(failures.size()<100) failures.push_back(why+":"+std::to_string(id));
        Event("FAIL",id,logical,logical&65535,0,why);
    }
    void Check(bool ok,const std::string& why,uint32_t id=0) {if(!ok)Fail(why,id);}
    static void Put(std::vector<uint8_t>& p,uint32_t at,uint32_t x) {
        for(uint32_t j=0;j<4;++j)p.at(at+j)=uint8_t(x>>(8*j));
    }
    static uint32_t Get(const std::vector<uint8_t>& p,uint32_t at) {
        uint32_t x=0;for(uint32_t j=0;j<4;++j)x|=uint32_t(p.at(at+j))<<(8*j);return x;
    }
    void Init() {
        Config::Reset();GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false));
        for(uint32_t i=0;i<nodes;++i) {
            auto node=CreateObject<Node>();hosts.push_back(node);
            Check(node->GetId()==i,"unexpected_node_id");
            auto sw=CreateObject<UbSwitch>();node->AggregateObject(sw);sw->SetNodeType(UB_DEVICE);
            auto c=CreateObject<UbController>();node->AggregateObject(c);
            c->CreateUbFunction();c->CreateUbTransaction();
            for(uint32_t j=0;j<nodes-1;++j) {
                auto p=CreateObject<UbPort>();p->SetAddress(Mac48Address::Allocate());node->AddDevice(p);
            }
            c->CreateDefaultCtpEntity(1);c->FreezeCtpEntities();
            sw->Init();UbCongestionControl::Create(UB_SWITCH)->OnSwitchAttached(sw);
            Check(c->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor(
                [this](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){Target(req,done);}
            )),"target_executor_registration");
        }
        for(uint32_t a=0;a<nodes;++a)for(uint32_t b=a+1;b<nodes;++b) {
            auto pa=DynamicCast<UbPort>(hosts[a]->GetDevice(Port(a,b)));
            auto pb=DynamicCast<UbPort>(hosts[b]->GetDevice(Port(b,a)));
            auto link=CreateObject<UbLink>();pa->Attach(link);pb->Attach(link);
            for(auto [src,dst]:{Key{a,b},Key{b,a}}) {
                auto routing=hosts[src]->GetObject<UbSwitch>()->GetRoutingProcess();
                routing->GetRoutingTable().AddShortestRoute(NodeIdToIp(dst).Get(),{uint16_t(Port(src,dst))});
                routing->GetRoutingTable().AddShortestRoute(NodeIdToIp(dst,Port(dst,src)).Get(),{uint16_t(Port(src,dst))});
            }
            Connection c;c.ownerNodeId=a;c.node1=a;c.node2=b;c.port1=Port(a,b);c.port2=Port(b,a);
            c.tpn1=Tpn(a,b);c.tpn2=Tpn(b,a);c.priority=7;c.metrics=0;
            Ctrl(a)->GetTpConnManager()->AddUnilateralConnection(c,a);
            Ctrl(b)->GetTpConnManager()->AddUnilateralConnection(c,b);
            for(auto [src,dst]:{Key{a,b},Key{b,a}}) {
                auto tm=Ctrl(src)->GetTransportChannelManager();
                tm->CreateTp(src,dst,Port(src,dst),Port(dst,src),7,Tpn(src,dst),Tpn(dst,src),UbCongestionControl::Create(UB_DEVICE));
                auto tp=tm->GetTp(Tpn(src,dst));tps[{src,dst}]=tp;
                tp->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>(
                    [this,src](uint32_t,uint32_t id,uint32_t wire){Sent(src,id,wire);}));
            }
        }
        manager=std::make_unique<PairJettyManager>([this](uint32_t rank){return Ctrl(rank);},nodes,segment,
                    MakeCallback(&LifecycleProbe::Client,this));
        // Local-only work stays entirely outside transport. Manager also rejects accidental local keys.
        for(uint32_t i=0;i<nodes;++i) {
            std::vector<uint8_t> input(97),target(97);
            for(uint32_t j=0;j<input.size();++j)input[j]=uint8_t(i*43+j*17);
            target=input;Check(target==input,"local_copy_bytes");++localCopies;
            try {manager->Get(i,i,0);Fail("manager_accepted_local_pair");}
            catch(const std::runtime_error&) {++localRejections;}
        }
        Check(manager->Size()==0,"local_created_jetty");
        for(uint32_t i=0;i<nodes;++i) {
            auto snap=Ctrl(i)->GetUbFunction()->GetJettyStorageSnapshot();
            Check(snap.taskScopedJetties==0 && snap.reusableJetties==0,"local_storage_created_jetty");
        }
        std::set<uint32_t> ids;
        for(uint32_t a=0;a<nodes;++a)for(uint32_t b=0;b<nodes;++b)if(a!=b && (mode=="directional" || (a==0&&b==1))) {
            auto e=manager->Get(a,b,Tpn(a,b));entries[{a,b}]=e;
            Check(ids.insert(e.id).second,"directional_jetty_id_collision");
            Check(e.id==a*nodes+b+1,"pair_id_formula");
            Check(manager->Get(a,b,Tpn(a,b)).jetty==e.jetty,"pair_not_cached");
            e.jetty->SetWqeCompletionCallback(MakeCallback(&LifecycleProbe::Terminal,this));
            try {manager->Get(a,b,Tpn(a,b)+10000);Fail("manager_accepted_changed_tp");}
            catch(const std::runtime_error&) {}
        }
        Check(manager->Size()==entries.size(),"pair_count");
        try {manager->Get(nodes,0,0);Fail("manager_accepted_invalid_rank");}
        catch(const std::runtime_error&) {}
    }
    void Prepare(uint32_t id,uint32_t src,uint32_t dst) {
        auto& w=works[id];w.src=src;w.dst=dst;w.jetty=entries.at({src,dst}).id;
        w.payload.resize(bytes);w.covered.resize(bytes);
        for(uint32_t off=0;off<bytes;off+=segment) {
            uint32_t len=std::min(segment,bytes-off);
            for(uint32_t j=0;j<len;++j)w.payload[off+j]=uint8_t((uint64_t(id)*73+(off+j)*131+src*19+dst*31)%251);
            Put(w.payload,off,magic);Put(w.payload,off+4,id);Put(w.payload,off+8,off);
            Put(w.payload,off+12,len);Put(w.payload,off+16,src);Put(w.payload,off+20,dst);
        }
    }
    void Submit(uint32_t id) {
        auto& w=works.at(id);Check(!w.submitted,"duplicate_submit",id);w.submitted=true;
        auto fn=Ctrl(w.src)->GetUbFunction();auto q=fn->CreateWqe(w.src,w.dst,bytes,id,UbTransactionOpcode::WRITE);
        q->SetOrderType(OrderType::ORDER_NO);q->SetExplicitPayload(Create<Packet>(w.payload.data(),w.payload.size()));
        Check(manager->Get(w.src,w.dst,Tpn(w.src,w.dst)).jetty==entries.at({w.src,w.dst}).jetty,"reuse_pointer_changed",id);
        ++active[{w.src,w.dst}];peak[{w.src,w.dst}]=std::max(peak[{w.src,w.dst}],active[{w.src,w.dst}]);
        Check(fn->SubmitWqe(q,w.jetty).status==UbWqeSubmissionStatus::ACCEPTED,"submit_rejected",id);
        Event("submit",id);
    }
    void Sent(uint32_t source,uint32_t id,uint32_t wire) {
        auto it=works.find(id);if(it==works.end()){Fail("unknown_sent_task",id);return;}
        auto& w=it->second;Key pair{w.src,w.dst};
        if(source!=w.src) {++responseTAs;Event("response_sent",id,0,wire);return;}
        uint32_t logical=logicalNext[pair]++;
        Check((logical&65535)==wire,"wire_not_modulo_logical",id);
        if(logical && wire==0)++wireWraps;
        Check(w.nextOffset<bytes,"too_many_sent_fragments",id);
        Check(w.logicalOffsets.emplace(logical,w.nextOffset).second,"logical_owner_repeated",id);
        Check(logicalOwners.emplace(std::make_pair(pair,logical),id).second,"logical_ssn_repeated",id);
        Event("request_sent",id,logical,wire,w.nextOffset);
        w.nextOffset+=std::min(segment,bytes-w.nextOffset);++w.sent;++requestTAs;
    }
    void Target(Ptr<const UbWqeSegment> req,UbTargetCompletion done) {
        uint32_t id=req->GetTaskId(),logical=req->GetTaSsn(),len=req->GetLogicalBytes();
        auto it=works.find(id);if(it==works.end()){Fail("unknown_target_task",id);return;}
        auto& w=it->second;bool valid=true;
        if(req->GetSrc()!=w.src || req->GetDest()!=w.dst || req->GetJettyNum()!=w.jetty || req->GetType()!=UbTransactionOpcode::WRITE || !req->HasTransactionResolved()) {
            Fail("target_metadata",id);valid=false;
        }
        auto own=logicalOwners.find({{w.src,w.dst},logical});
        if(own==logicalOwners.end()||own->second!=id){Fail("logical_owner_mismatch",id,logical);valid=false;}
        uint32_t off=0;
        if(!req->HasExplicitPayload()||len<24||req->GetExplicitPayload()->GetSize()!=len||req->GetPayloadBytes()!=len) {
            Fail("target_payload_size",id);valid=false;
        }else{
            std::vector<uint8_t> got(len);req->GetExplicitPayload()->CopyData(got.data(),len);off=Get(got,8);
            if(Get(got,0)!=magic||Get(got,4)!=id||Get(got,12)!=len||Get(got,16)!=w.src||Get(got,20)!=w.dst||
               off>=bytes||off%segment||len!=std::min(segment,bytes-off)) {Fail("decoded_payload_identity_offset",id);valid=false;}
            else {
                if(!std::equal(got.begin(),got.end(),w.payload.begin()+off)){Fail("target_byte_mismatch",id);valid=false;}
                if(std::any_of(w.covered.begin()+off,w.covered.begin()+off+len,[](uint8_t x){return x!=0;})){Fail("duplicate_target_bytes",id);valid=false;}
                auto x=w.logicalOffsets.find(logical);
                if(x==w.logicalOffsets.end()||x->second!=off){Fail("logical_vs_payload_offset_mismatch",id,logical);valid=false;}
                if(valid){std::fill(w.covered.begin()+off,w.covered.begin()+off+len,1);++w.received;verifiedBytes+=len;}
            }
        }
        Event("target_verified",id,logical,logical&65535,off,valid?"valid":"invalid");
        uint64_t delay=1000+(id%7)*500+(off/segment%2)*2000;
        if(mode=="cancel"||mode=="fail")delay=id==1001?200000:(id==1004?150000:1000);
        Simulator::Schedule(NanoSeconds(delay),[this,id,done,logical,off,valid]{
            if(valid)++works.at(id).executed;
            Event("target_done",id,logical,logical&65535,off);
            done(UbWorkExecutionResult{});done(UbWorkExecutionResult{});++duplicateDoneCalls;
        });
    }
    void Client(uint32_t id,uint32_t jetty) {
        auto it=works.find(id);if(it==works.end()){Fail("unknown_client_task",id);return;}
        auto& w=it->second;++w.client;++clientCount;
        Check(jetty==w.jetty&&w.client==1,"wrong_or_duplicate_client_identity",id);
        Check(w.expectedOutcome==UbWorkOutcome::COMPLETED,"client_called_on_failure",id);
        Check(w.received==3&&w.executed==3,"client_before_target_complete",id);
        Event("client_callback",id);
    }
    void Terminal(UbWqeCompletion c) {
        auto it=works.find(c.wqeId);if(it==works.end()){Fail("unknown_terminal_task",c.wqeId);return;}
        auto& w=it->second;++w.terminal;++terminalCount;
        Check(w.submitted&&c.jettyNum==w.jetty&&w.terminal==1,"wrong_or_duplicate_terminal_identity",c.wqeId);
        Check(c.outcome==w.expectedOutcome,"wrong_terminal_outcome",c.wqeId);
        if(c.outcome==UbWorkOutcome::COMPLETED)Check(w.received==3&&w.executed==3,"terminal_before_target_complete",c.wqeId);
        Check(active[{w.src,w.dst}]>0,"negative_active_count",c.wqeId);
        if(active[{w.src,w.dst}])--active[{w.src,w.dst}];
        Event("terminal_callback",c.wqeId,0,0,0,std::to_string(unsigned(c.outcome)));
    }
    void Plan() {
        if(mode=="directional") {
            uint32_t id=1001;
            for(const auto& [p,e]:entries)for(uint32_t j=0;j<4;++j) {
                Prepare(id,p.first,p.second);
                Simulator::Schedule(NanoSeconds(j<3?10:50000),&LifecycleProbe::Submit,this,id++);
            }
        }else if(mode=="wrap") {
            for(uint32_t j=0;j<count;++j) {
                Prepare(1001+j,0,1);
                // Fixed admission times, never gated by a completion/idle condition.
                Simulator::Schedule(NanoSeconds(10+uint64_t(j)*100),&LifecycleProbe::Submit,this,1001+j);
            }
        }else {
            for(uint32_t id=1001;id<=1005;++id)Prepare(id,0,1);
            works.at(1001).expectedOutcome=mode=="fail"?UbWorkOutcome::FAILED:UbWorkOutcome::CANCELED;
            for(uint32_t id=1001;id<=1003;++id)Simulator::Schedule(NanoSeconds(10),&LifecycleProbe::Submit,this,id);
            Simulator::Schedule(MicroSeconds(100),[this]{
                Check(works.at(1002).executed==3&&works.at(1003).executed==3,"later_targets_not_done_before_cancel");
                Check(works.at(1002).terminal==0&&works.at(1003).terminal==0,"missing_terminal_hole_precondition");
                Ctrl(0)->GetUbTransaction()->CompleteWqeOperation(entries.at({0,1}).id,1001,works.at(1001).expectedOutcome);
                Event("forced_terminal",1001);
            });
            Simulator::Schedule(MicroSeconds(120),&LifecycleProbe::Submit,this,1004);
            Simulator::Schedule(MicroSeconds(150),[this]{
                for(uint32_t id=1001;id<=1003;++id)Check(works.at(id).terminal==1,"cancel_failed_to_wake_later_wqe",id);
                Check(works.at(1001).client==0,"failure_client_callback");
                Check(works.at(1004).terminal==0,"late_reuse_not_active");
                Event("terminal_wakeup_checkpoint");
            });
            Simulator::Schedule(MicroSeconds(250),&LifecycleProbe::Submit,this,1005);
        }
        Simulator::Schedule(NanoSeconds(11),[this]{
            try{manager->CheckIdle();Fail("manager_missed_active_wqe");}
            catch(const std::runtime_error&){busyRejected=true;}
        });
    }
    int Run() {
        if(nodes<2||nodes>4||(mode!="directional"&&mode!="cancel"&&mode!="fail"&&mode!="wrap")||
           (mode!="directional"&&nodes!=2)||(mode=="wrap"&&(count<21846||count>25000)))return 2;
        {std::ofstream out(output+"-summary.txt");if(!out)return 2;out<<"status=INCOMPLETE_OR_NATIVE_ABORT\n";}
        events.open(output+"-events.csv");if(!events)return 2;
        events<<"time_ns,event,wqe_id,logical_ssn,wire_ssn,offset,detail\n";
        Init();Plan();Simulator::Stop(MilliSeconds(10));Simulator::Run();
        for(const auto& [id,w]:works) {
            Check(w.submitted&&w.terminal==1,"final_terminal_count",id);
            Check(w.client==(w.expectedOutcome==UbWorkOutcome::COMPLETED?1u:0u),"final_client_count",id);
            Check(w.sent==3&&w.received==3&&w.executed==3&&w.nextOffset==bytes,"final_fragment_count",id);
            Check(std::count(w.covered.begin(),w.covered.end(),uint8_t(1))==bytes,"final_target_coverage",id);
        }
        Check(busyRejected,"no_busy_check");
        for(const auto& [p,e]:entries) {
            Check(peak[p]>=2,"pair_lacked_overlapping_wqes");
            Check(active[p]==0&&e.jetty->IsIdle()&&e.jetty->GetActiveWqeCount()==0,"final_pair_not_idle");
            Check(e.jetty->GetTaSsnSndUnaForTest()==logicalNext[p]&&e.jetty->GetTaSsnSndNxtForTest()==logicalNext[p],"final_logical_window_not_drained");
        }
        for(uint32_t i=0;i<nodes;++i) {
            auto t=Ctrl(i)->GetUbTransaction();
            Check(t->GetResidentOperationCount()==0&&t->GetActiveOperationCount()==0&&t->GetResidentSegmentCount()==0,"transaction_not_reclaimed");
        }
        for(const auto& [p,tp]:tps)Check(tp->GetOutstandingUnackedSegmentCount()==0,"transport_not_drained");
        if(mode=="wrap")Check(requestTAs>65536&&wireWraps>=1&&logicalNext[{0,1}]>65536,"wrap_not_exercised");
        try{manager->CheckIdle();idleChecked=true;}catch(const std::runtime_error&){Fail("manager_final_idle_failed");}
        // Manager ownership ends before simulator/node disposal, and only after verified idle.
        if(idleChecked){manager.reset();managerDestroyed=true;Event("manager_destroyed_after_idle");}
        auto terminalBeforeDestroy=terminalCount,clientBeforeDestroy=clientCount;
        entries.clear();tps.clear();
        Simulator::Destroy();
        Check(terminalCount==terminalBeforeDestroy&&clientCount==clientBeforeDestroy,"callback_during_idle_destruction");
        std::ofstream out(output+"-summary.txt");
        out<<"status="<<(failures.empty()?"PASS":"FAIL")<<"\nmode="<<mode<<"\nnodes="<<nodes
           <<"\nwqes="<<works.size()<<"\nterminal_callbacks="<<terminalCount<<"\nclient_success_callbacks="<<clientCount
           <<"\nrequest_ta_segments="<<requestTAs<<"\nresponse_ta_segments="<<responseTAs<<"\nverified_bytes="<<verifiedBytes
           <<"\nwire_wraps="<<wireWraps<<"\nduplicate_done_calls="<<duplicateDoneCalls
           <<"\nlocal_copies_no_jetty="<<localCopies<<"\nlocal_pair_rejections="<<localRejections
           <<"\nbusy_check_rejected="<<busyRejected<<"\nidle_verified="<<idleChecked<<"\nmanager_destroyed_before_simulator="<<managerDestroyed
           <<"\nfailures="<<failures.size()<<'\n';
        for(const auto& [p,n]:logicalNext)out<<"pair="<<p.first<<"->"<<p.second<<" logical_ta_next="<<n<<" peak_outstanding="<<peak[p]<<'\n';
        for(const auto& f:failures)out<<"failure="<<f<<'\n';
        std::cout<<"status="<<(failures.empty()?"PASS":"FAIL")<<" mode="<<mode<<" nodes="<<nodes<<" WQEs="<<works.size()<<" TAs="<<requestTAs<<" failures="<<failures.size()<<'\n';
        return failures.empty()?0:1;
    }
};
int main(int argc,char** argv) {
    LifecycleProbe p;CommandLine cmd;cmd.AddValue("mode","directional/cancel/fail/wrap",p.mode);
    cmd.AddValue("nodes","2..4 nodes (directional only)",p.nodes);cmd.AddValue("count","Wrap WQEs",p.count);
    cmd.AddValue("output","Output prefix",p.output);cmd.Parse(argc,argv);return p.Run();
}
