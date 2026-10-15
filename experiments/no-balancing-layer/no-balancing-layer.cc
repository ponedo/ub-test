// SPDX-License-Identifier: GPL-2.0-only
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "nb-tracker.h"
#include <filesystem>
#include <fstream>
#include <set>
#include <vector>
#include <memory>
using namespace ns3;
void Require(bool ok,const std::string& why) { if(!ok) throw std::runtime_error(why); }
struct Assignment { uint32_t token,rank,expert,source,target; };
class Layer {
 public:
  uint32_t n,e,k,t,dim,ff,dtype,segment,peak,util,setup,seed,linkGbps,linkDelayNs;
  uint32_t bytes=0,receivedTokens=0,senderCount=0,remoteCount=0;
  std::vector<uint32_t> placement,expected,arrived,contributions;
  std::vector<Assignment> assignments;
  std::vector<Ptr<Node>> nodes;
  std::vector<bool> started,finished,ready;
  std::vector<std::unique_ptr<ChunkTracker>> trackers;
  std::vector<std::vector<uint8_t>> buffers;
  std::ofstream log;
  bool traceOn=false;
  static constexpr uint64_t startPs=1000;
  void Event(std::string event,int stage=-1,int aid=-1,int node=-1,uint64_t off=0,uint64_t len=0) {
    log<<Simulator::Now().GetPicoSeconds()<<','<<event<<','<<stage<<','<<aid<<','<<node<<','<<off<<','<<len<<'\n';
  }
  uint8_t InputByte(uint32_t aid,uint64_t i) const {
    auto a=assignments.at(aid);
    return uint8_t((uint64_t(seed)+a.token*131ULL+a.expert*71ULL+a.rank*43ULL+i*17+(i>>8)*29)%256);
  }
  uint8_t ResultByte(uint32_t aid,uint8_t input) const {return input ^ uint8_t(assignments.at(aid).expert*37+165);}
  uint8_t ExpectedByte(uint32_t stage,uint32_t aid,uint64_t i) const {
    auto b=InputByte(aid,i); return stage?ResultByte(aid,b):b;
  }
  void Read(const std::string& path) {
    std::ifstream f(path); Require(bool(f),"missing input");
    uint64_t vals[14]; for(auto& v:vals) Require(bool(f>>v)&&v<=UINT32_MAX,"invalid integer config");
    n=vals[0];e=vals[1];k=vals[2];t=vals[3];dim=vals[4];ff=vals[5];dtype=vals[6];segment=vals[7];peak=vals[8];util=vals[9];setup=vals[10];seed=vals[11];
    linkGbps=vals[12];linkDelayNs=vals[13];Require(linkGbps>=1&&linkGbps<=10000&&linkDelayNs<=1000000,"invalid link");
    Require(n>=1&&n<=256&&e>=1&&e<=4096&&k>=1&&k<=e&&t<=100000,"invalid dimensions");
    Require(dim>=1&&dim<=16384&&ff>=1&&ff<=65536&&dtype>=1&&dtype<=8&&segment>=1&&segment<=65536&&peak>=1&&peak<=10000000&&util>=1&&util<=1000&&setup<=100000000,"invalid model parameters");
    bytes=dim*dtype; Require(uint64_t(t)*k<=100000&&uint64_t(t)*k*bytes<=256*1024*1024,"case exceeds explicit-payload safety bound");
    placement.resize(e); for(auto& p:placement) Require(bool(f>>p)&&p<n,"invalid placement");
    expected.assign(n,0);arrived.assign(n,0);contributions.assign(t,0);started.assign(n,false);finished.assign(n,false);
    for(uint32_t token=0;token<t;++token) {
      uint32_t source;Require(bool(f>>source)&&source<n,"invalid token source");std::set<uint32_t> unique;
      for(uint32_t rank=0;rank<k;++rank) {
        uint32_t expert;Require(bool(f>>expert)&&expert<e&&unique.insert(expert).second,"invalid or duplicate top-k");
        assignments.push_back({token,rank,expert,source,placement[expert]});++expected[placement[expert]];
      }
    }
    std::string extra;Require(!(f>>extra),"extra input fields");
    ready.assign(2*assignments.size(),false); buffers.resize(2*assignments.size());
    for(size_t i=0;i<2*assignments.size();++i) {trackers.push_back(std::make_unique<ChunkTracker>(bytes));buffers[i].resize(bytes);}
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
  void Pair(uint32_t a,uint32_t b) {
    Connection c;c.ownerNodeId=a;c.node1=a;c.node2=b;c.port1=c.port2=0;c.tpn1=Tpn(a,b);c.tpn2=Tpn(b,a);c.priority=7;c.metrics=0;
    Ctrl(a)->GetTpConnManager()->AddUnilateralConnection(c,a);Ctrl(b)->GetTpConnManager()->AddUnilateralConnection(c,b);
    for(auto [src,dst]:{std::pair{a,b},std::pair{b,a}}) {
      Ctrl(src)->GetTransportChannelManager()->CreateTp(src,dst,0,0,7,Tpn(src,dst),Tpn(dst,src),UbCongestionControl::Create(UB_DEVICE));
      Ctrl(src)->GetTransportChannelManager()->GetTp(Tpn(src,dst))->TraceConnectWithoutContext("WqeSegmentSendsNotify",Callback<void,uint32_t,uint32_t,uint32_t>([this,src](uint32_t,uint32_t task,uint32_t ssn){
        Require(task<ready.size(),"unknown task admission");uint32_t stage=task/assignments.size(),aid=task%assignments.size();uint64_t off=uint64_t(ssn)*segment;Require(off<bytes,"invalid TA offset");
        auto a=assignments[aid];uint32_t requestSource=stage?a.target:a.source;
        Event(src==requestSource?"ta_admitted":"ta_response_admitted",stage,aid,src,off,src==requestSource?std::min<uint64_t>(segment,bytes-off):0);
      }));
    }
  }
  void Topology(const std::string& out) {
    GlobalValue::Bind("UB_CC_ENABLED",BooleanValue(false));UbUtils::Get();
    for(auto key:{"UB_TRACE_ENABLE","UB_PACKET_TRACE_ENABLE","UB_PORT_TRACE_ENABLE","UB_RECORD_PKT_TRACE"}) GlobalValue::Bind(key,BooleanValue(true));
    std::filesystem::create_directories(out+"/native/runlog");UbUtils::SetTracePathForTest(out+"/native");traceOn=true;
    nodes.resize(n+1);for(uint32_t i=0;i<n;++i) Init(i,true,1);Init(n,false,n);
    for(uint32_t i=0;i<n;++i) {
      auto link=CreateObject<UbLink>();link->SetAttribute("Delay",TimeValue(NanoSeconds(linkDelayNs)));
      DynamicCast<UbPort>(nodes[i]->GetDevice(0))->Attach(link);DynamicCast<UbPort>(nodes[n]->GetDevice(i))->Attach(link);
      Route(n,i,i);for(uint32_t j=0;j<n;++j) if(j!=i) Route(i,j,0);
    }
    std::set<std::pair<uint32_t,uint32_t>> pairs;
    for(auto a:assignments) if(a.source!=a.target) pairs.insert(std::minmax(a.source,a.target));
    for(auto [a,b]:pairs) Pair(a,b);
    for(uint32_t stage=0;stage<2;++stage) for(uint32_t aid=0;aid<assignments.size();++aid) {
      auto a=assignments[aid];if(a.source==a.target)continue;++remoteCount;
      uint32_t src=stage?a.target:a.source,dst=stage?a.source:a.target,task=stage*assignments.size()+aid;
      auto fn=Ctrl(src)->GetUbFunction();fn->CreateJetty(src,dst,task);
      Require(Ctrl(src)->GetUbTransaction()->JettyBindTp(src,dst,task,false,{Tpn(src,dst)}),"bind failed");
      auto jetty=fn->GetJetty(task);jetty->SetTaSegmentBytes(segment);
      jetty->SetClientCallback(Callback<void,uint32_t,uint32_t>([this,stage,aid,src](uint32_t,uint32_t){++senderCount;Event("sender_complete",stage,aid,src);}));
    }
    for(uint32_t node=0;node<n;++node) Require(Ctrl(node)->GetUbTransaction()->SetTargetExecutor(UbTargetExecutor([this,node](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){
      uint32_t task=req->GetTaskId();Require(task<ready.size(),"unknown target task");uint32_t stage=task/assignments.size(),aid=task%assignments.size();auto a=assignments[aid];
      Require(req->GetSrc()==(stage?a.target:a.source)&&node==(stage?a.source:a.target)&&req->GetDest()==node&&req->GetType()==UbTransactionOpcode::WRITE&&req->HasTransactionResolved(),"target identity mismatch");
      uint64_t off=uint64_t(req->GetTaSsn())*segment,len=req->GetLogicalBytes();
      Require(off<bytes&&len==std::min<uint64_t>(segment,bytes-off)&&req->GetPayloadBytes()==len&&req->HasExplicitPayload()&&req->GetExplicitPayload()->GetSize()==len,"invalid TA bytes");
      Event("target_received",stage,aid,node,off,len);std::vector<uint8_t> data(len);req->GetExplicitPayload()->CopyData(data.data(),len);
      Validate(stage,aid,off,data);Event("payload_verified",stage,aid,node,off,len);done(UbWorkExecutionResult{});Event("target_complete",stage,aid,node,off,len);
      if(trackers[task]->Notify(req->GetTaSsn(),off,len)) Ready(stage,aid);
    })),"executor failed");
    UbUtils::Get()->TopoTraceConnect();for(auto [a,b]:pairs) {UbUtils::Get()->SingleTpTraceConnect(a,Tpn(a,b));UbUtils::Get()->SingleTpTraceConnect(b,Tpn(b,a));}
  }
  void Validate(uint32_t stage,uint32_t aid,uint64_t off,const std::vector<uint8_t>& data) {
    auto task=stage*assignments.size()+aid;for(size_t i=0;i<data.size();++i) {Require(data[i]==ExpectedByte(stage,aid,off+i),"payload mismatch");buffers[task][off+i]=data[i];}
  }
  void Send(uint32_t stage,uint32_t aid) {
    auto a=assignments[aid];uint32_t src=stage?a.target:a.source,dst=stage?a.source:a.target;
    Require(!stage||finished[src],"combine before compute");Event("send",stage,aid,src,0,bytes);
    std::vector<uint8_t> data(bytes);
    if(!stage) for(uint32_t i=0;i<bytes;++i)data[i]=InputByte(aid,i);
    else for(uint32_t i=0;i<bytes;++i)data[i]=ResultByte(aid,buffers[aid][i]);
    if(src==dst) {
      Simulator::ScheduleNow([this,stage,aid,src,data]{Validate(stage,aid,0,data);Event("local_verified",stage,aid,src,0,bytes);Ready(stage,aid);});return;
    }
    auto fn=Ctrl(src)->GetUbFunction();auto task=stage*assignments.size()+aid;
    auto wqe=fn->CreateWqe(src,dst,bytes,task,UbTransactionOpcode::WRITE);wqe->SetExplicitPayload(Create<Packet>(data.data(),data.size()));
    Require(fn->SubmitWqe(wqe,task).status==UbWqeSubmissionStatus::ACCEPTED,"WQE rejected");
  }
  uint64_t Duration(uint32_t count) const {
    uint64_t flops=uint64_t(count)*4*dim*ff,den=uint64_t(peak)*util;
    __uint128_t num=__uint128_t(flops)*1000000;
    auto duration=num/den+(num%den!=0)+uint64_t(setup)*1000;
    Require(duration<UINT64_C(1000000000000000),"compute duration too large");return uint64_t(duration);
  }
  void Compute(uint32_t node) {
    Require(!started[node]&&arrived[node]==expected[node],"compute dependency violation");started[node]=true;
    if(!expected[node]) {finished[node]=true;Event("compute_idle",-1,-1,node);return;}
    Event("compute_start",-1,-1,node,0,expected[node]);std::map<uint32_t,uint32_t> loads;
    for(auto a:assignments) {if(a.target==node)++loads[a.expert];}
    uint64_t elapsed=0;
    for(auto [expert,count]:loads) {
      uint64_t duration=Duration(count);
      Simulator::Schedule(PicoSeconds(elapsed),[this,node,expert,count]{Event("expert_start",-1,expert,node,0,count);});elapsed+=duration;
      Simulator::Schedule(PicoSeconds(elapsed),[this,node,expert,count]{Event("expert_end",-1,expert,node,0,count);});
    }
    Simulator::Schedule(PicoSeconds(elapsed),[this,node]{finished[node]=true;Event("compute_end",-1,-1,node,0,expected[node]);for(uint32_t aid=0;aid<assignments.size();++aid)if(assignments[aid].target==node)Send(1,aid);});
  }
  void Ready(uint32_t stage,uint32_t aid) {
    auto task=stage*assignments.size()+aid;Require(!ready[task],"duplicate ready");ready[task]=true;auto a=assignments[aid];
    Event("data_ready",stage,aid,stage?a.source:a.target,0,bytes);
    if(!stage) {if(++arrived[a.target]==expected[a.target])Compute(a.target);}
    else {Require(++contributions[a.token]<=k,"duplicate contribution");if(contributions[a.token]==k) {Event("token_complete",-1,a.token,a.source);if(++receivedTokens==t)Event("layer_end");}}
  }
  void Run(const std::string& input,const std::string& out) {
    Read(input);std::filesystem::create_directories(out);log.open(out+"/events.csv");Require(bool(log),"cannot write events");log<<"time_ps,event,stage,id,node,offset,bytes\n";
    Topology(out);Simulator::Schedule(PicoSeconds(startPs),[this]{Event("layer_start");for(uint32_t node=0;node<n;++node)if(!expected[node])Compute(node);if(!t)Event("layer_end");for(uint32_t aid=0;aid<assignments.size();++aid)Send(0,aid);});
    Simulator::Stop(Seconds(10));Simulator::Run();Require(receivedTokens==t&&senderCount==remoteCount,"incomplete layer or senders");for(bool r:ready)Require(r,"missing assignment");
    std::cout<<"PASS layer: N="<<n<<" tokens="<<t<<" assignments="<<assignments.size()<<" remote_WQEs="<<remoteCount<<"\n";
    log.close();UbUtils::Get()->Destroy();traceOn=false;Simulator::Destroy();
  }
};
int main(int argc,char** argv) {
  Time::SetResolution(Time::PS);
  Layer layer;std::string input,out;CommandLine cmd;cmd.AddValue("input","validated synthetic input.txt",input);cmd.AddValue("out","output directory",out);cmd.Parse(argc,argv);
  try {Require(!input.empty()&&!out.empty(),"input/out required");layer.Run(input,out);}
  catch(const std::exception& ex) {if(layer.log) {layer.Event("error");layer.log.flush();}if(layer.traceOn)UbUtils::Get()->Destroy();std::cerr<<"ERROR: "<<ex.what()<<'\n';return 2;}return 0;
}
