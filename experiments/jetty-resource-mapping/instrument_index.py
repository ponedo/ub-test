#!/usr/bin/env python3
"""Generate (never apply) diagnostic instrumentation patches for ns3-ub d6aa9e2.
Usage: python native_timing_patch.py --native CLONE --output native.patch \
  [--app multi-npu-relay.cc --app-output app.patch]
Apply native.patch in a separate native checkout and app.patch in the application
repo. Rebuild all affected objects. Enable with NATIVE_CPU_PROFILE=1; optionally
set NATIVE_CPU_PROFILE_OUT=/absolute/profile.tsv (otherwise stderr). Set
NATIVE_CPU_PROFILE_DETAIL=1 for additional per-packet and native trace scopes.
Data/stack/report have one exported out-of-line owner in ub-function.cc, shared
by executable and native DSO. Existing
protocol logs are untouched. Run single-threaded; counters are intentionally
non-atomic. Normal process exit emits aggregate data; abort/_exit does not.
"""
import argparse
import difflib
import re
from pathlib import Path
import subprocess

TIMERS = ['CreateJettyBound','CreateJettyUnbound','CreateObjectJetty','JettyInit','RegisterJetty','ResolveWqeLifecycleLocalId','SubmitWqe','SubmitCtpWqe','RegisterWqe','AckResize','AckReset','AppRun','AppRead','AppTopology','AppWriteArtifacts','AppWritePayloads','AppSimulatorRun','AppSimulatorDestroy','AppValidate','AppTargetExecutor','AppTargetCompletion','AppEvent','AppSend','AppUbUtilsDestroy','AppLogClose','AppLayerDestroy','TransactionInboundTaUnit','TransactionSegmentComplete','GetJettiesUsingTpn','TransactionExecuteInbound','NativeAppendTrace','NativeCommitTrace','NativeFlushTrace','PortDispatchReceive','TransportParseData','TransportHandleAck','AppPair','AppInit']
COUNTERS = ['LifecycleCandidates','JettyRecordsScanned','WqeEntriesCompared','AckResizeSlots','AckResizeBytes','AckCapacityGrowthRequests','AckResetSlots','AckResetBytes','TpnLookupJettyRecordsScanned','TpnLookupTransportEntriesCompared','TpnLookupLiveTransportVectorSlots','TpnLookupMatchedJetties']
HEADER = r'''
// BEGIN opt-in native CPU diagnostics. Single-threaded simulator only.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
namespace ns3 { namespace ubcpu {
enum TimerId { @TIMERS@, TimerCount };
enum CounterId { @COUNTERS@, CounterCount };
inline bool Enabled() {
    static const bool enabled = [] { const char* p = std::getenv("NATIVE_CPU_PROFILE");
        return p && *p && std::strcmp(p, "0") != 0; }();
    return enabled;
}
inline bool Detailed() {
    static const bool enabled = [] { const char* p = std::getenv("NATIVE_CPU_PROFILE_DETAIL");
        return p && *p && std::strcmp(p, "0") != 0; }(); return enabled;
}
struct Stat { uint64_t calls=0, wall=0, cpu=0, selfWall=0, selfCpu=0; };
struct State { Stat timers[TimerCount]; uint64_t counters[CounterCount]{}; uint64_t clockErrors=0; };
#if defined(__GNUC__)
#define NS3_UBCPU_EXPORT __attribute__((visibility("default")))
#else
#define NS3_UBCPU_EXPORT
#endif
NS3_UBCPU_EXPORT void Report();
NS3_UBCPU_EXPORT State& Data();
inline uint64_t Wall() { return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count(); }
inline uint64_t Cpu() { struct timespec ts{};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts) != 0) { ++Data().clockErrors; return 0; }
    return uint64_t(ts.tv_sec)*1000000000ULL + uint64_t(ts.tv_nsec); }
inline void Count(CounterId id, uint64_t n=1) { if (Enabled()) Data().counters[id]+=n; }
struct Scope;
NS3_UBCPU_EXPORT Scope*& Top();
struct Scope {
    TimerId id; bool active; Scope* parent=nullptr;
    uint64_t wall=0,cpu=0,childWall=0,childCpu=0;
    explicit Scope(TimerId i, bool detailed=false): id(i), active(Enabled() && (!detailed || Detailed())) {
        if (!active) return;
        ++Data().timers[id].calls; parent=Top(); Top()=this; wall=Wall(); cpu=Cpu();
    }
    ~Scope() {
        if (!active) return;
        const auto endCpu=Cpu(), endWall=Wall();
        const auto w=endWall-wall, c=endCpu>=cpu?endCpu-cpu:0;
        auto& s=Data().timers[id]; s.wall+=w; s.cpu+=c;
        s.selfWall+=w>=childWall?w-childWall:0; s.selfCpu+=c>=childCpu?c-childCpu:0;
        Top()=parent; if(parent){parent->childWall+=w; parent->childCpu+=c;}
    }
    Scope(const Scope&)=delete; Scope& operator=(const Scope&)=delete;
};
}} // ns3::ubcpu
// END opt-in native CPU diagnostics.
'''.replace('@TIMERS@', ','.join(TIMERS)).replace('@COUNTERS@', ','.join(COUNTERS)).replace('@TIMER_NAMES@', ','.join('"'+s+'"' for s in TIMERS)).replace('@COUNTER_NAMES@', ','.join('"'+s+'"' for s in COUNTERS))

CPP = r'''
namespace ns3 { namespace ubcpu {
State& Data() { static State* p = [] { auto* s = new State;
    std::atexit(Report); return s; }(); return *p; }
Scope*& Top() { static thread_local Scope* p=nullptr; return p; }
void Report() {
    if (!Enabled()) return;
    const char* path=std::getenv("NATIVE_CPU_PROFILE_OUT");
    FILE* f=path&&*path?std::fopen(path,"w"):stderr;
    if(!f){ std::fprintf(stderr,"native_cpu_profile: cannot open output; using stderr\n"); f=stderr; }
    const char* timers[]={@TIMER_NAMES@}; const char* counters[]={@COUNTER_NAMES@};
    std::fprintf(f,"kind\tname\tcalls_or_count\tinclusive_wall_ns\tinclusive_thread_cpu_ns\texclusive_wall_ns\texclusive_thread_cpu_ns\n");
    for(unsigned i=0;i<TimerCount;++i){const auto& s=Data().timers[i];
        std::fprintf(f,"timer\t%s\t%llu\t%llu\t%llu\t%llu\t%llu\n",timers[i],
        (unsigned long long)s.calls,(unsigned long long)s.wall,(unsigned long long)s.cpu,
        (unsigned long long)s.selfWall,(unsigned long long)s.selfCpu);}
    for(unsigned i=0;i<CounterCount;++i) std::fprintf(f,"counter\t%s\t%llu\t0\t0\t0\t0\n",
        counters[i],(unsigned long long)Data().counters[i]);
    std::fprintf(f,"counter\tClockErrors\t%llu\t0\t0\t0\t0\n",(unsigned long long)Data().clockErrors);
    if(f!=stderr) std::fclose(f); else std::fflush(f);
}
}} // ns3::ubcpu
'''.replace('@TIMER_NAMES@', ','.join('"'+s+'"' for s in TIMERS)).replace('@COUNTER_NAMES@', ','.join('"'+s+'"' for s in COUNTERS))

def replace(text, old, new, count=1):
    actual=text.count(old)
    if actual != count: raise RuntimeError(f'Expected {count} occurrences, got {actual}: {old[:120]!r}')
    return text.replace(old,new)

def scope(text, signature, name):
    return replace(text, signature, signature+'\n    ns3::ubcpu::Scope cpuScope(ns3::ubcpu::'+name+');')

def scope_function(text, token, name, detailed=False):
    matches=list(re.finditer(re.escape(token)+r'\([^;{}]*\)[^;{}]*\{',text))
    if len(matches)!=1: raise RuntimeError(f'Expected one function {token}, found {len(matches)}')
    end=matches[0].end()
    return text[:end]+'\n    ns3::ubcpu::Scope cpuScope(ns3::ubcpu::'+name+(', true' if detailed else '')+');'+text[end:]

def diff(old,new,path):
    return ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))

def native_patch(root):
    head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    actual=subprocess.check_output(['git','-C',str(root),'diff','d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b','--binary'])
    expected=(Path(__file__).resolve().parent/'tpn-jetty-index.patch').read_bytes()
    if actual != expected:
        raise RuntimeError('Native source must equal baseline plus the exact reviewed index patch')
    p='src/unified-bus/model/ub-sliding-bitmap-window.h'; old=(root/p).read_text(); new=old
    new=replace(new,'#include <vector>','#include <vector>\n'+HEADER)
    new=scope(new,'    void Resize(uint32_t windowSize)\n    {','AckResize')
    new=replace(new,'        m_windowSize = windowSize;', '''        ns3::ubcpu::Count(ns3::ubcpu::AckResizeSlots, windowSize);
        ns3::ubcpu::Count(ns3::ubcpu::AckResizeBytes, uint64_t(windowSize)*sizeof(uint64_t));
        if (windowSize > m_slots.capacity()) ns3::ubcpu::Count(ns3::ubcpu::AckCapacityGrowthRequests);
        m_windowSize = windowSize;''')
    new=scope(new,'    void Reset(uint64_t baseSequence = 0)\n    {','AckReset')
    new=replace(new,'        m_baseSequence = baseSequence;', '''        ns3::ubcpu::Count(ns3::ubcpu::AckResetSlots, m_slots.size());
        ns3::ubcpu::Count(ns3::ubcpu::AckResetBytes, uint64_t(m_slots.size())*sizeof(uint64_t));
        m_baseSequence = baseSequence;''')
    result=diff(old,new,p)
    p='src/unified-bus/model/protocol/ub-function.cc'; old=(root/p).read_text();new=old
    for sig,name in [
        ('UbFunction::CreateJetty(uint32_t src, uint32_t dest, uint32_t jettyNum, UbJettyLifetime lifetime)','CreateJettyBound'),
        ('UbFunction::CreateJetty(uint32_t src, uint32_t jettyNum, UbJettyLifetime lifetime)','CreateJettyUnbound'),
        ('UbJetty::Init()','JettyInit'),
        ('UbJettyManager::RegisterJetty(Ptr<UbJetty> jetty, UbJettyLifetime lifetime)','RegisterJetty'),
        ('UbFunction::SubmitWqe(Ptr<UbWqe> wqe, uint32_t jettyNum)','SubmitWqe'),
        ('UbJettyManager::ResolveWqeLifecycleLocalId(uint32_t jettyNum, uint32_t wqeId) const','ResolveWqeLifecycleLocalId')]:
        new=scope(new,sig+'\n{',name)
    # Capture all allocation/attribute construction, including member initialization.
    new=replace(new,'    Ptr<UbJetty> jetty = CreateObject<UbJetty>();', '''    Ptr<UbJetty> jetty = [] {
        ns3::ubcpu::Scope allocationScope(ns3::ubcpu::CreateObjectJetty);
        return CreateObject<UbJetty>();
    }();''',2)
    # Exact scan counts retain the existing loop, predicate and short circuiting.
    new=replace(new,'    const auto isInUse = [this](uint64_t localId) {','''    const auto isInUse = [this](uint64_t localId) {
        ns3::ubcpu::Count(ns3::ubcpu::LifecycleCandidates);''')
    new=replace(new,'            (void)candidateJettyNum;', '''            ns3::ubcpu::Count(ns3::ubcpu::JettyRecordsScanned);
            (void)candidateJettyNum;''')
    new=replace(new,'                                return entry.second.localId == localId;', '''                                ns3::ubcpu::Count(ns3::ubcpu::WqeEntriesCompared);
                                return entry.second.localId == localId;''')
    # Multiline signatures are matched up to the opening brace.
    for name,token in [('RegisterWqe','UbJettyManager::RegisterWqe('),('SubmitCtpWqe','UbFunction::SubmitCtpWqe(')]:
        start=new.index(token); end=new.index('\n{',start)+2
        new=new[:end]+'\n    ns3::ubcpu::Scope cpuScope(ns3::ubcpu::'+name+');'+new[end:]
    new += CPP
    result += diff(old,new,p)
    p='src/unified-bus/model/protocol/ub-transaction.cc'; old=(root/p).read_text(); new=old
    for signature,name in [
        ('UbTransaction::HandleInboundTaUnit(uint32_t localTpn, Ptr<UbWqeSegment> segment)','TransactionInboundTaUnit'),
        ('UbTransaction::ProcessWqeSegmentComplete(Ptr<UbWqeSegment> wqeSegment)','TransactionSegmentComplete')]:
        new=scope(new,signature+'\n{',name)
    new=scope_function(new,'UbTransaction::GetJettiesUsingTpn','GetJettiesUsingTpn')
    new=scope_function(new,'UbTransaction::ExecuteInboundTransaction','TransactionExecuteInbound', True)
    new=replace(new,'    for (uint32_t jettyNum : candidates)\n    {','''    for (uint32_t jettyNum : candidates)
    {
        ns3::ubcpu::Count(ns3::ubcpu::TpnLookupJettyRecordsScanned);''')
    new=replace(new,'        const bool jettyUsesTpn =','''        ns3::ubcpu::Count(ns3::ubcpu::TpnLookupLiveTransportVectorSlots, transports.size());
        const bool jettyUsesTpn =''')
    new=replace(new,'                            return transport != nullptr && transport->GetTpn() == tpn;','''                            ns3::ubcpu::Count(ns3::ubcpu::TpnLookupTransportEntriesCompared);
                            return transport != nullptr && transport->GetTpn() == tpn;''')
    new=replace(new,'            jetties.push_back(jetty);','''            ns3::ubcpu::Count(ns3::ubcpu::TpnLookupMatchedJetties);
            jetties.push_back(jetty);''')
    result+=diff(old,new,p)
    for p, functions in [
        ('src/unified-bus/model/ub-utils.cc', [('UbUtils::AppendTraceLine','NativeAppendTrace'),('UbUtils::CommitTraceChunk','NativeCommitTrace'),('UbUtils::FlushTraceFile','NativeFlushTrace')]),
        ('src/unified-bus/model/ub-port.cc', [('UbPort::DispatchReceive','PortDispatchReceive')]),
        ('src/unified-bus/model/protocol/ub-transport.cc', [('UbTransportChannel::ParseReceivedDataPacket','TransportParseData'),('UbTransportChannel::HandleReceivedAckOrSack','TransportHandleAck')])]:
        old=(root/p).read_text();new='#include "ns3/ub-sliding-bitmap-window.h"\n'+old
        for token,name in functions: new=scope_function(new,token,name, True)
        result+=diff(old,new,p)
    return result

def app_patch(path):
    old=path.read_text();new='#include "ns3/ub-sliding-bitmap-window.h"\n#include <optional>\n'+old
    for signature,name in [
        ('    void Run(const std::string& input,const std::string& out){','AppRun'),
        ('    void Read(const std::string& path){','AppRead'),
        ('    void Topology(const std::string& out){','AppTopology'),
        ('    void WriteArtifacts(const std::string& out){','AppWriteArtifacts'),
        ('    void WritePayloads(const std::string& out){','AppWritePayloads'),
        ('    void Validate(uint32_t task,uint64_t off,const std::vector<uint8_t>& data){','AppValidate'),
        ('    void Send(uint32_t task){','AppSend'),
        ('    void Event(std::string event,int stage=-1,int id=-1,int node=-1,uint64_t off=0,uint64_t len=0,int task=-1){','AppEvent'),
        ('[this,node](Ptr<const UbWqeSegment> req,const UbTransactionRule&,UbTargetCompletion done){','AppTargetExecutor'),
        ('auto complete=[this,task,node,off,len,ssn=req->GetTaSsn(),done]{','AppTargetCompletion')]: new=scope(new,signature,name)
    for token,name in [('Simulator::Run();','AppSimulatorRun'),('Simulator::Destroy();','AppSimulatorDestroy'),('log.close();','AppLogClose')]:
        new=replace(new,token,'{ns3::ubcpu::Scope stageScope(ns3::ubcpu::'+name+');'+token+'}')
    new=scope_function(new,'void Pair','AppPair')
    new=scope_function(new,'void Init','AppInit')
    # Both normal and error-path native trace flushes; Event covers TE's actual output.
    new=replace(new,'UbUtils::Get()->Destroy();','{ns3::ubcpu::Scope cleanupScope(ns3::ubcpu::AppUbUtilsDestroy);UbUtils::Get()->Destroy();}',2)
    # First member is destroyed last. Emplace only on entry to Layer destruction;
    # its Scope closes after all original members, including vectors and streams.
    new=replace(new,'class Layer {\npublic:','''class Layer {
public:
    struct CpuCleanupTail { std::optional<ns3::ubcpu::Scope> scope; } cpuCleanupTail;
    ~Layer(){cpuCleanupTail.scope.emplace(ns3::ubcpu::AppLayerDestroy);}
''')
    return diff(old,new,'experiments/multi-npu-relay/multi-npu-relay.cc')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--app',type=Path)
    parser.add_argument('--app-output',type=Path)
    args=parser.parse_args()
    if bool(args.app)!=bool(args.app_output):parser.error('--app and --app-output must be supplied together')
    native=native_patch(args.native)
    app=app_patch(args.app) if args.app else None
    args.output.write_text(native)
    if app is not None:args.app_output.write_text(app)
    print(f'Generated {args.output}; native source unchanged')
    if app is not None:print(f'Generated {args.app_output}; app source unchanged')
if __name__=='__main__': main()
