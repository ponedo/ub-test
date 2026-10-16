// Independent cancellation/failure wakeup oracle on the original real-link fixture.
#define main OriginalSharedJettyProbeMain
#include "original-shared-jetty-probe.cc"
#undef main

class TerminalWakeProbe {
public:
    TargetExecutionPair pair;
    std::map<uint32_t, unsigned> callbacks;
    std::map<uint32_t, unsigned> targetDone;
    unsigned errors = 0;
    bool holeObserved = false;
    bool fail = false;
    void Snapshot(const char* label) {
        std::cout << Simulator::Now().GetNanoSeconds() << ',' << label
                  << ",una=" << pair.senderJetty->GetTaSsnSndUnaForTest()
                  << ",nxt=" << pair.senderJetty->GetTaSsnSndNxtForTest()
                  << ",active=" << pair.senderJetty->GetActiveWqeCount()
                  << ",A=" << callbacks[1001] << ",B=" << callbacks[1002]
                  << ",C=" << callbacks[1003] << std::endl;
    }
    void Completed(UbWqeCompletion completion) {
        ++callbacks[completion.wqeId];
        const auto expected = completion.wqeId == 1001 ? (fail ? UbWorkOutcome::FAILED : UbWorkOutcome::CANCELED)
                                                      : UbWorkOutcome::COMPLETED;
        if (callbacks[completion.wqeId] != 1 || completion.outcome != expected) ++errors;
        std::cout << "callback," << completion.wqeId << ",outcome="
                  << unsigned(completion.outcome) << std::endl;
        Snapshot("callback_state");
    }
    void Submit(uint32_t id) {
        auto wqe = pair.senderFunction->CreateWqe(pair.sender->GetId(),
            pair.receiver->GetId(), 96, id, UbTransactionOpcode::WRITE);
        wqe->SetOrderType(OrderType::ORDER_NO);
        if (pair.senderFunction->SubmitWqe(wqe, kTargetExecutionJettyNum).status !=
            UbWqeSubmissionStatus::ACCEPTED) ++errors;
    }
    void Target(Ptr<const UbWqeSegment> request, const UbTransactionRule&,
                UbTargetCompletion done) {
        const auto id = request->GetTaskId();
        // A remains semantically incomplete; its TP packet may still be ACKed.
        Simulator::Schedule(MicroSeconds(id == 1001 ? 200 : 1), [this, id, done] {
            ++targetDone[id];
            std::cout << Simulator::Now().GetNanoSeconds() << ",target_done," << id << std::endl;
            done(UbWorkExecutionResult{});
            done(UbWorkExecutionResult{});
        });
    }
    int Run() {
        pair = BuildTargetExecutionPair();
        pair.senderJetty->SetTaSegmentBytes(64);
        pair.senderJetty->SetWqeCompletionCallback(
            MakeCallback(&TerminalWakeProbe::Completed, this));
        if (!pair.receiverTransaction->SetTargetExecutor(UbTargetExecutor(
            [this](Ptr<const UbWqeSegment> r, const UbTransactionRule& rule,
                   UbTargetCompletion done) { Target(r, rule, done); }))) return 2;
        Simulator::Schedule(NanoSeconds(10), [this] { Submit(1001); Submit(1002); });
        Simulator::Schedule(MicroSeconds(100), [this] {
            Snapshot("before_cancel");
            if (targetDone[1002] != 2 || callbacks[1002] != 0) ++errors;
            pair.senderTransaction->CompleteWqeOperation(kTargetExecutionJettyNum,
                1001, fail ? UbWorkOutcome::FAILED : UbWorkOutcome::CANCELED);
            Snapshot("after_cancel");
        });
        Simulator::Schedule(MicroSeconds(150), [this] {
            Snapshot("quiet_after_cancel");
            holeObserved = callbacks[1002] == 0 &&
                pair.senderJetty->GetTaSsnSndUnaForTest() ==
                    pair.senderJetty->GetTaSsnSndNxtForTest() &&
                pair.senderJetty->GetActiveWqeCount() == 1;
            if (callbacks[1002] != 1 || callbacks[1001] != 1) ++errors;
        });
        Simulator::Schedule(MicroSeconds(200), [this] { Submit(1003); });
        Simulator::Stop(MicroSeconds(300));
        Simulator::Run();
        Snapshot("final");
        if (callbacks[1001] != 1 || callbacks[1002] != 1 || callbacks[1003] != 1 ||
            pair.senderJetty->GetActiveWqeCount() != 0) ++errors;
        if (pair.senderTransaction->GetResidentOperationCount() != 0 ||
            pair.senderTransaction->GetResidentSegmentCount() != 0 ||
            pair.senderTp->GetOutstandingUnackedSegmentCount() != 0 ||
            pair.receiverTp->GetOutstandingUnackedSegmentCount() != 0) ++errors;
        std::cout << "hole_observed=" << holeObserved << ",errors=" << errors << std::endl;
        Simulator::Destroy();
        return errors ? 1 : 0;
    }
};
int main(int argc, char** argv) { TerminalWakeProbe probe; CommandLine cmd; cmd.AddValue("fail", "Use FAILED instead of CANCELED", probe.fail); cmd.Parse(argc, argv); return probe.Run(); }
