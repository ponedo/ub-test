// SPDX-License-Identifier: GPL-2.0-only
// Diagnostic-only, single-threaded application instrumentation. No simulated events.
#pragma once
#include <array>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <time.h>

namespace qprof {
enum class Phase : unsigned {
    Program, Read, ReadEdges, ReadTransfers, ReadDependencies, ReadWeights,
    InitAudit, Topology, SimulatorRun, Audit, AuditGroupScan, AuditWeightScan,
    AuditWeightsEndScan, FinalAudit, Send, Validate, Ready, WriteSummary,
    WritePayloads, UbDestroy, SimulatorDestroy, LayerDestroy, Count
};
inline constexpr const char* phaseNames[] = {
    "program", "Read", "Read.edges", "Read.transfers", "Read.dependencies", "Read.replica_buffers",
    "InitAudit", "Topology", "Simulator::Run", "Audit", "Audit.group_scan", "Audit.weight_scan",
    "Audit.weights_end_scan", "FinalAudit", "Send", "Validate", "Ready", "WriteSummary",
    "WritePayloads", "UbUtils::Destroy", "Simulator::Destroy", "Layer::~Layer"
};
enum class Counter : unsigned {
    DependencyCandidates, DependencyEdges, DependencyReplicaTasks,
    AuditGroupCandidates, AuditGroupMatches, AuditWeightCandidates, AuditWeightMatches,
    AuditWeightsEndCandidates, AuditGroupEvents, AuditWeightEvents,
    ReadyDependencyPredicates, SendDependencyChecks, AuditSendDependencyChecks,
    TransferPayloadAllocated, ReplicaPayloadAllocated, TransfersCreated,
    SendPayloadBytes, ValidatePayloadBytes, FinalTaskPayloadBytes, FinalRelayPayloadBytes,
    FinalReplicaPayloadBytes, AuditEvents, RemoteWqesSubmitted, Count
};
inline constexpr const char* counterNames[] = {
    "read_dependency_candidates", "read_dependency_edges", "read_dependency_replica_tasks",
    "audit_group_scan_candidates", "audit_group_scan_matches", "audit_weight_scan_candidates", "audit_weight_scan_matches",
    "audit_weights_end_physical_candidates", "audit_group_events", "audit_weight_events",
    "ready_dependency_predicates", "send_dependency_checks", "audit_send_dependency_checks",
    "transfer_payload_bytes_allocated", "replica_payload_bytes_allocated", "transfers_created",
    "send_payload_bytes_generated", "validate_payload_bytes_completed", "final_task_payload_bytes_checked", "final_relay_payload_bytes_checked",
    "final_replica_payload_bytes_checked", "audit_events", "remote_wqes_submitted"
};
constexpr unsigned phaseCount = static_cast<unsigned>(Phase::Count);
constexpr unsigned counterCount = static_cast<unsigned>(Counter::Count);
static_assert(sizeof(phaseNames)/sizeof(*phaseNames)==phaseCount);
static_assert(sizeof(counterNames)/sizeof(*counterNames)==counterCount);
struct Stat { uint64_t calls=0, completed=0, inclusive=0, self=0; };
struct Frame { Phase phase{}; uint64_t start=0, child=0; Frame* parent=nullptr; };
struct State {
    bool enabled=false, complete=false, failed=false, simulatorLive=false;
    uint64_t cpuOrigin=0, wallOrigin=0, nextCheckpoint=0, interval=1000000000ULL;
    uint64_t polls=0, snapshots=0, snapshotCpu=0, snapshotWall=0;
    uint64_t simulatorEvents=0, simulatedPs=0, assignments=0, tasks=0, nodes=0, physical=0;
    uint64_t remoteWqes=0, taCount=0, senderCompletions=0, completedTokens=0, pendingWeights=0;
    uint64_t txPackets=0, rxPackets=0, txBytes=0, rxBytes=0;
    void* observerContext=nullptr;
    void (*observer)(void*)=nullptr;
    Frame* top=nullptr;
    std::array<Stat,phaseCount> stats{};
    std::array<uint64_t,counterCount> counters{};
    std::string path, historyPath;
};
inline State state;
inline volatile std::sig_atomic_t stopSignal=0;
inline void SignalHandler(int signal) noexcept { stopSignal=signal; }
inline uint64_t CpuNow() noexcept { timespec t{}; clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t); return uint64_t(t.tv_sec)*1000000000ULL+uint64_t(t.tv_nsec); }
inline uint64_t WallNow() noexcept { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
inline void UpdateSimulator() {
    if(state.simulatorLive){state.simulatorEvents=ns3::Simulator::GetEventCount();state.simulatedPs=ns3::Simulator::Now().GetPicoSeconds();}
}
inline void SimulatorStarted(){if(state.enabled)state.simulatorLive=true;}
inline void FreezeSimulator(){if(state.enabled){UpdateSimulator();state.simulatorLive=false;}}
inline void SetModel(uint64_t assignments,uint64_t tasks,uint64_t nodes,uint64_t physical){
    if(state.enabled){state.assignments=assignments;state.tasks=tasks;state.nodes=nodes;state.physical=physical;}
}
template<class Range> inline uint64_t Sum(const Range& range){uint64_t total=0;for(auto value:range)total+=value;return total;}
template<class Range> inline void Progress(uint64_t assignments,uint64_t tasks,uint64_t wqes,uint64_t tas,uint64_t senders,uint64_t tokens,uint64_t weights,const Range& txPackets,const Range& rxPackets,const Range& txBytes,const Range& rxBytes){
    state.assignments=assignments;state.tasks=tasks;state.remoteWqes=wqes;state.taCount=tas;
    state.senderCompletions=senders;state.completedTokens=tokens;state.pendingWeights=weights;
    state.txPackets=Sum(txPackets);state.rxPackets=Sum(rxPackets);state.txBytes=Sum(txBytes);state.rxBytes=Sum(rxBytes);
}
inline void SetObserver(void* context,void(*observer)(void*)){if(state.enabled){state.observerContext=context;state.observer=observer;}}
inline void ClearObserver(){if(state.enabled&&state.observer){state.observer(state.observerContext);state.observer=nullptr;state.observerContext=nullptr;}}
inline void Snapshot(const char* reason,bool terminal=false){
    if(!state.enabled)return;
    const auto cpu=CpuNow(), wall=WallNow();
    UpdateSimulator();
    if(state.observer)state.observer(state.observerContext);
    auto observed=state.stats;
    std::array<uint64_t,phaseCount> active{};
    uint64_t activeChild=0;
    for(auto* f=state.top;f;f=f->parent){
        const auto elapsed=cpu-f->start;
        auto& stat=observed[static_cast<unsigned>(f->phase)];
        stat.inclusive+=elapsed;
        const auto excluded=f->child+activeChild;
        stat.self+=elapsed>=excluded?elapsed-excluded:0;
        ++active[static_cast<unsigned>(f->phase)];
        activeChild=elapsed;
    }
    std::ostringstream out;
    out<<"{\"schema\":1,\"reason\":\""<<reason<<"\",\"terminal\":"<<(terminal?"true":"false")
       <<",\"complete\":"<<(state.complete?"true":"false")<<",\"failed\":"<<(state.failed?"true":"false")
       <<",\"signal\":"<<stopSignal<<",\"wall_ns\":"<<wall-state.wallOrigin
       <<",\"process_cpu_ns\":"<<cpu-state.cpuOrigin
       <<",\"snapshot_overhead_cpu_ns_before_this_snapshot\":"<<state.snapshotCpu
       <<",\"snapshot_overhead_wall_ns_before_this_snapshot\":"<<state.snapshotWall
       <<",\"snapshot_index\":"<<++state.snapshots
       <<",\"active_phase\":\""<<(state.top?phaseNames[static_cast<unsigned>(state.top->phase)]:"none")
       <<"\",\"active_stack\":[";
    bool comma=false;
    for(auto* f=state.top;f;f=f->parent){if(comma)out<<',';comma=true;out<<'"'<<phaseNames[static_cast<unsigned>(f->phase)]<<'"';}
    out<<"],\"progress\":{\"remote_wqes_planned\":"<<state.remoteWqes<<",\"remote_wqes_submitted\":"<<state.counters[static_cast<unsigned>(Counter::RemoteWqesSubmitted)]
       <<",\"TA_count\":"<<state.taCount<<",\"sender_completions\":"<<state.senderCompletions<<",\"completed_tokens\":"<<state.completedTokens
       <<",\"pending_replica_weights\":"<<state.pendingWeights<<",\"packet_tx_total\":"<<state.txPackets<<",\"packet_rx_total\":"<<state.rxPackets
       <<",\"byte_tx_total\":"<<state.txBytes<<",\"byte_rx_total\":"<<state.rxBytes<<"},\"simulator_events\":"<<state.simulatorEvents<<",\"simulated_time_ps\":"<<state.simulatedPs
       <<",\"simulator_counter_live\":"<<(state.simulatorLive?"true":"false")
       <<",\"model\":{\"assignments\":"<<state.assignments<<",\"tasks\":"<<state.tasks<<",\"nodes\":"<<state.nodes<<",\"physical_experts\":"<<state.physical<<"},\"phases\":{";
    for(unsigned i=0;i<phaseCount;++i){const auto& s=observed[i];if(i)out<<',';out<<'"'<<phaseNames[i]<<"\":{\"calls\":"<<s.calls<<",\"completed_calls\":"<<s.completed<<",\"active_calls\":"<<active[i]<<",\"inclusive_cpu_ns\":"<<s.inclusive<<",\"self_cpu_ns\":"<<s.self<<'}';}
    out<<"},\"counters\":{";
    for(unsigned i=0;i<counterCount;++i){if(i)out<<',';out<<'"'<<counterNames[i]<<"\":"<<state.counters[i];}
    out<<"}}\n";
    const auto text=out.str(), temporary=state.path+".tmp";
    {std::ofstream file(temporary,std::ios::binary|std::ios::trunc);file<<text;file.close();
     if(file) {if(std::rename(temporary.c_str(),state.path.c_str())!=0)std::perror("qprof snapshot rename");}
     else std::fprintf(stderr,"qprof could not write snapshot: %s\n",temporary.c_str());}
    if(!state.historyPath.empty()){std::ofstream history(state.historyPath,std::ios::binary|std::ios::app);history<<text;}
    const auto endCpu=CpuNow(), endWall=WallNow();
    const auto overhead=endCpu-cpu;
    state.snapshotCpu+=overhead;state.snapshotWall+=endWall-wall;
    // Exclude snapshot serialization/I/O CPU from every currently active timer.
    for(auto* f=state.top;f;f=f->parent)f->start+=overhead;
    state.nextCheckpoint=endWall+state.interval;
}
inline void Checkpoint(bool force=false){
    if(!state.enabled)return;
    if(stopSignal){Snapshot("signal",true);std::_Exit(128+stopSignal);}
    if(!force&&((++state.polls&255)!=0))return;
    if(force||WallNow()>=state.nextCheckpoint)Snapshot(force?"phase_boundary":"periodic");
}
inline void Count(Counter counter,uint64_t amount=1){if(state.enabled)state.counters[static_cast<unsigned>(counter)]+=amount;}
inline void Candidate(Counter counter){
    if(state.enabled){auto& count=state.counters[static_cast<unsigned>(counter)];++count;if((count&4095)==0)Checkpoint();}
}
inline bool Coarse(Phase phase){
    switch(phase){
    case Phase::Read:case Phase::ReadEdges:case Phase::ReadTransfers:case Phase::ReadDependencies:case Phase::ReadWeights:
    case Phase::InitAudit:case Phase::Topology:case Phase::SimulatorRun:case Phase::FinalAudit:
    case Phase::WriteSummary:case Phase::WritePayloads:case Phase::UbDestroy:case Phase::SimulatorDestroy:case Phase::LayerDestroy:return true;
    default:return false;
    }
}
class Scope {
    Frame frame_{};
    bool active_=false;
public:
    Scope()=default;
    explicit Scope(Phase phase){Begin(phase);}
    Scope(const Scope&)=delete;Scope& operator=(const Scope&)=delete;
    void Begin(Phase phase){
        if(!state.enabled)return;
        frame_.phase=phase;frame_.start=CpuNow();frame_.child=0;frame_.parent=state.top;
        state.top=&frame_;active_=true;++state.stats[static_cast<unsigned>(phase)].calls;
        Checkpoint(Coarse(phase));
    }
    void End(){
        if(!active_)return;
        Checkpoint(Coarse(frame_.phase));
        const auto elapsed=CpuNow()-frame_.start;
        auto& stat=state.stats[static_cast<unsigned>(frame_.phase)];
        ++stat.completed;stat.inclusive+=elapsed;stat.self+=elapsed>=frame_.child?elapsed-frame_.child:0;
        state.top=frame_.parent;if(state.top)state.top->child+=elapsed;active_=false;
    }
    ~Scope(){End();}
};
// Declare first in Layer: it is destroyed last, after all original Layer members.
struct LayerLifetime {Scope scope;void Begin(){scope.Begin(Phase::LayerDestroy);}};
class Session {
    Scope program_;
    using Handler=void(*)(int);
    Handler old_=SIG_DFL;
public:
    Session(){
        const auto* enabled=std::getenv("QWEN_CPU_PROFILE");
        const auto* path=std::getenv("QWEN_CPU_PROFILE_OUT");
        if(enabled&&std::string(enabled)!="1")return;
        if(!path||!*path)path=std::getenv("QWEN_PROFILE_JSON");
        if(!path||!*path)return;
        state.enabled=true;state.path=path;
        state.historyPath=state.path+".jsonl";
        if(const auto* history=std::getenv("QWEN_PROFILE_HISTORY"))state.historyPath=history;
        if(const auto* interval=std::getenv("QWEN_PROFILE_CHECKPOINT_SECONDS")){
            char* end=nullptr;const double value=std::strtod(interval,&end);
            if(end!=interval&&*end=='\0'&&value>=0.05&&value<=3600)state.interval=uint64_t(value*1e9);
        }
        state.cpuOrigin=CpuNow();state.wallOrigin=WallNow();state.nextCheckpoint=state.wallOrigin+state.interval;
        old_=std::signal(SIGTERM,SignalHandler);program_.Begin(Phase::Program);Snapshot("start");
    }
    ~Session(){
        if(!state.enabled)return;
        program_.End();Snapshot(state.complete?"completed":state.failed?"failed":"exit",true);
        if(old_!=SIG_ERR)std::signal(SIGTERM,old_);
    }
};
inline void Complete(){if(state.enabled)state.complete=true;}
inline void Failed(){if(state.enabled)state.failed=true;}
} // namespace qprof
