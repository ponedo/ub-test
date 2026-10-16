// SPDX-License-Identifier: GPL-2.0-only
#include "ns3/test.h"

#include "ub-node-test-fixture.h"

#include "ns3/boolean.h"
#include "ns3/config.h"
#include "ns3/global-value.h"
#include "ns3/simulator.h"
#include "ns3/ub-congestion-control.h"
#include "ns3/ub-controller.h"
#include "ns3/ub-function.h"
#include "ns3/ub-link.h"
#include "ns3/ub-tp-connection-manager.h"
#include "ns3/ub-transaction-rules.h"
#include "ns3/ub-transaction.h"
#include "ns3/ub-transport-channel-manager.h"
#include "ns3/ub-transport.h"

namespace ns3
{
namespace
{
constexpr uint32_t kTargetExecutionSenderTpn = 101;
constexpr uint32_t kTargetExecutionReceiverTpn = 202;
constexpr uint32_t kTargetExecutionPriority = 7;
constexpr uint32_t kTargetExecutionJettyNum = 3;

/** One direct-link RTP pair that can carry a real inbound request to a target executor. */
struct TargetExecutionPair
{
    Ptr<Node> sender;
    Ptr<Node> receiver;
    Ptr<UbPort> senderPort;
    Ptr<UbPort> receiverPort;
    Ptr<UbTransportChannel> senderTp;
    Ptr<UbTransportChannel> receiverTp;
    Ptr<UbFunction> senderFunction;
    Ptr<UbTransaction> senderTransaction;
    Ptr<UbTransaction> receiverTransaction;
    Ptr<UbJetty> senderJetty;
};

TargetExecutionPair
BuildTargetExecutionPair()
{
    Config::Reset();
    GlobalValue::Bind("UB_CC_ENABLED", BooleanValue(false));
    TargetExecutionPair pair;
    pair.sender = CreateObject<Node>(0);
    pair.receiver = CreateObject<Node>(0);
    InitNode(pair.sender, UB_DEVICE, 1);
    InitNode(pair.receiver, UB_DEVICE, 1);
    pair.senderPort = DynamicCast<UbPort>(pair.sender->GetDevice(0));
    pair.receiverPort = DynamicCast<UbPort>(pair.receiver->GetDevice(0));

    Ptr<UbLink> link = CreateObject<UbLink>();
    pair.senderPort->Attach(link);
    pair.receiverPort->Attach(link);
    AddShortestRoute(pair.sender,
                     pair.receiver->GetId(),
                     pair.receiverPort->GetIfIndex(),
                     pair.senderPort->GetIfIndex());
    AddShortestRoute(pair.receiver,
                     pair.sender->GetId(),
                     pair.senderPort->GetIfIndex(),
                     pair.receiverPort->GetIfIndex());

    Ptr<UbController> senderCtrl = pair.sender->GetObject<UbController>();
    Ptr<UbController> receiverCtrl = pair.receiver->GetObject<UbController>();
    Connection connection;
    connection.ownerNodeId = pair.sender->GetId();
    connection.node1 = pair.sender->GetId();
    connection.port1 = pair.senderPort->GetIfIndex();
    connection.tpn1 = kTargetExecutionSenderTpn;
    connection.node2 = pair.receiver->GetId();
    connection.port2 = pair.receiverPort->GetIfIndex();
    connection.tpn2 = kTargetExecutionReceiverTpn;
    connection.priority = kTargetExecutionPriority;
    connection.metrics = 0;
    senderCtrl->GetTpConnManager()->AddUnilateralConnection(connection, pair.sender->GetId());
    receiverCtrl->GetTpConnManager()->AddUnilateralConnection(connection, pair.receiver->GetId());
    senderCtrl->GetTransportChannelManager()->CreateTp(pair.sender->GetId(),
                                                       pair.receiver->GetId(),
                                                       pair.senderPort->GetIfIndex(),
                                                       pair.receiverPort->GetIfIndex(),
                                                       kTargetExecutionPriority,
                                                       kTargetExecutionSenderTpn,
                                                       kTargetExecutionReceiverTpn,
                                                       UbCongestionControl::Create(UB_DEVICE));
    receiverCtrl->GetTransportChannelManager()->CreateTp(pair.receiver->GetId(),
                                                         pair.sender->GetId(),
                                                         pair.receiverPort->GetIfIndex(),
                                                         pair.senderPort->GetIfIndex(),
                                                         kTargetExecutionPriority,
                                                         kTargetExecutionReceiverTpn,
                                                         kTargetExecutionSenderTpn,
                                                         UbCongestionControl::Create(UB_DEVICE));

    pair.senderTp = senderCtrl->GetTransportChannelManager()->GetTp(kTargetExecutionSenderTpn);
    pair.receiverTp =
        receiverCtrl->GetTransportChannelManager()->GetTp(kTargetExecutionReceiverTpn);
    pair.senderTransaction = senderCtrl->GetUbTransaction();
    pair.receiverTransaction = receiverCtrl->GetUbTransaction();

    pair.senderFunction = senderCtrl->GetUbFunction();
    pair.senderFunction->CreateJetty(pair.sender->GetId(),
                                     pair.receiver->GetId(),
                                     kTargetExecutionJettyNum);
    NS_ABORT_MSG_IF(!pair.senderTransaction->JettyBindTp(pair.sender->GetId(),
                                                         pair.receiver->GetId(),
                                                         kTargetExecutionJettyNum,
                                                         false,
                                                         {kTargetExecutionSenderTpn}),
                    "sender Jetty must bind to the direct TP");
    pair.senderJetty = pair.senderFunction->GetJetty(kTargetExecutionJettyNum);
    return pair;
}

/** Facts of the request a registered executor observed on the real inbound path. */
struct ObservedTargetRequest
{
    uint32_t calls{0};
    UbTransactionOpcode opcode{UbTransactionOpcode::MAX_OPCODE};
    UbTransactionType type{UbTransactionType::MEMORY};
    uint32_t logicalBytes{0};
    uint32_t payloadBytes{0};
    bool hasResolved{false};
    bool hasMessageTarget{false};
    bool hasImmediate{false};
    bool hasNotify{false};
    bool hasManagement{false};
    bool hasMemoryAccess{false};
    uint32_t managementPduLength{0};
};
} // namespace

/**
 * D7: a real carrier inbound request must reach the registered executor through the common target
 * entry, and its response must travel back to the initiator as a normal transaction completion.
 */
class UbTargetExecutionInboundPathTest : public TestCase
{
  public:
    UbTargetExecutionInboundPathTest()
        : TestCase("all four transaction types reach the executor and complete the initiator")
    {
    }

  private:
    static UbTransactionType RuleTypeOf(UbTransactionOpcode opcode)
    {
        const auto* rule = FindTransactionRule(opcode);
        return rule == nullptr ? UbTransactionType::MEMORY : rule->type;
    }

    void CheckOpcode(UbTransactionOpcode opcode, uint32_t size)
    {
        TargetExecutionPair pair = BuildTargetExecutionPair();
        m_observed = ObservedTargetRequest{};
        NS_TEST_ASSERT_MSG_EQ(
            pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
                [this](Ptr<const UbWqeSegment> request,
                       const UbTransactionRule& rule,
                       UbTargetCompletion done) {
                    ++m_observed.calls;
                    m_observed.opcode = request->GetType();
                    m_observed.type = rule.type;
                    m_observed.logicalBytes = request->GetLogicalBytes();
                    m_observed.payloadBytes = request->GetPayloadBytes();
                    m_observed.hasResolved = request->HasTransactionResolved();
                    const UbTransactionFields& fields = request->GetTransactionFields();
                    m_observed.hasMessageTarget = fields.messageTarget.has_value();
                    m_observed.hasImmediate = fields.immediate.has_value();
                    m_observed.hasNotify = fields.notify.has_value();
                    m_observed.hasManagement = fields.management.has_value();
                    m_observed.hasMemoryAccess = fields.memoryAccess.has_value();
                    m_observed.managementPduLength =
                        fields.management ? fields.management->pduLength : 0;
                    done(UbWorkExecutionResult{});
                })),
            true,
            "target executor registration");

        m_completions = 0;
        m_responseCount = 0;
        pair.senderJetty->SetClientCallback(
            MakeCallback(&UbTargetExecutionInboundPathTest::OnCompletion, this));
        pair.senderTp->TraceConnectWithoutContext(
            "LastPacketReceivesNotify",
            MakeCallback(&UbTargetExecutionInboundPathTest::OnResponsePacket, this));

        Ptr<UbWqe> wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
                                                        pair.receiver->GetId(),
                                                        size,
                                                        700 + static_cast<uint32_t>(opcode),
                                                        opcode);
        NS_TEST_ASSERT_MSG_EQ(
            static_cast<uint32_t>(
                pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status),
            static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
            "the request is submitted through the production path");

        Simulator::Stop(MilliSeconds(1));
        Simulator::Run();

        NS_TEST_ASSERT_MSG_EQ(m_observed.calls, 1u, "the executor is invoked exactly once");
        NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(m_observed.opcode),
                              static_cast<uint32_t>(opcode),
                              "the executor sees the request opcode");
        NS_TEST_ASSERT_MSG_EQ(m_observed.hasResolved,
                              true,
                              "the inbound request carries its cached normalized result");
        NS_TEST_ASSERT_MSG_EQ(m_completions, 1u, "the initiator completes exactly once");
        NS_TEST_ASSERT_MSG_EQ(m_responseCount,
                              1u,
                              "the response sink delivers one response packet");

        switch (RuleTypeOf(opcode))
        {
        case UbTransactionType::MEMORY:
            NS_TEST_ASSERT_MSG_EQ(m_observed.hasMemoryAccess,
                                  true,
                                  "memory requests carry their normalized MAETAH fields");
            break;
        case UbTransactionType::MESSAGE:
        {
            NS_TEST_ASSERT_MSG_EQ(m_observed.hasMessageTarget,
                                  true,
                                  "message requests carry their required MTETAH fields");
            const bool expectsImmediate = opcode == UbTransactionOpcode::SEND_WITH_IMMEDIATE ||
                                          opcode == UbTransactionOpcode::WRITE_WITH_IMMEDIATE;
            NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(m_observed.hasImmediate),
                                  static_cast<uint32_t>(expectsImmediate),
                                  "immediate requests carry their required IMMETAH fields");
            break;
        }
        case UbTransactionType::MAINTENANCE:
            NS_TEST_ASSERT_MSG_EQ(m_observed.hasMemoryAccess,
                                  true,
                                  "maintenance requests carry their normalized MAETAH fields");
            break;
        case UbTransactionType::MANAGEMENT:
            NS_TEST_ASSERT_MSG_EQ(m_observed.hasManagement,
                                  true,
                                  "management requests carry their required MGMTETAH fields");
            NS_TEST_ASSERT_MSG_EQ(m_observed.managementPduLength,
                                  size,
                                  "the defaulted management PDU length follows the payload");
            break;
        }
        Simulator::Destroy();
    }

    void OnCompletion(uint32_t, uint32_t)
    {
        ++m_completions;
    }

    void OnResponsePacket(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t)
    {
        ++m_responseCount;
    }

    void DoRun() override
    {
        // Memory, message, maintenance, and management requests all use the same target entry.
        CheckOpcode(UbTransactionOpcode::WRITE, 64);
        CheckOpcode(UbTransactionOpcode::READ, 64);
        CheckOpcode(UbTransactionOpcode::ATOMIC_SWAP, 8);
        CheckOpcode(UbTransactionOpcode::SEND, 64);
        CheckOpcode(UbTransactionOpcode::SEND_WITH_IMMEDIATE, 64);
        CheckOpcode(UbTransactionOpcode::WRITE_WITH_IMMEDIATE, 64);
        CheckOpcode(UbTransactionOpcode::PREFETCH_TGT, 64);
        CheckOpcode(UbTransactionOpcode::MANAGEMENT, 64);
    }

    ObservedTargetRequest m_observed;
    uint32_t m_completions{0};
    uint32_t m_responseCount{0};
};

/** D7: the single target execution delay controls the executor invocation instant. */
class UbTargetExecutionDelayTimingTest : public TestCase
{
  public:
    UbTargetExecutionDelayTimingTest()
        : TestCase("target execution delay moves the executor call by exactly its value")
    {
    }

  private:
    void CheckDelay(Time delay)
    {
        TargetExecutionPair pair = BuildTargetExecutionPair();
        NS_TEST_ASSERT_MSG_EQ(pair.receiverTransaction->SetTargetExecutionDelay(NanoSeconds(-1)),
                              false,
                              "a strictly negative target execution delay is rejected");
        NS_TEST_ASSERT_MSG_EQ(pair.receiverTransaction->SetTargetExecutionDelay(delay),
                              true,
                              "target execution delay before the first request");
        m_arrival = Seconds(0);
        m_executorCall = Seconds(0);
        m_completed = false;
        m_completedDuringArrival = false;
        pair.receiverTp->TraceConnectWithoutContext(
            "WqeSegmentCompletesNotify",
            MakeCallback(&UbTargetExecutionDelayTimingTest::OnInboundComplete, this));
        NS_TEST_ASSERT_MSG_EQ(
            pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
                [this](Ptr<const UbWqeSegment>, const UbTransactionRule&, UbTargetCompletion done) {
                    m_executorCall = Simulator::Now();
                    done(UbWorkExecutionResult{});
                })),
            true,
            "target executor registration");
        pair.senderJetty->SetClientCallback(
            MakeCallback(&UbTargetExecutionDelayTimingTest::OnCompletion, this));

        Ptr<UbWqe> wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
                                                        pair.receiver->GetId(),
                                                        64,
                                                        800,
                                                        UbTransactionOpcode::WRITE);
        NS_TEST_ASSERT_MSG_EQ(
            static_cast<uint32_t>(
                pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status),
            static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
            "the request is submitted through the production path");

        Simulator::Stop(MilliSeconds(1));
        Simulator::Run();

        NS_TEST_ASSERT_MSG_EQ(m_completed, true, "the request completes on the initiator");
        NS_TEST_ASSERT_MSG_EQ(m_executorCall - m_arrival,
                              delay,
                              "the executor runs exactly one target execution delay after arrival");
        NS_TEST_ASSERT_MSG_EQ(m_completedDuringArrival,
                              false,
                              "target completion is asynchronous, never inline with the arrival");
        NS_TEST_ASSERT_MSG_EQ(
            pair.receiverTransaction->SetAttributeFailSafe("TargetExecutionDelay",
                                                            TimeValue(NanoSeconds(7))),
            false,
            "target execution delay attribute is rejected after the first request");
        Simulator::Destroy();
    }

    void OnInboundComplete(uint32_t, uint32_t, uint32_t)
    {
        m_arrival = Simulator::Now();
        m_completedDuringArrival = m_completed;
    }

    void OnCompletion(uint32_t, uint32_t)
    {
        m_completed = true;
    }

    void DoRun() override
    {
        CheckDelay(NanoSeconds(0));
        CheckDelay(NanoSeconds(500));
    }

    Time m_arrival{Seconds(0)};
    Time m_executorCall{Seconds(0)};
    bool m_completed{false};
    bool m_completedDuringArrival{false};
};

/**
 * D7: the default executor completes asynchronously, a deferred completion does not publish its
 * response early, and a duplicated completion yields exactly one response and one completion.
 */
class UbTargetExecutorAsyncAndDedupTest : public TestCase
{
  public:
    UbTargetExecutorAsyncAndDedupTest()
        : TestCase("target completion is asynchronous, deferred, and deduplicated")
    {
    }

  private:
    void CheckDefaultExecutorIsAsynchronous()
    {
        TargetExecutionPair pair = BuildTargetExecutionPair();
        m_completed = false;
        m_responseCount = 0;
        m_completedAtDelivery = false;
        pair.receiverTp->TraceConnectWithoutContext(
            "WqeSegmentCompletesNotify",
            MakeCallback(&UbTargetExecutorAsyncAndDedupTest::OnInboundComplete, this));
        pair.senderJetty->SetClientCallback(
            MakeCallback(&UbTargetExecutorAsyncAndDedupTest::OnCompletion, this));
        pair.senderTp->TraceConnectWithoutContext(
            "LastPacketReceivesNotify",
            MakeCallback(&UbTargetExecutorAsyncAndDedupTest::OnResponsePacket, this));

        Ptr<UbWqe> wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
                                                        pair.receiver->GetId(),
                                                        64,
                                                        900,
                                                        UbTransactionOpcode::WRITE);
        NS_TEST_ASSERT_MSG_EQ(
            static_cast<uint32_t>(
                pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status),
            static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
            "the request is submitted through the production path");

        Simulator::Stop(MilliSeconds(1));
        Simulator::Run();
        NS_TEST_ASSERT_MSG_EQ(m_completed, true, "the default executor completes the WQE");
        NS_TEST_ASSERT_MSG_EQ(m_responseCount, 1u, "the default executor publishes one response");
        NS_TEST_ASSERT_MSG_EQ(m_completedAtDelivery,
                              false,
                              "the default executor completes asynchronously, not inline");
        Simulator::Destroy();
    }

    void CheckDuplicatedCompletion()
    {
        TargetExecutionPair pair = BuildTargetExecutionPair();
        NS_TEST_ASSERT_MSG_EQ(
            pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
                [](Ptr<const UbWqeSegment>, const UbTransactionRule&, UbTargetCompletion done) {
                    done(UbWorkExecutionResult{});
                    done(UbWorkExecutionResult{});
                })),
            true,
            "target executor registration");
        m_completions = 0;
        m_responseCount = 0;
        pair.senderJetty->SetClientCallback(
            MakeCallback(&UbTargetExecutorAsyncAndDedupTest::OnCompletion, this));
        pair.senderTp->TraceConnectWithoutContext(
            "LastPacketReceivesNotify",
            MakeCallback(&UbTargetExecutorAsyncAndDedupTest::OnResponsePacket, this));

        Ptr<UbWqe> wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
                                                        pair.receiver->GetId(),
                                                        64,
                                                        901,
                                                        UbTransactionOpcode::WRITE);
        NS_TEST_ASSERT_MSG_EQ(
            static_cast<uint32_t>(
                pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status),
            static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
            "the request is submitted through the production path");

        Simulator::Stop(MilliSeconds(1));
        Simulator::Run();
        NS_TEST_ASSERT_MSG_EQ(m_completions, 1u, "a duplicated completion completes the WQE once");
        NS_TEST_ASSERT_MSG_EQ(m_responseCount,
                              1u,
                              "a duplicated completion publishes exactly one response");

        // The executor configuration stays frozen once target execution has started.
        NS_TEST_ASSERT_MSG_EQ(
            pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
                [](Ptr<const UbWqeSegment>, const UbTransactionRule&, UbTargetCompletion done) {
                    done(UbWorkExecutionResult{});
                })),
            false,
            "executor registration is rejected after the first request executed");
        NS_TEST_ASSERT_MSG_EQ(pair.receiverTransaction->SetTargetExecutionDelay(NanoSeconds(7)),
                              false,
                              "target execution delay is rejected after the first request");
        Simulator::Destroy();
    }

    void OnInboundComplete(uint32_t, uint32_t, uint32_t)
    {
        m_completedAtDelivery = m_completed;
    }

    void OnCompletion(uint32_t, uint32_t)
    {
        m_completed = true;
        ++m_completions;
    }

    void OnResponsePacket(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t)
    {
        ++m_responseCount;
    }

    void DoRun() override
    {
        CheckDefaultExecutorIsAsynchronous();
        CheckDuplicatedCompletion();
    }

    bool m_completed{false};
    bool m_completedAtDelivery{false};
    uint32_t m_completions{0};
    uint32_t m_responseCount{0};
};

/** Preserve the global Jetty prefix barrier, but never use a reserved SSN interval. */
class UbInterleavedWqeCompletionTest : public TestCase
{
  public:
    UbInterleavedWqeCompletionTest()
        : TestCase("concurrent segmented WQEs complete only after all actual target executions")
    {
    }

  private:
    void OnCompletion(uint32_t id, uint32_t jetty)
    {
        NS_TEST_ASSERT_MSG_EQ(jetty, kTargetExecutionJettyNum, "correct Jetty");
        NS_TEST_ASSERT_MSG_EQ(++m_callbacks[id], 1u, "exactly one callback");
        NS_TEST_ASSERT_MSG_EQ(m_completed[id], m_expected[id], "all owned TA executions precede success");
    }

    void RunCase(uint32_t count, uint32_t bytes, bool duplicate, bool late)
    {
        auto pair = BuildTargetExecutionPair();
        m_callbacks.clear();
        m_completed.clear();
        m_expected.clear();
        pair.senderJetty->SetTaSegmentBytes(1024);
        pair.senderJetty->SetClientCallback(
            MakeCallback(&UbInterleavedWqeCompletionTest::OnCompletion, this));
        const bool installed = pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
            [this, duplicate](Ptr<const UbWqeSegment> request,
                              const UbTransactionRule&,
                              UbTargetCompletion done) {
                const uint32_t id = request->GetTaskId();
                const uint32_t ssn = request->GetTaSsn();
                const uint64_t delay = 50000 + (id % 3) * 5000 + (ssn % 2) * 10000;
                Simulator::Schedule(NanoSeconds(delay), [this, id, duplicate, done] {
                    ++m_completed[id];
                    done(UbWorkExecutionResult{});
                    if (duplicate)
                    {
                        done(UbWorkExecutionResult{});
                    }
                });
            }));
        NS_TEST_ASSERT_MSG_EQ(installed, true, "install target executor");
        for (uint32_t i = 0; i < count + (late ? 1u : 0u); ++i)
        {
            const uint32_t id = 1001 + i;
            m_expected[id] = (bytes + 1023) / 1024;
            Simulator::Schedule(NanoSeconds(i == count ? 25000 : 10), [&, id, bytes] {
                auto wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
                                                          pair.receiver->GetId(), bytes, id,
                                                          UbTransactionOpcode::WRITE);
                wqe->SetOrderType(OrderType::ORDER_NO);
                const auto result = pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum);
                NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(result.status),
                                      static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
                                      "concurrent WQE accepted without serialization");
            });
        }
        Simulator::Stop(MilliSeconds(2));
        Simulator::Run();
        for (const auto& [id, expected] : m_expected)
        {
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[id], 1u, "no missing callback");
            NS_TEST_ASSERT_MSG_EQ(m_completed[id], expected, "all target executions complete");
            NS_TEST_ASSERT_MSG_EQ(pair.senderTransaction->HasWqeOperation(kTargetExecutionJettyNum, id),
                                  false, "operation is reclaimed");
        }
        NS_TEST_ASSERT_MSG_EQ(pair.senderTransaction->GetResidentOperationCount(), 0u,
                              "all operation records reclaimed");
        NS_TEST_ASSERT_MSG_EQ(pair.senderTransaction->GetResidentSegmentCount(), 0u, "all TA records reclaimed");
        NS_TEST_ASSERT_MSG_EQ(pair.senderJetty->GetActiveWqeCount(), 0u, "all WQEs removed");
        NS_TEST_ASSERT_MSG_EQ(pair.senderJetty->IsIdle(), true, "ACK prefix drained");
        NS_TEST_ASSERT_MSG_EQ(pair.senderTp->GetOutstandingUnackedSegmentCount(), 0u,
                              "sender transport state reclaimed");
        NS_TEST_ASSERT_MSG_EQ(pair.receiverTp->GetOutstandingUnackedSegmentCount(), 0u,
                              "response transport state reclaimed");
        Simulator::Destroy();
    }

    void DoRun() override
    {
        RunCase(1, 64, false, false);
        RunCase(1, 4128, false, false);
        RunCase(3, 64, false, false);
        RunCase(3, 4128, false, false);
        RunCase(3, 4128, true, true);
        RunCase(16, 32800, true, true);
    }
    std::map<uint32_t, uint32_t> m_expected, m_completed, m_callbacks;
};

/** A terminal cleanup can advance the prefix without a later network response. */
class UbTerminalWqeWakeTest : public TestCase
{
  public:
    UbTerminalWqeWakeTest()
        : TestCase("cancel and failure wake completed successors after terminal cleanup")
    {
    }

  private:
    enum class Action { NONE, SUBMIT, CANCEL_SUCCESSOR, DESTROY, REPLACE, B_CANCEL_C, B_DESTROY };
    TargetExecutionPair m_pair;
    Action m_action{Action::NONE};
    UbWorkOutcome m_terminal{UbWorkOutcome::CANCELED};
    std::map<uint32_t, uint32_t> m_callbacks, m_targetDone;

    void Submit(uint32_t id)
    {
        auto wqe = m_pair.senderFunction->CreateWqe(m_pair.sender->GetId(),
                                                     m_pair.receiver->GetId(), 96, id,
                                                     UbTransactionOpcode::WRITE);
        wqe->SetOrderType(OrderType::ORDER_NO);
        NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(
                                  m_pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status),
                              static_cast<uint32_t>(UbWqeSubmissionStatus::ACCEPTED),
                              "WQE accepted on the real native path");
    }

    void OnCompletion(UbWqeCompletion completion)
    {
        const uint32_t id = completion.wqeId;
        NS_TEST_ASSERT_MSG_EQ(++m_callbacks[id], 1u, "terminal callback exactly once");
        UbWorkOutcome expected = UbWorkOutcome::COMPLETED;
        if (id == 1001) expected = m_terminal;
        else if (id == 1002 && m_action == Action::CANCEL_SUCCESSOR)
            expected = UbWorkOutcome::CANCELED;
        else if (id == 1002 && (m_action == Action::DESTROY || m_action == Action::REPLACE))
            expected = UbWorkOutcome::FLUSHED;
        if (id == 1003 && m_action == Action::B_CANCEL_C) expected = UbWorkOutcome::CANCELED;
        if (id == 1003 && m_action == Action::B_DESTROY) expected = UbWorkOutcome::FLUSHED;
        NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(completion.outcome),
                              static_cast<uint32_t>(expected), "correct terminal outcome");
        if (completion.outcome == UbWorkOutcome::COMPLETED)
            NS_TEST_ASSERT_MSG_EQ(m_targetDone[id], 2u, "all target executions precede success");
        if (id == 1002 && m_action == Action::B_CANCEL_C)
            m_pair.senderTransaction->CompleteWqeOperation(kTargetExecutionJettyNum, 1003,
                                                           UbWorkOutcome::CANCELED);
        if (id == 1002 && m_action == Action::B_DESTROY)
        {
            const auto status = m_pair.senderFunction->DestroyJetty(kTargetExecutionJettyNum,
                                                                   UbDestroyReason::SIMULATION_STOP);
            NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(status),
                                  static_cast<uint32_t>(UbDestroyStatus::COMPLETED),
                                  "awakened B callback can destroy the Jetty during recheck");
        }
        if (id != 1001) return;
        NS_TEST_ASSERT_MSG_EQ(m_pair.senderJetty->GetActiveWqeCount(), 1u,
                              "terminal A removed before its callback");
        if (m_action == Action::SUBMIT || m_action == Action::B_CANCEL_C ||
            m_action == Action::B_DESTROY) Submit(1003);
        else if (m_action == Action::CANCEL_SUCCESSOR)
            m_pair.senderTransaction->CompleteWqeOperation(kTargetExecutionJettyNum, 1002,
                                                           UbWorkOutcome::CANCELED);
        else if (m_action == Action::DESTROY || m_action == Action::REPLACE)
        {
            const auto status = m_pair.senderFunction->DestroyJetty(kTargetExecutionJettyNum,
                                                                   UbDestroyReason::SIMULATION_STOP);
            NS_TEST_ASSERT_MSG_EQ(static_cast<uint32_t>(status),
                                  static_cast<uint32_t>(UbDestroyStatus::COMPLETED),
                                  "reentrant forced destroy finishes");
            if (m_action == Action::REPLACE)
            {
                m_pair.senderFunction->CreateJetty(m_pair.sender->GetId(), m_pair.receiver->GetId(),
                                                   kTargetExecutionJettyNum);
                NS_TEST_ASSERT_MSG_EQ(m_pair.senderTransaction->JettyBindTp(
                                          m_pair.sender->GetId(), m_pair.receiver->GetId(),
                                          kTargetExecutionJettyNum, false, {kTargetExecutionSenderTpn}),
                                      true, "replacement Jetty binds");
                m_pair.senderJetty = m_pair.senderFunction->GetJetty(kTargetExecutionJettyNum);
                m_pair.senderJetty->SetTaSegmentBytes(64);
                m_pair.senderJetty->SetWqeCompletionCallback(
                    MakeCallback(&UbTerminalWqeWakeTest::OnCompletion, this));
                Submit(1003);
            }
        }
    }

    void RunCase(UbWorkOutcome outcome, Action action)
    {
        m_pair = BuildTargetExecutionPair();
        m_action = action; m_terminal = outcome;
        m_callbacks.clear(); m_targetDone.clear();
        m_pair.senderJetty->SetTaSegmentBytes(64);
        m_pair.senderJetty->SetWqeCompletionCallback(
            MakeCallback(&UbTerminalWqeWakeTest::OnCompletion, this));
        NS_TEST_ASSERT_MSG_EQ(m_pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
            [this](Ptr<const UbWqeSegment> request, const UbTransactionRule&, UbTargetCompletion done) {
                const uint32_t id = request->GetTaskId();
                Simulator::Schedule(MicroSeconds(id == 1001 ? 200 : 1), [this, id, done] {
                    ++m_targetDone[id];
                    done(UbWorkExecutionResult{});
                    done(UbWorkExecutionResult{}); // duplicate target notification remains suppressed
                });
            })), true, "target executor installed");
        Simulator::Schedule(NanoSeconds(10), [this] { Submit(1001); Submit(1002); });
        Simulator::Schedule(MicroSeconds(100), [this] {
            NS_TEST_ASSERT_MSG_EQ(m_targetDone[1002], 2u, "B complete at target");
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[1002], 0u, "earlier A hole retains prefix barrier");
            m_pair.senderTransaction->CompleteWqeOperation(kTargetExecutionJettyNum, 1001, m_terminal);
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[1001], 1u, "A terminal notified");
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[1002], 1u, "B notified without new traffic");
            const uint32_t expectedC =
                (m_action == Action::B_CANCEL_C || m_action == Action::B_DESTROY) ? 1u : 0u;
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[1003], expectedC,
                                  "newly submitted C is only canceled or flushed, never premature success");
        });
        Simulator::Stop(MicroSeconds(300));
        Simulator::Run();
        NS_TEST_ASSERT_MSG_EQ(m_callbacks[1001], 1u, "late A responses cannot duplicate its terminal event");
        NS_TEST_ASSERT_MSG_EQ(m_callbacks[1002], 1u, "B callback remains exactly once");
        if (action == Action::SUBMIT || action == Action::REPLACE ||
            action == Action::B_CANCEL_C || action == Action::B_DESTROY)
            NS_TEST_ASSERT_MSG_EQ(m_callbacks[1003], 1u, "reentrant C receives its expected terminal outcome");
        NS_TEST_ASSERT_MSG_EQ(m_pair.senderTransaction->GetResidentOperationCount(), 0u,
                              "terminal and successful operation records reclaimed");
        NS_TEST_ASSERT_MSG_EQ(m_pair.senderTransaction->GetResidentSegmentCount(), 0u,
                              "all segment records reclaimed after late responses");
        NS_TEST_ASSERT_MSG_EQ(m_pair.senderJetty->GetActiveWqeCount(), 0u, "no residual WQEs");
        NS_TEST_ASSERT_MSG_EQ(m_pair.senderTp->GetOutstandingUnackedSegmentCount(), 0u,
                              "sender transport reclaimed");
        NS_TEST_ASSERT_MSG_EQ(m_pair.receiverTp->GetOutstandingUnackedSegmentCount(), 0u,
                              "response transport reclaimed");
        Simulator::Destroy();
    }

    void DoRun() override
    {
        for (auto outcome : {UbWorkOutcome::CANCELED, UbWorkOutcome::FAILED})
            for (auto action : {Action::NONE, Action::SUBMIT, Action::CANCEL_SUCCESSOR,
                                Action::DESTROY, Action::REPLACE, Action::B_CANCEL_C, Action::B_DESTROY})
                RunCase(outcome, action);
    }
};

class UbTargetExecutionSeamSuite : public TestSuite
{
  public:
    UbTargetExecutionSeamSuite() : TestSuite("unified-bus-target-execution", Type::UNIT)
    {
        AddTestCase(new UbTerminalWqeWakeTest, TestCase::Duration::QUICK);
        AddTestCase(new UbInterleavedWqeCompletionTest, TestCase::Duration::QUICK);
        AddTestCase(new UbTargetExecutionInboundPathTest, TestCase::Duration::QUICK);
        AddTestCase(new UbTargetExecutionDelayTimingTest, TestCase::Duration::QUICK);
        AddTestCase(new UbTargetExecutorAsyncAndDedupTest, TestCase::Duration::QUICK);
    }
} g_ubTargetExecutionSeamSuite;
} // namespace ns3
