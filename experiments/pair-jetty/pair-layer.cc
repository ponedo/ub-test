// SPDX-License-Identifier: GPL-2.0-only
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "../no-balancing-layer/nb-tracker.h"
#include "pair-jetty-manager.h"
#include "../direct-weight-forward/weight-distribution.h"
#include <filesystem>
#include <fstream>
#include <set>
#include <vector>
#include <memory>
#include <map>
#include <deque>
#include <chrono>
#include <array>
#include <iomanip>
#include <sstream>
using namespace ns3;
void Require(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
struct Assignment {uint32_t token,rank,expert,source,target,physical;};
struct Transfer {
    uint32_t stage,id,source,target,physical,bytes;
    uint32_t offset=0,sourcePhysical=0,jettyId=0,nextOffset=0;
    std::map<uint32_t,uint32_t> segmentOffsets;
    std::map<uint32_t,std::deque<uint32_t>> pendingResponses;
    std::vector<uint32_t> dependencies;
    bool sent=false,ready=false,senderDone=false;
    std::unique_ptr<ChunkTracker> tracker;
    std::vector<uint8_t> data;
};
class Layer {
public:
    uint32_t n,e,k,t,dim,ff,dtype,segment,peak,util,setup,seed,linkGbps,linkDelayNs;
    uint32_t matrices,weightBytes,planningNs,rerouteNs,weightCompleteNs,balanced,strategy;
    uint32_t bytes,receivedTokens=0,senderCount=0,remoteCount=0,pendingWeights=0;
    bool planningDone=false,rerouteDone=false,weightsDone=false,dispatchStarted=false,traceOn=false;
    std::vector<uint32_t> placement,expected,arrived,contributions,physicalArrived;
    std::vector<bool> started,finished,weightReady;
    std::vector<PhysicalExpert> physical;
    std::map<uint32_t,uint32_t> pIndex;
    std::vector<Assignment> assignments;
    std::vector<Transfer> transfers;
    std::vector<Ptr<Node>> nodes;
    std::ofstream log;
    std::string fault,capacityMetrics;
    WeightDistributionOptions weightOptions;
    std::string jettyMode="pair",logLevel="summary";bool combineLogged=false;
#include "online-validation.inc"
    std::unique_ptr<PairJettyManager> pairJetties;
    std::map<std::pair<uint32_t,uint32_t>,uint32_t> nextSsn;
    std::ofstream admissions;
    uint64_t payloadBudgetBytes=UINT64_C(256)*1024*1024,weightTaskLimit=20000;
    static uint64_t CheckedMul(uint64_t a,uint64_t b){Require(!b||a<=UINT64_MAX/b,"capacity multiplication overflow");return a*b;}
    static uint64_t CheckedAdd(uint64_t a,uint64_t b){Require(a<=UINT64_MAX-b,"capacity addition overflow");return a+b;}
    uint64_t taCount=0;uint32_t jettyCount=0;
    void SenderComplete(uint32_t task,uint32_t jetty){
        auto& x=transfers.at(task);Require(x.jettyId==jetty&&!x.senderDone,"sender identity/duplicate");
        Require(x.ready,"sender completed before target data ready");
        if(fault=="missing-wqe")return;
        x.senderDone=true;++senderCount;TE("sender_complete",task,x.source);
        if(fault=="duplicate-completion")TE("sender_complete",task,x.source);
    }
    uint32_t reorderNs=0,slowRelayRank=UINT32_MAX,slowRelayNs=0;
    std::set<std::tuple<uint32_t,uint32_t,uint32_t>> readyGroups;
    std::vector<std::vector<uint8_t>> weightData;
    std::vector<std::unique_ptr<ChunkTracker>> weightCoverage;
    std::vector<std::vector<uint32_t>> dependents;
    static constexpr uint64_t startPs=1000;
    PhysicalExpert& P(uint32_t id){Require(pIndex.count(id),"unknown physical ID");return physical[pIndex.at(id)];}
    void Event(std::string event,int stage=-1,int id=-1,int node=-1,uint64_t off=0,uint64_t len=0,int task=-1){
        Audit(event,stage,id,node,off,len,task);
        if(logLevel=="events"){
            auto key=[&](const std::string& name){log<<Simulator::Now().GetPicoSeconds()<<','<<name<<','<<stage<<','<<id<<','<<node<<','<<off<<','<<len<<','<<task<<'\n';};
            if(event=="dispatch_gate"){key("dispatch_start");if(assignments.empty()){key("dispatch_end");key("combine_start");key("combine_end");}}
            if(event=="data_ready"&&stage==0&&stageReadyCounts[0]==assignments.size())key("dispatch_end");
            if(event=="send"&&stage==1&&spans["send"][0]<=Simulator::Now().GetPicoSeconds()&&!combineLogged){combineLogged=true;key("combine_start");}
            if(event=="data_ready"&&stage==1&&stageReadyCounts[1]==assignments.size())key("combine_end");
            if(event=="edge_ready")key("chunk_ready");
            if(event=="weight_ready")key("replica_weight_ready");
            if(event=="send"&&stage==2&&!transfers[task].dependencies.empty())key("relay_forward_start");
        }
        if(logLevel=="summary" || (logLevel=="events"&&!KeyEvent(event,stage,task)))return;
        log<<Simulator::Now().GetPicoSeconds()<<','<<event<<','<<stage<<','<<id<<','<<node<<','<<off<<','<<len<<','<<task<<'\n';
    }
    void TE(std::string event,uint32_t task,uint32_t node,uint64_t off=0,uint64_t len=0){auto& x=transfers.at(task);Event(event,x.stage,x.id,node,off,len,task);}
    uint8_t InputByte(uint32_t aid,uint64_t i) const {
        auto a=assignments.at(aid);return uint8_t((uint64_t(seed)+a.token*131ULL+a.expert*71ULL+a.rank*43ULL+i*17+(i>>8)*29)%256);
    }
    uint8_t ResultByte(uint32_t aid,uint8_t input) const {return input ^ uint8_t(assignments.at(aid).expert*37+165);}
    uint8_t WeightByte(uint32_t pid,uint64_t i){auto& p=P(pid);return uint8_t((uint64_t(seed)+p.expert*71ULL+p.mainRank*131ULL+p.mainId*43ULL+i*17+(i>>8)*29)%256);}
    uint8_t ExpectedByte(uint32_t task,uint64_t i){auto& x=transfers.at(task);if(x.stage==2)return WeightByte(x.physical,x.offset+i);auto b=InputByte(x.id,i);return x.stage?ResultByte(x.id,b):b;}
    void AddTransfer(uint32_t stage,uint32_t id,uint32_t src,uint32_t dst,uint32_t pid,uint32_t size){
        Transfer x{stage,id,src,dst,pid,size};x.tracker=std::make_unique<ChunkTracker>(size);x.data.resize(size);transfers.push_back(std::move(x));
    }
    void Read(const std::string& path){
        std::ifstream f(path);Require(bool(f),"missing input");
        uint64_t v[14];for(auto& x:v)Require(bool(f>>x)&&x<=UINT32_MAX,"invalid integer config");
        n=v[0];e=v[1];k=v[2];t=v[3];dim=v[4];ff=v[5];dtype=v[6];segment=v[7];peak=v[8];util=v[9];setup=v[10];seed=v[11];linkGbps=v[12];linkDelayNs=v[13];
        uint64_t z[8];for(auto& x:z)Require(bool(f>>x)&&x<=UINT32_MAX,"invalid execution config");
        matrices=z[0];weightBytes=z[1];planningNs=z[2];rerouteNs=z[3];weightCompleteNs=z[4];balanced=z[5];strategy=z[6];uint32_t np=z[7];
        Require(n>=1&&n<=72&&e>=1&&e<=512&&k>=1&&k<=e&&t<=100000,"invalid dimensions");
        Require(dim>=1&&dim<=16384&&ff>=1&&ff<=65536&&dtype>=1&&dtype<=8&&segment>=1&&segment<=65536&&peak>=1&&peak<=10000000&&util>=1&&util<=1000&&setup<=100000000,"invalid model");
        Require(linkGbps>=1&&linkGbps<=10000&&linkDelayNs<=1000000,"invalid link");
        Require((matrices==2||matrices==3)&&weightBytes>0&&weightBytes<=64*1024*1024&&planningNs<=100000000&&rerouteNs<=100000000&&weightCompleteNs<=100000000&&balanced<=1&&strategy<=2,"unsupported execution parameters/strategy");
        Require(np>=e&&np<=1024,"physical count");
        Require(payloadBudgetBytes>0&&payloadBudgetBytes<=UINT64_C(8)*1024*1024*1024,"payload budget range");Require(weightTaskLimit>0&&weightTaskLimit<=1000000,"weight task limit range");
        bytes=dim*dtype;const auto assignmentCount=CheckedMul(t,k);const auto logicalPayload=CheckedAdd(CheckedMul(CheckedMul(assignmentCount,bytes),2),CheckedMul(np-e,weightBytes));
        Require(assignmentCount<=100000&&logicalPayload<=payloadBudgetBytes,"payload bound");
        placement.resize(e);for(auto& r:placement)Require(bool(f>>r)&&r<n,"main placement");
        std::set<std::pair<uint32_t,uint32_t>> unique;std::vector<uint32_t> mains(e,0);
        for(uint32_t i=0;i<np;++i){PhysicalExpert p;Require(bool(f>>p.id>>p.expert>>p.rank>>p.replica>>p.quota>>p.mainId>>p.mainRank),"physical input");
            Require(p.id<1024&&p.expert<e&&p.rank<n&&p.replica<=1&&unique.insert({p.expert,p.rank}).second&&!pIndex.count(p.id),"physical identity");
            if(!p.replica){Require(p.rank==placement[p.expert]&&p.mainId==p.id&&p.mainRank==p.rank,"main moved");++mains[p.expert];}
            else {Require(p.quota>0&&p.rank!=placement[p.expert],"invalid replica");}
            pIndex[p.id]=physical.size();physical.push_back(p);
        }
        for(auto count:mains)Require(count==1,"main absent/duplicate");
        for(auto p:physical){auto& main=P(p.mainId);Require(!main.replica&&main.expert==p.expert&&main.rank==p.mainRank,"weight provenance");}
        expected.assign(n,0);arrived.assign(n,0);contributions.assign(t,0);started.assign(n,false);finished.assign(n,false);physicalArrived.assign(np,0);weightReady.resize(np);
        for(uint32_t i=0;i<np;++i)weightReady[i]=!physical[i].replica;
        std::vector<uint32_t> counts(np,0);
        for(uint32_t token=0;token<t;++token){uint32_t source;Require(bool(f>>source)&&source<n,"source");std::set<uint32_t> ids;
            for(uint32_t rank=0;rank<k;++rank){uint32_t expert,pid;Require(bool(f>>expert>>pid)&&expert<e&&ids.insert(expert).second,"top-k");auto& p=P(pid);Require(p.expert==expert,"logical routing altered");assignments.push_back({token,rank,expert,source,p.rank,pid});++expected[p.rank];++counts[pIndex.at(pid)];}
        }
        for(uint32_t i=0;i<np;++i)Require(counts[i]==physical[i].quota,"physical quota mismatch");
        Require(bool(f>>weightOptions.chunkBytes>>weightOptions.minReplicas>>weightOptions.maxRelays>>weightOptions.minFanoutGain>>weightOptions.forceRelay>>weightOptions.shardCut>>reorderNs>>slowRelayRank>>slowRelayNs),"relay options");
        weightOptions.nodes=n;weightOptions.domain.assign(n,0);
        Require(weightOptions.chunkBytes>0&&weightOptions.chunkBytes<=64*1024*1024&&weightOptions.maxRelays>0&&weightOptions.maxRelays<=72&&reorderNs<=100000000&&slowRelayNs<=100000000&&(slowRelayRank==UINT32_MAX||slowRelayRank<n),"relay option bounds");
        uint32_t orderSize;Require(bool(f>>orderSize)&&orderSize==np,"ordinal size");
        std::vector<PhysicalExpert> ordered;std::set<uint32_t> seenOrder;
        for(uint32_t i=0;i<np;++i){uint32_t id;Require(bool(f>>id)&&seenOrder.insert(id).second,"ordinal duplicate");ordered.push_back(P(id));}
        std::string extra;Require(!(f>>extra),"extra input");
        // Predict count before generating ranges/edges, never reserve the configured maximum.
        std::map<uint32_t,uint64_t> replicaCounts;for(auto& p:physical)if(p.replica)++replicaCounts[p.expert];
        uint64_t predictedEdges=0;
        for(auto [expert,count]:replicaCounts){uint64_t nr=0;if(count>1){while((nr+1)*(nr+1)<=count)++nr;nr=std::min({nr,uint64_t(weightOptions.maxRelays),count-1});}
            bool relay=nr&&(weightOptions.forceRelay||(count>=weightOptions.minReplicas&&count-std::max(nr,(count-nr+nr-1)/nr)>=weightOptions.minFanoutGain));
            uint64_t pieces=1;if(strategy==2&&relay){auto cut=weightOptions.shardCut;Require(cut<weightBytes,"shard range");auto ceilChunk=[&](uint64_t value){return (value+weightOptions.chunkBytes-1)/weightOptions.chunkBytes;};pieces=cut?CheckedAdd(ceilChunk(cut),ceilChunk(weightBytes-cut)):ceilChunk(weightBytes);}
            predictedEdges=CheckedAdd(predictedEdges,CheckedMul(count,pieces));}
        Require(predictedEdges<=weightTaskLimit,"weight task count bound");
        std::vector<WeightEdge> edges;
        if(strategy==0)edges=DirectWeightDistribution().Edges(physical,weightBytes);
        else if(strategy==1)edges=TwoStageRelay(weightOptions).Edges(ordered,weightBytes);
        else edges=ChunkStreamingRelay(weightOptions).Edges(ordered,weightBytes);
        Require(edges.size()==predictedEdges&&edges.size()<=weightTaskLimit,"weight task count bound");
        Require(CheckedAdd(CheckedMul(assignments.size(),2),edges.size())<=INT32_MAX,"task ID/index range");
        uint64_t segmentTotal=CheckedMul(CheckedMul(assignments.size(),2),(uint64_t(bytes)+segment-1)/segment);
        for(auto& edge:edges)segmentTotal=CheckedAdd(segmentTotal,(uint64_t(edge.bytes)+segment-1)/segment);
        Require(segmentTotal<=UINT32_MAX,"logical SSN/count range");
        for(uint32_t stage=0;stage<2;++stage)for(uint32_t aid=0;aid<assignments.size();++aid){auto a=assignments[aid];AddTransfer(stage,aid,stage?a.target:a.source,stage?a.source:a.target,a.physical,bytes);}
        for(auto edge:edges){
            auto& src=P(edge.sourcePhysical);auto& dst=P(edge.targetPhysical);
            Require(src.expert==dst.expert&&dst.replica&&edge.bytes&&edge.offset<weightBytes&&edge.bytes<=weightBytes-edge.offset,"weight edge range/identity");
            AddTransfer(2,dst.id,src.rank,dst.rank,dst.id,edge.bytes);
            transfers.back().offset=edge.offset;transfers.back().sourcePhysical=src.id;
        }
        dependents.resize(transfers.size());
        for(uint32_t task=2*assignments.size();task<transfers.size();++task){
            auto& x=transfers[task];if(!P(x.sourcePhysical).replica)continue;
            auto scope=edges[task-2*assignments.size()].sourceDependency;
            ChunkTracker coverage(scope==WeightReadyScope::FullExpert?weightBytes:x.bytes);
            for(uint32_t parent=2*assignments.size();parent<transfers.size();++parent){
                auto& y=transfers[parent];
                if(scope==WeightReadyScope::GroupChunk){
                    // One upstream Stage-I fan-out task publishes all relay flags together.
                    // Aggregate its per-edge target completions without using sender ACKs.
                    if(P(y.sourcePhysical).replica||P(y.physical).expert!=P(x.physical).expert||y.offset!=x.offset||y.bytes!=x.bytes)continue;
                }else if(y.physical!=x.sourcePhysical)continue;
                x.dependencies.push_back(parent);dependents[parent].push_back(task);
                if(y.physical==x.sourcePhysical)coverage.Notify(parent,scope==WeightReadyScope::GroupChunk?0:y.offset,y.bytes);
            }
            Require(coverage.Complete(),"relay source coverage graph");
        }
        weightData.resize(np);weightCoverage.resize(np);
        for(uint32_t i=0;i<np;++i)if(physical[i].replica){
            weightData[i].resize(weightBytes);weightCoverage[i]=std::make_unique<ChunkTracker>(weightBytes);++pendingWeights;
        }
        if(!balanced)Require(!pendingWeights&&!planningNs&&!rerouteNs,"baseline cannot replicate/plan");
    }
  Ptr<UbController> Ctrl(uint32_t node) {return nodes[node]->GetObject<UbController>();}
  void Init(uint32_t node,bool host,uint32_t count) {
    nodes[node]=CreateObject<Node>();auto sw=CreateObject<UbSwitch>();nodes[node]->AggregateObject(sw);sw->SetNodeType(host?UB_DEVICE:UB_SWITCH);
    if(host) {auto c=CreateObject<UbController>();nodes[node]->AggregateObject(c);c->CreateUbFunction();c->CreateUbTransaction();}
    for(uint32_t p=0;p<count;++p) {
      auto port=CreateObject<UbPort>();port->SetAddress(Mac48Address::Allocate());port->SetAttribute("UbDataRate",DataRateValue(DataRate(uint64_t(linkGbps)*1000000000)));nodes[node]->AddDevice(port);
    }
    sw->Init();UbCongestionControl::Create(UB_SWITCH)->OnSwitchAttached(sw);
  }
  void Route(uint32_t node,uint32_t dest,uint16_t out) {
    auto r=nodes[node]->GetObject<UbSwitch>()->GetRoutingProcess();
    r->GetRoutingTable().AddShortestRoute(NodeIdToIp(dest).Get(),{out});
    r->GetRoutingTable().AddShortestRoute(NodeIdToIp(dest,0).Get(),{out});
  }
  uint32_t Tpn(uint32_t a,uint32_t b) const {return a*n+b+1;}

    void Pair(uint32_t a,uint32_t b){
        Connection c;c.ownerNodeId=a;c.node1=a;c.node2=b;c.port1=c.port2=0;c.tpn1=Tpn(a,b);c.tpn2=Tpn(b,a);c.priority=7;c.metrics=0;
        Ctrl(a)->GetTpConnManager()->AddUnilateralConnection(c,a);Ctrl(b)->GetTpConnManager()->AddUnilateralConnection(c,b);
        for(auto [src,dst]:{std::pair{a,b},std::pair{b,a}}){
            Ctrl(src)->GetTransportChannelManager()->CreateTp(src,dst,0,0,7,Tpn(src,dst),Tpn(dst,src),UbCongestionControl::Create(UB_DEVICE));
            Ctrl(src)->GetTransportChannelManager()->GetTp(Tpn(src,dst))->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this,src](uint32_t,uint32_t task,uint32_t ssn){
                auto& x=transfers.at(task);
                if(src==x.source){
                    uint32_t logical=nextSsn[{x.source,x.jettyId}]++;
                    Require((logical&65535)==ssn,"unexpected wire SSN progression");
                    uint64_t off=x.nextOffset;Require(off<x.bytes,"TA offset");
                    uint32_t len=std::min<uint64_t>(segment,x.bytes-off);
                    Require(x.segmentOffsets.emplace(logical,off).second,"duplicate TA admission");
                    x.pendingResponses[ssn].push_back(logical);x.nextOffset+=len;++taCount;
                    if(logLevel=="debug")admissions<<Simulator::Now().GetPicoSeconds()<<','<<task<<','<<x.jettyId<<','<<logical<<','<<off<<','<<len<<'\n';
                    TE("ta_admitted",task,src,off,len);
                }else{
                    // Responses retain the request SSN, never allocate payload offsets.
                    auto it=x.pendingResponses.find(ssn);
                    Require(it!=x.pendingResponses.end()&&!it->second.empty(),"response missing request admission");
                    uint32_t logical=it->second.front();it->second.pop_front();
                    if(it->second.empty())x.pendingResponses.erase(it);
                    TE("ta_response_admitted",task,src,x.segmentOffsets.at(logical),0);
                }
            }));
        }
    }
    void Topology(const std::string& out){
        GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false));UbUtils::Get();
        for(auto key:{"UB_TRACE_ENABLE","UB_PACKET_TRACE_ENABLE","UB_PORT_TRACE_ENABLE","UB_RECORD_PKT_TRACE"})GlobalValue::Bind(key,BooleanValue(logLevel=="debug"));
        if(logLevel=="debug"){std::filesystem::create_directories(out+"/native/runlog");UbUtils::SetTracePathForTest(out+"/native");}traceOn=true;
        nodes.resize(n+1);for(uint32_t i=0;i<n;++i)Init(i,true,1);Init(n,false,n);
        for(uint32_t i=0;i<n;++i){auto link=CreateObject<UbLink>();link->SetAttribute("Delay",TimeValue(NanoSeconds(linkDelayNs)));DynamicCast<UbPort>(nodes[i]->GetDevice(0))->Attach(link);DynamicCast<UbPort>(nodes[n]->GetDevice(i))->Attach(link);Route(n,i,i);for(uint32_t j=0;j<n;++j)if(i!=j)Route(i,j,0);}
        std::set<std::pair<uint32_t,uint32_t>> pairs;
        for(auto& x:transfers)if(x.source!=x.target)pairs.insert(std::minmax(x.source,x.target));
        for(auto [a,b]:pairs)Pair(a,b);
        pairJetties=std::make_unique<PairJettyManager>([this](uint32_t rank){return Ctrl(rank);},n,segment,MakeCallback(&Layer::SenderComplete,this));
        for(uint32_t task=0;task<transfers.size();++task){auto& x=transfers[task];if(x.source==x.target)continue;++remoteCount;
            if(jettyMode=="pair"){
                const auto& entry=pairJetties->Get(x.source,x.target,Tpn(x.source,x.target));x.jettyId=entry.id;
            }else{
                x.jettyId=task;auto fn=Ctrl(x.source)->GetUbFunction();fn->CreateJetty(x.source,x.target,task);
                Require(Ctrl(x.source)->GetUbTransaction()->JettyBindTp(x.source,x.target,task,false,{Tpn(x.source,x.target)}),"bind");
                auto jetty=fn->GetJetty(task);jetty->SetTaSegmentBytes(segment);
                jetty->SetClientCallback(MakeCallback(&Layer::SenderComplete,this));++jettyCount;
            }
        }
        if(jettyMode=="pair")jettyCount=pairJetties->Size();
        for(uint32_t node=0;node<n;++node)Require(Ctrl(node)->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor([this,node](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){
            uint32_t task=req->GetTaskId();auto& x=transfers.at(task);
            Require(req->GetJettyNum()==x.jettyId&&req->GetSrc()==x.source&&req->GetDest()==node&&node==x.target&&req->GetType()==UbTransactionOpcode::WRITE&&req->HasTransactionResolved()&&x.sent,"target identity");
            Require(x.segmentOffsets.count(req->GetTaSsn()),"target SSN missing admission");
            uint64_t off=x.segmentOffsets.at(req->GetTaSsn()),len=req->GetLogicalBytes();
            Require(off<x.bytes&&len==std::min<uint64_t>(segment,x.bytes-off)&&req->GetPayloadBytes()==len&&req->HasExplicitPayload()&&req->GetExplicitPayload()->GetSize()==len,"TA payload length");
            TE("target_received",task,node,off,len);std::vector<uint8_t> data(len);req->GetExplicitPayload()->CopyData(data.data(),len);Validate(task,off,data);TE("payload_verified",task,node,off,len);
            // Target execution completion, not sender WQE completion, grants ready.
            auto complete=[this,task,node,off,len,ssn=req->GetTaSsn(),done]{
                done(UbWorkExecutionResult{});TE("target_complete",task,node,off,len);
                bool fresh=transfers[task].tracker->Notify(ssn,off,len);
                if(fault=="duplicate-notify"&&transfers[task].stage==2){
                    Require(!transfers[task].tracker->Notify(ssn,off,len),"duplicate notification advanced coverage");
                    TE("duplicate_ignored",task,node,off,len);
                }
                if(fresh)Ready(task);
            };
            uint64_t delay=x.stage==2?weightCompleteNs:0;
            if(x.stage==2&&!P(x.sourcePhysical).replica&&x.offset==0)delay+=reorderNs;
            if(x.stage==2&&!P(x.sourcePhysical).replica&&x.target==slowRelayRank)delay+=slowRelayNs;
            if(delay)Simulator::Schedule(NanoSeconds(delay),complete);else complete();
        })),"target executor");
        txBytes.assign(n+1,0);rxBytes.assign(n+1,0);txPackets.assign(n+1,0);rxPackets.assign(n+1,0);
        for(uint32_t rank=0;rank<nodes.size();++rank)for(uint32_t port=0;port<nodes[rank]->GetNDevices();++port){
            auto p=DynamicCast<UbPort>(nodes[rank]->GetDevice(port));
            p->TraceConnectWithoutContext("PortTxNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this,rank](uint32_t,uint32_t,uint32_t size){++txPackets[rank];txBytes[rank]+=size;}));
            p->TraceConnectWithoutContext("PortRxNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this,rank](uint32_t,uint32_t,uint32_t size){++rxPackets[rank];rxBytes[rank]+=size;}));
        }
        if(logLevel=="debug"){UbUtils::Get()->TopoTraceConnect();for(auto [a,b]:pairs){UbUtils::Get()->SingleTpTraceConnect(a,Tpn(a,b));UbUtils::Get()->SingleTpTraceConnect(b,Tpn(b,a));}}
    }
    void Validate(uint32_t task,uint64_t off,const std::vector<uint8_t>& data){auto wall=std::chrono::steady_clock::now();auto& x=transfers.at(task);for(size_t i=0;i<data.size();++i){Require(data[i]==ExpectedByte(task,off+i),"payload byte mismatch");x.data[off+i]=data[i];if(x.stage==2)weightData[pIndex.at(x.physical)][x.offset+off+i]=data[i];}verificationNs+=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-wall).count();}
    void Send(uint32_t task){auto& x=transfers.at(task);Require(!x.sent,"duplicate forwarding");
        Require(planningDone,"send before planning");if(x.stage==0)Require(dispatchStarted,"dispatch gate");if(x.stage==1)Require(finished[x.source],"combine before compute");
        if(x.stage==2)for(auto parent:x.dependencies)Require(transfers[parent].ready,"relay before target chunk ready (including group)");
        if(x.stage==2&&strategy==2&&P(x.sourcePhysical).replica){
            auto key=std::make_tuple(P(x.physical).expert,x.offset,x.bytes);
            if(readyGroups.insert(key).second)Event("group_chunk_ready",2,P(x.physical).expert,P(x.physical).mainRank,x.offset,x.bytes);
        }
        x.sent=true;TE("send",task,x.source,0,x.bytes);std::vector<uint8_t> data(x.bytes);
        if(x.stage==2&&P(x.sourcePhysical).replica&&fault=="relay-buffer-byte")weightData[pIndex.at(x.sourcePhysical)][x.offset]^=1;
        for(uint32_t i=0;i<x.bytes;++i){
            if(x.stage==2&&P(x.sourcePhysical).replica)data[i]=weightData[pIndex.at(x.sourcePhysical)][x.offset+i];
            else data[i]=x.stage==1?ResultByte(x.id,transfers[x.id].data[i]):ExpectedByte(task,i);
        }
        if(x.stage==2&&P(x.sourcePhysical).replica){
            TE("relay_buffer_read",task,x.source,x.offset,x.bytes);
            if(fault=="relay-byte")data.back()^=1;
        }
        if((x.stage==2&&fault=="weight-byte")||fault=="payload-byte")data.back()^=1;
        if(fault=="early-wqe"&&x.source!=x.target)SenderComplete(task,x.jettyId);
        if(x.stage==2&&fault=="premature-ready")Ready(task);
        if(x.source==x.target){Simulator::ScheduleNow([this,task,data]{auto& x=transfers[task];Validate(task,0,data);TE("local_verified",task,x.target,0,x.bytes);Ready(task);});return;}
        auto fn=Ctrl(x.source)->GetUbFunction();auto wqe=fn->CreateWqe(x.source,x.target,x.bytes,task,UbTransactionOpcode::WRITE);wqe->SetExplicitPayload(Create<Packet>(data.data(),data.size()));Require(fn->SubmitWqe(wqe,x.jettyId).status==UbWqeSubmissionStatus::ACCEPTED,"WQE rejected");
    }
    uint64_t Duration(uint32_t count){__uint128_t num=__uint128_t(count)*2*matrices*dim*ff*1000000;uint64_t den=uint64_t(peak)*util;auto duration=num/den+(num%den!=0)+uint64_t(setup)*1000;Require(duration<UINT64_C(1000000000000000),"compute bound");return uint64_t(duration);}
    void Compute(uint32_t node){
        Require(dispatchStarted&&!started[node]&&arrived[node]==expected[node],"compute token/gate dependency");
        for(uint32_t i=0;i<physical.size();++i)if(physical[i].rank==node&&physical[i].quota)Require(weightReady[i]&&physicalArrived[i]==physical[i].quota,"compute weight/quota dependency");
        started[node]=true;if(!expected[node]){finished[node]=true;Event("compute_idle",-1,-1,node);return;}
        Event("compute_start",-1,-1,node,0,expected[node]);uint64_t elapsed=0;
        for(auto p:physical)if(p.rank==node&&p.quota){Simulator::Schedule(PicoSeconds(elapsed),[this,p]{Event("expert_start",-1,p.id,p.rank,0,p.quota);});elapsed+=Duration(p.quota);Simulator::Schedule(PicoSeconds(elapsed),[this,p]{Event("expert_end",-1,p.id,p.rank,0,p.quota);});}
        Simulator::Schedule(PicoSeconds(elapsed),[this,node]{finished[node]=true;Event("compute_end",-1,-1,node,0,expected[node]);for(uint32_t aid=0;aid<assignments.size();++aid)if(assignments[aid].target==node)Send(assignments.size()+aid);});
    }
    void Ready(uint32_t task){auto& x=transfers.at(task);Require(!x.ready,"duplicate ready");Require(x.sent&&(x.source==x.target||x.tracker->Complete()),"ready before target completion coverage");x.ready=true;
        TE(x.stage==2?"edge_ready":"data_ready",task,x.target,0,x.bytes);
        if(x.stage==2){
            auto idx=pIndex.at(x.physical);
            if(fault=="early-final-ready")FinalWeight(x.physical);
            if(weightCoverage[idx]->Notify(task,x.offset,x.bytes))FinalWeight(x.physical);
            if(fault=="early-group"&&strategy==2&&!P(x.sourcePhysical).replica){
                for(auto child:dependents[task])if(transfers[child].sourcePhysical==x.physical&&
                    !std::all_of(transfers[child].dependencies.begin(),transfers[child].dependencies.end(),[this](auto p){return transfers[p].ready;})){
                    TE("early_group_attempt",child,transfers[child].source);Send(child);
                }
            }
            for(auto child:dependents[task])if(!transfers[child].sent &&
                std::all_of(transfers[child].dependencies.begin(),transfers[child].dependencies.end(),[this](auto p){return transfers[p].ready;}))Send(child);
        }
        else if(x.stage==0){auto a=assignments[x.id];Require(++physicalArrived[pIndex.at(a.physical)]<=P(a.physical).quota,"quota exceeded");if(++arrived[x.target]==expected[x.target])Compute(x.target);}
        else{auto a=assignments[x.id];Require(++contributions[a.token]<=k,"duplicate contribution");if(contributions[a.token]==k){Event("token_complete",-1,a.token,a.source);if(++receivedTokens==t)Event("layer_end");}}
    }
    void FinalWeight(uint32_t pid){
        auto idx=pIndex.at(pid);Require(weightCoverage[idx]->Complete(),"final ready before full weight coverage");
        Require(!weightReady[idx]&&pendingWeights>0,"weight duplicate");weightReady[idx]=true;
        Event("weight_ready",2,pid,P(pid).rank,0,weightBytes);
        if(--pendingWeights==0){weightsDone=true;Event("weights_end");Gate();}
    }
    void Graph(std::ostream& graph){
        graph<<"task,stage,id,source,target,physical,bytes,source_physical,offset,dependencies\n";
        for(uint32_t task=0;task<transfers.size();++task){auto& x=transfers[task];
            graph<<task<<','<<x.stage<<','<<x.id<<','<<x.source<<','<<x.target<<','<<x.physical<<','<<x.bytes<<','<<x.sourcePhysical<<','<<x.offset<<',';
            for(size_t i=0;i<x.dependencies.size();++i)graph<<(i?";":"")<<x.dependencies[i];
            graph<<'\n';
        }
    }
    std::string GraphHash(){std::ostringstream graph;Graph(graph);auto text=graph.str();return Hex(Hash(14695981039346656037ULL,text.data(),text.size()));}
    void WriteArtifacts(const std::string& out){std::ofstream graph(out+"/executed-transfers.csv");Graph(graph);}
    void WritePayloads(const std::string& out){
        std::ofstream data(out+"/received-payloads.bin",std::ios::binary),index(out+"/payload-index.csv");
        index<<"task,offset,bytes\n";uint64_t off=0;
        for(uint32_t task=0;task<transfers.size();++task){auto& x=transfers[task];
            index<<task<<','<<off<<','<<x.bytes<<'\n';data.write(reinterpret_cast<const char*>(x.data.data()),x.bytes);off+=x.bytes;
        }
        Require(bool(data)&&bool(index),"payload artifact write");
    }
    void Gate(){if(dispatchStarted||!planningDone||!rerouteDone||!weightsDone)return;dispatchStarted=true;Event("dispatch_gate");for(uint32_t node=0;node<n;++node)if(!expected[node])Compute(node);if(!t)Event("layer_end");for(uint32_t aid=0;aid<assignments.size();++aid)Send(aid);}
    void Start(){Event("layer_start");for(auto p:physical)if(!p.replica)Event("main_weight_ready",2,p.id,p.rank,0,weightBytes);Event("planning_start");
        Simulator::Schedule(NanoSeconds(planningNs),[this]{planningDone=true;Event("planning_end");Event("reroute_start");Event("weights_start");
            Simulator::Schedule(NanoSeconds(rerouteNs),[this]{rerouteDone=true;Event("reroute_end");Gate();});
            if(!pendingWeights){weightsDone=true;Event("weights_end");Gate();}
            for(uint32_t task=2*assignments.size();task<transfers.size();++task){
                if(transfers[task].dependencies.empty()){Send(task);if(fault=="duplicate-weight")Send(task);}
                else if(fault=="early-relay")Send(task);
            }
            if(fault=="early-compute")Compute(0);
        });
    }
    void Run(const std::string& input,const std::string& out){
        Read(input);InitAudit();std::filesystem::create_directories(out);
        if(logLevel=="debug"){admissions.open(out+"/ta-identity.csv");admissions<<"time_ps,task,jetty,logical_ssn,offset,bytes\n";WriteArtifacts(out);}
        if(logLevel!="summary"){log.open(out+"/events.csv");Require(bool(log),"log");log<<"time_ps,event,stage,id,node,offset,bytes,task\n";}
        Topology(out);Simulator::Schedule(PicoSeconds(startPs),&Layer::Start,this);Simulator::Stop(Seconds(10));Simulator::Run();
        if(!capacityMetrics.empty()){
            std::ofstream metrics(capacityMetrics);Require(bool(metrics),"capacity metrics file");
            metrics<<"{\"simulator_events\":"<<Simulator::GetEventCount()<<",\"assignments\":"<<assignments.size()
                   <<",\"tasks\":"<<transfers.size()<<",\"remote_WQEs\":"<<remoteCount
                   <<",\"jettys\":"<<jettyCount<<",\"TA_count\":"<<taCount<<",\"sender_completions\":"<<senderCount<<",\"completed_tokens\":"<<receivedTokens<<"}\n";
        }
        for(auto& x:transfers)if(x.source!=x.target)Require(x.nextOffset==x.bytes&&x.pendingResponses.empty(),"incomplete TA admission/response tracking");
        Require(dispatchStarted&&receivedTokens==t&&pendingWeights==0&&senderCount==remoteCount,"unfinished layer");for(auto& x:transfers)Require(x.sent&&x.ready,"missing transfer");for(auto r:weightReady)Require(r,"missing weight");
        pairJetties->CheckIdle();FinalAudit();
        std::cout<<"PASS forward: N="<<n<<" assignments="<<assignments.size()<<" replicas="<<physical.size()-e<<" remote_WQEs="<<remoteCount<<" target-verified bytes\n";
        WriteSummary(out);if(logLevel=="debug")WritePayloads(out);admissions.close();log.close();UbUtils::Get()->Destroy();traceOn=false;Simulator::Destroy();
    }
};
int main(int argc,char** argv){Time::SetResolution(Time::PS);Layer layer;std::string input,out;CommandLine cmd;cmd.AddValue("input","validated execution input",input);cmd.AddValue("out","output directory",out);cmd.AddValue("capacityMetrics","optional post-run capacity counters",layer.capacityMetrics);cmd.AddValue("fault","test-only fault injection",layer.fault);cmd.AddValue("logLevel","summary (default), events, debug",layer.logLevel);cmd.AddValue("jettyMode","pair or per-wqe",layer.jettyMode);cmd.AddValue("payloadBudgetBytes","logical payload budget, default 256 MiB, maximum 8 GiB",layer.payloadBudgetBytes);cmd.AddValue("weightTaskLimit","weight WQE budget, default 20000, maximum 1000000",layer.weightTaskLimit);cmd.Parse(argc,argv);try{Require(layer.logLevel=="summary"||layer.logLevel=="events"||layer.logLevel=="debug","unknown log level");Require(layer.jettyMode=="pair"||layer.jettyMode=="per-wqe","unknown Jetty mode");Require(layer.fault=="payload-byte"||layer.fault=="early-wqe"||layer.fault=="missing-wqe"||layer.fault=="duplicate-completion"||layer.fault.empty()||layer.fault=="weight-byte"||layer.fault=="premature-ready"||layer.fault=="duplicate-weight"||layer.fault=="early-compute"||layer.fault=="early-group"||layer.fault=="relay-byte"||layer.fault=="relay-buffer-byte"||layer.fault=="duplicate-notify"||layer.fault=="early-relay"||layer.fault=="early-final-ready","unknown fault");Require(!input.empty()&&!out.empty(),"input/out");layer.Run(input,out);}catch(const std::exception& ex){if(!out.empty()){std::filesystem::create_directories(out);std::ofstream failed(out+"/validation.json");failed<<"{\"status\":\"FAIL\",\"error\":\""<<ex.what()<<"\"}\n";}if(layer.log){layer.Event("error");layer.log.flush();}if(layer.traceOn)UbUtils::Get()->Destroy();std::cerr<<"ERROR: "<<ex.what()<<'\n';return 2;}return 0;}
