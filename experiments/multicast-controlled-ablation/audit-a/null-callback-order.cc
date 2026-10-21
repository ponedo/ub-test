// Private bounded audit, not an application/runtime patch.
// Links the unchanged accepted diagnostic native library and uses accepted PairV2Proxy.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/unified-bus-module.h"
#include "pair-multicast-v2.h"
#include <iostream>
#include <string>
#include <vector>
using namespace ns3;

class AuditAllocator : public UbRoundRobinAllocator {
public:
    bool suppress = false;
    std::vector<Ptr<pairv2::Proxy>> queues;
    std::vector<std::string> commits;
    uint32_t callbacks = 0;
    uint32_t suppressed = 0;
    void Start(Ptr<UbPort> outPort) {
        if (!suppress) {
            UbSwitchAllocator::TriggerAllocator(outPort);
            return;
        }
        // TriggerAllocator 360--385, same native single selection; only delta is
        // immediate release when the actual selection returns null.
        auto id = outPort->GetIfIndex();
        if (m_disposed || id >= m_running.size() || !GetEgressStatus(id)) return;
        if (m_running[id]) { m_runAgain[id] = true; return; }
        m_running[id] = true;
        m_runAgain[id] = false;
        auto chosen = SelectNextIngressQueue(outPort);
        SetActiveIngressQueue(chosen);
        if (m_disposed) { m_running[id] = false; return; }
        if (chosen == nullptr) {
            ++suppressed;
            m_running[id] = false;
            return;
        }
        ScheduleAllocation(outPort);
    }
    void AllocateNextPacket(Ptr<UbPort> port) override {
        ++callbacks;
        // Passive queue-size snapshots, not predicate probes.
        std::vector<size_t> before;
        for (auto q: queues) before.push_back(q->tp->m_ackQ.size());
        UbRoundRobinAllocator::AllocateNextPacket(port);
        for (size_t i=0;i<queues.size();++i) {
            if (queues[i]->tp->m_ackQ.size() < before[i]) {
                commits.push_back(std::string(i == 0 ? "A" : "B") + "@" +
                                  std::to_string(Simulator::Now().GetPicoSeconds()) + "ps");
            }
        }
    }
};
int Consume(Ptr<Packet>, uint32_t, uint32_t, Ptr<UbPort>) { return 0; }
Ptr<Packet> MakeQueuedAck() {
    // Packet content is a fixture: only the native ACK queue and scheduler are
    // under test. A real DL header preserves native CBFC VL accounting.
    auto p = Create<Packet>(76);
    UbDatalinkPacketHeader dl;
    dl.SetPacketVL(7); dl.SetConfig(3);
    p->AddHeader(dl);
    return p;
}
int main(int argc, char** argv) {
    Time::SetResolution(Time::PS);
    bool suppress = argc > 1 && std::string(argv[1]) == "suppress";
    Config::SetDefault("ns3::UbSwitch::FlowControl", EnumValue(FcType::CBFC));
    Config::SetDefault("ns3::UbSwitchAllocator::AllocationTime", TimeValue(NanoSeconds(5)));
    Config::SetDefault("ns3::UbSwitchAllocator::EnableDirectAllocationCompletion", BooleanValue(true));
    auto node = CreateObject<Node>();
    auto sw = CreateObject<UbSwitch>();
    node->AggregateObject(sw);
    auto port = CreateObject<UbPort>();
    port->SetDataRate(DataRate(uint64_t(3136) * 1000000000ULL));
    node->AddDevice(port);
    sw->Init();
    port->SetFaultCallBack(MakeCallback(&Consume));
    auto allocator = CreateObject<AuditAllocator>();
    allocator->SetNodeId(node->GetId());
    allocator->suppress = suppress;
    allocator->Init();
    pairv2::Manager manager;
    for (uint32_t i=0;i<2;++i) {
        auto q = CreateObject<pairv2::Proxy>();
        q->tp = CreateObject<UbTransportChannel>();
        q->manager = &manager;
        q->source = node->GetId(); q->target = i+1;
        q->SetInPortId(0); q->SetOutPortId(0); q->SetIngressPriority(7);
        allocator->RegisterUbIngressQueue(q,0,7);
        allocator->queues.push_back(q);
    }
    // Node 0 / port 0 starts at RR slot 0. TP slots are A=1 and B=2.
    // Both queues initially empty. B arrives first; A arrives second, inside
    // the original null grant's 5 ns coalescing window.
    allocator->Start(port);
    Simulator::Schedule(NanoSeconds(1), [allocator,port]{
        allocator->queues[1]->tp->EnqueueAckForTest(MakeQueuedAck());
        allocator->queues[1]->Refresh(); allocator->Start(port);
    });
    Simulator::Schedule(NanoSeconds(2), [allocator,port]{
        allocator->queues[0]->tp->EnqueueAckForTest(MakeQueuedAck());
        allocator->queues[0]->Refresh(); allocator->Start(port);
    });
    // A later ordinary wake drains the remaining queue in either variant.
    Simulator::Schedule(NanoSeconds(20), [allocator,port]{allocator->Start(port);});
    Simulator::Stop(NanoSeconds(30));
    Simulator::Run();
    std::cout << (suppress ? "suppress" : "native") << " fc=CBFC link_gbps=3136 allocation_ps=5000 callbacks="
              << allocator->callbacks << " suppressed=" << allocator->suppressed << " commits=";
    for (size_t i=0;i<allocator->commits.size();++i) std::cout << (i ? "," : "") << allocator->commits[i];
    std::cout << "\n";
    bool ok = allocator->commits.size()==2 && allocator->commits[0][0] == (suppress?'B':'A');
    allocator->Dispose();
    Simulator::Destroy();
    return ok ? 0 : 2;
}
