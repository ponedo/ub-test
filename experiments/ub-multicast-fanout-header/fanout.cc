// SPDX-License-Identifier: GPL-2.0-only
// Isolated weights-only fixture. The accepted Layer, graph, payload, native WRITE,
// target execution, dependency gates, and online audit remain unchanged.
#define main accepted_pair_layer_main
#include "../pair-jetty/pair-layer.cc"
#undef main
#include <openssl/sha.h>

namespace {
std::string Sha256(const std::vector<uint8_t>& data)
{
    unsigned char digest[SHA256_DIGEST_LENGTH];
    Require(SHA256(data.data(), data.size(), digest) != nullptr, "SHA256 failed");
    std::ostringstream out;
    for (auto byte : digest)
        out << std::hex << std::setfill('0') << std::setw(2) << unsigned(byte);
    return out.str();
}

struct Fanout {
    Layer layer;
    std::string out, strategy = "direct", headerModel = "full";
    uint32_t fanout = 1, weightBytes = 18 * 1024 * 1024;
    uint64_t predictedTas = 0, predictedEdges = 0, mainBytes = 0, forwardedBytes = 0;
    uint64_t candidateRelays = 0, gain = 0;
    bool relayEnabled = false;
    std::string sourceSha;
    std::map<uint32_t, uint64_t> senderTimes;
    struct PortObservation { uint64_t tx = 0, rx = 0, consumed = 0, returned = 0; };
    std::map<std::pair<uint32_t,uint32_t>, PortObservation> observed;
    std::map<std::tuple<uint32_t,uint32_t,bool,bool,uint32_t>, uint64_t> sizes;
    std::map<uint32_t, uint64_t> ingressPeak;
    std::ofstream wire;

    void Prepare()
    {
        Require(fanout == 1 || fanout == 2 || fanout == 3 || fanout == 4 || fanout == 8,
                "fanout must be 1, 2, 3, 4, or 8");
        Require(weightBytes > 0 && weightBytes <= 18 * 1024 * 1024, "weight byte bound");
        Require(strategy == "direct" || strategy == "chunk-streaming" || strategy == "multicast",
                "unknown strategy");
        Require(headerModel == "full" || headerModel == "compact-oracle" || headerModel == "ideal-oracle",
                "unknown header model");
        Require(strategy == "multicast" || headerModel == "full", "header model requires multicast");
        Require(layer.logLevel == "summary" || layer.logLevel == "events" || layer.logLevel == "debug",
                "unknown log level");
        const std::set<std::string> faults{"", "payload-byte", "early-wqe", "missing-wqe", "duplicate-completion",
            "weight-byte", "premature-ready", "duplicate-weight", "early-compute", "early-group", "relay-byte",
            "relay-buffer-byte", "duplicate-notify", "early-relay", "early-final-ready"};
        Require(faults.count(layer.fault), "unknown fault");
        auto& l = layer;
        // No Planner input or artificial token assignment is created. Resident
        // expert placement is metadata only; only expert zero emits weight data.
        l.n = 64; l.e = 128; l.k = 8; l.t = 0;
        l.dim = 4096; l.ff = 1536; l.dtype = 2; l.segment = 1024;
        l.peak = 1000; l.util = 500; l.setup = 100; l.seed = 20261016;
        l.linkGbps = 100; l.linkDelayNs = 20; l.matrices = 3;
        l.weightBytes = weightBytes; l.bytes = l.dim * l.dtype;
        l.planningNs = l.rerouteNs = l.weightCompleteNs = 0;
        l.balanced = 1; l.strategy = strategy == "direct" ? 0 : strategy == "chunk-streaming" ? 2 : 3;
        l.jettyMode = "pair"; l.dependencyMode = l.onlineMembershipMode = "index";
        l.weightOptions.nodes = l.n; l.weightOptions.domain.assign(l.n, 0);
        l.weightOptions.chunkBytes = 4096; l.weightOptions.minReplicas = 4;
        l.weightOptions.maxRelays = 8; l.weightOptions.minFanoutGain = 2;
        l.weightOptions.forceRelay = false;
        l.weightOptions.shardCut = weightBytes % 3 == 0 ? weightBytes / 3 * 2 : 0;
        Require(l.payloadBudgetBytes > 0 && l.payloadBudgetBytes <= UINT64_C(8)*1024*1024*1024,
                "payload budget range");
        Require(l.weightTaskLimit > 0 && l.weightTaskLimit <= 1000000, "weight task limit range");
        Require(Layer::CheckedMul(fanout, weightBytes) <= l.payloadBudgetBytes, "logical payload bound");
#ifndef FANOUT_LEGACY_HEADER
        l.multicast.headerMode = headerModel == "full" ? lightweight::HeaderMode::FULL :
            headerModel == "compact-oracle" ? lightweight::HeaderMode::COMPACT_ORACLE :
            lightweight::HeaderMode::IDEAL_ORACLE;
#else
        Require(headerModel == "full", "legacy build supports full header only");
#endif
        l.placement.resize(l.e);
        for (uint32_t expert = 0; expert < l.e; ++expert) {
            const uint32_t rank = expert / 2;
            l.placement[expert] = rank;
            l.pIndex.emplace(expert, l.physical.size());
            l.physical.push_back({expert, expert, rank, 0, 0, expert, rank});
        }
        for (uint32_t rank = 1; rank <= fanout; ++rank) {
            const uint32_t id = l.e + rank - 1;
            Require(l.pIndex.emplace(id, l.physical.size()).second, "duplicate replica ID");
            l.physical.push_back({id, 0, rank, 1, 0, 0, 0});
        }
        l.expected.assign(l.n, 0); l.arrived.assign(l.n, 0);
        l.started.assign(l.n, false); l.finished.assign(l.n, false);
        l.physicalArrived.assign(l.physical.size(), 0);
        l.weightReady.resize(l.physical.size());
        l.weightData.resize(l.physical.size()); l.weightCoverage.resize(l.physical.size());
        for (size_t i = 0; i < l.physical.size(); ++i) {
            l.weightReady[i] = !l.physical[i].replica;
            if (l.physical[i].replica) {
                l.weightData[i].resize(weightBytes);
                l.weightCoverage[i] = std::make_unique<ChunkTracker>(weightBytes);
                ++l.pendingWeights;
            }
        }
        // The eligibility calculation is an audit prediction, never a substitute
        // for the production graph generator immediately below.
        if (fanout > 1) {
            while ((candidateRelays + 1) * (candidateRelays + 1) <= fanout) ++candidateRelays;
            candidateRelays = std::min({candidateRelays, uint64_t(l.weightOptions.maxRelays), uint64_t(fanout - 1)});
            gain = fanout - std::max(candidateRelays, (fanout - candidateRelays + candidateRelays - 1) / candidateRelays);
        }
        relayEnabled = strategy == "chunk-streaming" && candidateRelays && fanout >= 4 && gain >= 2;
        uint64_t chunks = 1;
        if (relayEnabled) {
            auto ceil = [](uint64_t x) { return (x + 4095) / 4096; };
            chunks = l.weightOptions.shardCut ? ceil(l.weightOptions.shardCut) + ceil(weightBytes - l.weightOptions.shardCut) : ceil(weightBytes);
        }
        predictedEdges = Layer::CheckedMul(fanout, chunks);
        Require(predictedEdges <= l.weightTaskLimit && predictedEdges <= INT32_MAX, "weight task count bound");
        const auto edges = strategy == "chunk-streaming" ?
            ChunkStreamingRelay(l.weightOptions).Edges(l.physical, weightBytes) :
            DirectWeightDistribution().Edges(l.physical, weightBytes);
        Require(edges.size() == predictedEdges, "production graph count differs from prediction");
        std::map<uint32_t, std::unique_ptr<ChunkTracker>> finalCoverage;
        for (uint32_t rank = 1; rank <= fanout; ++rank)
            finalCoverage.emplace(l.e + rank - 1, std::make_unique<ChunkTracker>(weightBytes));
        for (const auto& edge : edges) {
            auto& source = l.P(edge.sourcePhysical); auto& target = l.P(edge.targetPhysical);
            Require(source.expert == 0 && target.expert == 0 && target.replica &&
                    source.rank != target.rank && edge.bytes && edge.offset < weightBytes &&
                    edge.bytes <= weightBytes - edge.offset, "weight edge identity/range");
            l.AddTransfer(2, target.id, source.rank, target.rank, target.id, edge.bytes);
            l.transfers.back().sourcePhysical = source.id; l.transfers.back().offset = edge.offset;
            finalCoverage.at(target.id)->Notify(l.transfers.size() - 1, edge.offset, edge.bytes);
            predictedTas = Layer::CheckedAdd(predictedTas, (uint64_t(edge.bytes) + l.segment - 1) / l.segment);
            (source.replica ? forwardedBytes : mainBytes) += edge.bytes;
        }
        Require(predictedTas <= UINT32_MAX, "logical TA count bound");
        for (const auto& [id, coverage] : finalCoverage) Require(coverage->Complete(), "incomplete graph target coverage");
        Require(mainBytes + forwardedBytes == uint64_t(fanout) * weightBytes, "graph payload conservation");
        Require(bool(forwardedBytes) == relayEnabled, "actual relay differs from eligibility");
        // Same indexed predicates and append order as Layer::Read. FullExpert
        // parents cover that source; GroupChunk parents include every Stage-I
        // target for the expert and byte range, not only the forwarding relay.
        std::map<std::tuple<uint32_t,uint32_t,uint32_t>, std::vector<uint32_t>> groups;
        std::map<uint32_t, std::vector<uint32_t>> parents;
        for (uint32_t task = 0; task < l.transfers.size(); ++task) {
            const auto& x = l.transfers[task]; parents[x.physical].push_back(task);
            if (!l.P(x.sourcePhysical).replica) groups[{l.P(x.physical).expert, x.offset, x.bytes}].push_back(task);
        }
        l.dependents.resize(l.transfers.size());
        for (uint32_t task = 0; task < l.transfers.size(); ++task) {
            auto& x = l.transfers[task]; if (!l.P(x.sourcePhysical).replica) continue;
            const auto scope = edges[task].sourceDependency;
            ChunkTracker coverage(scope == WeightReadyScope::FullExpert ? weightBytes : x.bytes);
            const auto& candidates = scope == WeightReadyScope::GroupChunk ?
                groups.at({l.P(x.physical).expert, x.offset, x.bytes}) : parents.at(x.sourcePhysical);
            for (auto parent : candidates) {
                const auto& y = l.transfers[parent];
                if (scope == WeightReadyScope::GroupChunk) {
                    if (l.P(y.sourcePhysical).replica || l.P(y.physical).expert != l.P(x.physical).expert ||
                        y.offset != x.offset || y.bytes != x.bytes) continue;
                } else if (y.physical != x.sourcePhysical) continue;
                Require(parent < task, "dependency order/cycle");
                x.dependencies.push_back(parent); l.dependents[parent].push_back(task);
                if (y.physical == x.sourcePhysical)
                    coverage.Notify(parent, scope == WeightReadyScope::GroupChunk ? 0 : y.offset, y.bytes);
            }
            Require(coverage.Complete(), "relay source dependency coverage");
            if (scope == WeightReadyScope::GroupChunk)
                Require(x.dependencies.size() == candidateRelays, "group dependency must include every selected relay");
        }
        std::vector<uint8_t> original(weightBytes);
        for (uint32_t i = 0; i < weightBytes; ++i) original[i] = l.WeightByte(0, i);
        sourceSha = Sha256(original);
        Require(l.assignments.empty() && l.t == 0 && l.pendingWeights == fanout, "weights-only fixture");
    }

    void ObservePacket(uint32_t rank, uint32_t port, bool tx, Ptr<Packet> packet)
    {
        UbNetworkReplicationTag tag;
        bool envelope = packet->PeekPacketTag(tag) && tag.nativeEnvelope;
        bool control = !envelope && layer.nodes[rank]->GetObject<UbSwitch>()->GetPacketTypeForTest(packet) == UB_CONTROL_FRAME;
        const uint64_t cells = control ? 0 : (packet->GetSize() + 159) / 160;
        auto& o = observed[{rank, port}];
        if (tx) { o.tx += packet->GetSize(); o.consumed += cells; }
        else { o.rx += packet->GetSize(); o.returned += cells; }
        ++sizes[{rank,port,tx,control,packet->GetSize()}];
        if (wire) wire << Simulator::Now().GetPicoSeconds() << ',' << (tx ? "tx" : "rx") << ',' << rank << ',' << port << ',' << packet->GetSize() << ',' << cells << ',' << (control ? "credit" : envelope ? "multicast_data" : "native_data") << '\n';
    }

    void Observe()
    {
        auto& l = layer;
        // An observational callback preserves the original completion function,
        // including all native identity, target-ready and multicast checks.
        std::set<std::pair<uint32_t,uint32_t>> jetties;
        for (const auto& x : l.transfers) if (jetties.emplace(x.source,x.jettyId).second)
            l.Ctrl(x.source)->GetUbFunction()->GetJetty(x.jettyId)->SetClientCallback(
                Callback<void,uint32_t,uint32_t>([this](uint32_t task,uint32_t jetty) {
                    layer.SenderComplete(task,jetty);
                    Require(senderTimes.emplace(task, Simulator::Now().GetPicoSeconds()).second, "duplicate observed sender completion");
                }));
        for (uint32_t rank = 0; rank < l.nodes.size(); ++rank) {
            l.nodes[rank]->GetObject<UbSwitch>()->GetQueueManager()->TraceConnectWithoutContext(
                "IngressQueueOccupancyBytes", Callback<void,uint32_t,uint32_t,uint64_t>(
                [this,rank](uint32_t,uint32_t,uint64_t bytes) { ingressPeak[rank] = std::max(ingressPeak[rank],bytes); }));
            for (uint32_t port = 0; port < l.nodes[rank]->GetNDevices(); ++port) {
                auto p = DynamicCast<UbPort>(l.nodes[rank]->GetDevice(port));
                p->TraceConnectWithoutContext("TraComEventNotify", Callback<void,Ptr<Packet>,Time>(
                    [this,rank,port](Ptr<Packet> packet,Time) { ObservePacket(rank,port,true,packet); }));
                p->TraceConnectWithoutContext("PktRcvNotify", Callback<void,Ptr<Packet>>(
                    [this,rank,port](Ptr<Packet> packet) { ObservePacket(rank,port,false,packet); }));
            }
        }
    }

    void WritePorts()
    {
        auto& l = layer;
        std::ofstream f(out + "/ports.csv");
        f << "node,port,wire_tx_bytes,wire_rx_bytes,egress_peak,ingress_peak,initial_cells,consumed_cells,returned_cells,restored_cells,free_cells,pending_cells,blocked_queries,observed_consumed_cells,observed_returned_cells,egress_capacity,ingress_capacity,egress_final_bytes,switch_buffer_final_bytes\n";
        for (uint32_t rank = 0; rank < l.nodes.size(); ++rank) {
            auto sw = l.nodes[rank]->GetObject<UbSwitch>();
            Require(!sw->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes, "switch buffer not drained");
            Require(ingressPeak[rank] <= sw->GetQueueManager()->GetReservePerQueueBytes(), "ingress capacity exceeded");
            for (uint32_t port = 0; port < l.nodes[rank]->GetNDevices(); ++port) {
                auto p = DynamicCast<UbPort>(l.nodes[rank]->GetDevice(port));
                auto fc = DynamicCast<UbCbfc>(p->GetFlowControl()); Require(bool(fc), "missing CBFC");
                auto peer = DynamicCast<UbPort>(l.nodes[rank == l.n ? port : l.n]->GetDevice(rank == l.n ? 0 : rank));
                auto peerFc = DynamicCast<UbCbfc>(peer->GetFlowControl()); Require(bool(peerFc), "missing peer CBFC");
                const auto initial = l.portInitialCredit.at({rank,port}); const auto& o = observed[{rank,port}];
                UintegerValue capacity; p->GetUbQueue()->GetAttribute("MaxEgressBytes",capacity);
                Require(!p->GetUbQueue()->GetCurrentBytes() && l.portQueuePeak[{rank,port}] <= capacity.Get(), "egress overflow/leak");
                Require(o.tx == p->GetTxBytes() && o.tx == l.portTxWire[{rank,port}], "actual wire TX counters differ");
                Require(fc->GetConsumedCells() == o.consumed && fc->GetReturnedCells() == o.returned, "actual packet/cell accounting differs");
                Require(initial - int64_t(fc->GetConsumedCells()) + int64_t(fc->GetRestoredCells()) == fc->GetTxFreeCells(7), "local credit conservation");
                Require(fc->GetConsumedCells() == peerFc->GetReturnedCells() &&
                        peerFc->GetReturnedCells() == fc->GetRestoredCells() + uint64_t(peerFc->GetCrdToReturn(7)), "cross-link credit conservation");
                // Small sub-threshold pending returns are legal; record them.
                f << rank << ',' << port << ',' << o.tx << ',' << o.rx << ',' << l.portQueuePeak[{rank,port}] << ',' << ingressPeak[rank] << ',' << initial << ',' << fc->GetConsumedCells() << ',' << fc->GetReturnedCells() << ',' << fc->GetRestoredCells() << ',' << fc->GetTxFreeCells(7) << ',' << fc->GetCrdToReturn(7) << ',' << fc->GetBlockedQueryCount() << ',' << o.consumed << ',' << o.returned << ',' << capacity.Get() << ',' << sw->GetQueueManager()->GetReservePerQueueBytes() << ',' << p->GetUbQueue()->GetCurrentBytes() << ',' << sw->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes << '\n';
            }
        }
        const auto s = l.nodes[l.n]->GetObject<UbSwitch>()->GetNetworkReplicationStats();
        Require(s.admitted == s.released && s.branches == s.branchDequeues && !s.parentBytes && !s.branchBytes && !s.descriptors, "replication state leak");
        Require(bool(s.admitted) == (strategy == "multicast"), "unexpected replication activity");
        std::ofstream replication(out + "/replication-state.csv");
        replication << "node,admitted,released,branches,branch_dequeues,parent_bytes,branch_bytes,descriptors,outstanding_parents\n";
        replication << l.n << ',' << s.admitted << ',' << s.released << ',' << s.branches << ',' << s.branchDequeues << ',' << s.parentBytes << ',' << s.branchBytes << ',' << s.descriptors << ',' << l.nodes[l.n]->GetObject<UbSwitch>()->GetNetworkOutstandingParents() << '\n';
        Require(!l.nodes[l.n]->GetObject<UbSwitch>()->GetNetworkOutstandingParents(), "outstanding multicast parents");
        std::ofstream hist(out + "/packet-sizes.csv"); hist << "node,port,direction,control,wire_bytes,packets,cells_per_packet\n";
        for (const auto& [key,count] : sizes) { auto [rank,port,tx,control,bytes] = key;
            hist << rank << ',' << port << ',' << (tx ? "tx" : "rx") << ',' << control << ',' << bytes << ',' << count << ',' << (control ? 0 : (bytes + 159) / 160) << '\n'; }
        Require(bool(f) && bool(hist) && bool(replication), "port evidence write");
    }

    void WriteTaskEvidence()
    {
        auto& l = layer;
        std::ofstream tasks(out + "/task-timeline.csv"), receivers(out + "/receiver-stats.csv"), segments;
        tasks << "task,send_ps,ready_ps,sender_complete_ps,last_ta_complete_ps,ta_count,completed_tas,covered_bytes,payload_sha256\n";
        receivers << "rank,is_target,received_payload_bytes,received_tas,ready_physical_count\n";
        if (l.logLevel == "debug") {
            segments.open(out + "/ta-audit.csv");
            segments << "task,offset,bytes,admitted_ps,received_ps,verified_ps,completed_ps\n";
        }
        std::vector<uint64_t> actualBytes(l.n,0), actualTas(l.n,0);
        for (uint32_t task = 0; task < l.transfers.size(); ++task) {
            const auto& x = l.transfers[task]; const auto& a = l.taskAudit[task];
            uint64_t covered = 0, completed = 0, last = 0;
            for (size_t index = 0; index < a.segments.size(); ++index) {
                const auto& s = a.segments[index]; const uint64_t offset = index*l.segment;
                const uint64_t bytes = std::min<uint64_t>(l.segment,x.bytes-offset);
                Require(s.state == 4 && s.admitted <= s.received && s.received <= s.verified && s.verified <= s.completed,
                        "invalid terminal segment audit");
                covered += bytes; ++completed; last = std::max(last,s.completed);
                if (segments) segments << task << ',' << offset << ',' << bytes << ',' << s.admitted << ',' << s.received << ',' << s.verified << ',' << s.completed << '\n';
            }
            Require(covered == x.bytes && last == a.finish && a.finish == a.latest, "task aggregate coverage/timing");
            actualBytes[x.target] += covered; actualTas[x.target] += completed;
            tasks << task << ',' << a.send << ',' << a.finish << ',' << senderTimes.at(task) << ',' << last << ',' << a.segments.size() << ',' << completed << ',' << covered << ',' << Sha256(x.data) << '\n';
        }
        for (uint32_t rank = 0; rank < l.n; ++rank) {
            const bool target = rank >= 1 && rank <= fanout;
            Require(actualBytes[rank] == (target ? weightBytes : 0), "non-target payload or missing receiver payload");
            receivers << rank << ',' << target << ',' << actualBytes[rank] << ',' << actualTas[rank] << ',' << (target ? 1 : 0) << '\n';
        }
        Require(bool(tasks) && bool(receivers) && (l.logLevel != "debug" || bool(segments)), "task evidence write");
    }

    void WriteHeaderAccounting()
    {
        std::ofstream f(out + "/header-accounting.csv");
        f << "group,fanout,header_model,payload_sent,wire_data_bytes,charged_header_bytes,native_child_header_bytes,full_model_header_bytes,envelopes,oracle_pending_count,oracle_native_metadata_bytes,peak_oracle_native_metadata_bytes,peak_oracle_envelopes,window_wait_queries,empty_wait_queries,barrier_queries\n";
        for (const auto& [id,g] : layer.multicast.groups) {
            auto q = g.queue;
            uint64_t charged = q->wireDataBytes-q->payloadSent;
            uint64_t native = uint64_t(g.members.size())*78*((uint64_t(weightBytes)+1023)/1024);
            uint64_t full = charged, pending = 0, retained = 0, peakBytes = 0, peakEnvelopes = 0;
#ifndef FANOUT_LEGACY_HEADER
            Require(charged == q->chargedHeaderBytes, "charged header accounting differs from actual bytes");
            native = q->nativeChildHeaderBytes; full = q->fullModelHeaderBytes;
            pending = q->GetOraclePendingCount(); retained = q->oracleNativeMetadataBytes;
            peakBytes = q->peakOracleNativeMetadataBytes; peakEnvelopes = q->peakOracleEnvelopes;
            Require(!pending && !retained, "oracle metadata not drained");
#endif
            f << id << ',' << g.members.size() << ',' << headerModel << ',' << q->payloadSent << ',' << q->wireDataBytes << ',' << charged << ',' << native << ',' << full << ',' << q->envelopes << ',' << pending << ',' << retained << ',' << peakBytes << ',' << peakEnvelopes << ',' << q->windowWaits << ',' << q->emptyWaits << ',' << q->barrierChecks << '\n';
        }
        Require(bool(f), "header accounting write");
    }

    void WriteNativeState()
    {
        auto& l = layer; std::ofstream f(out + "/native-final-state.csv");
        f << "source,target,jetty,ta_una,ta_nxt,active_wqes,tx_una,tx_nxt,tx_outstanding,rx_una,rx_nxt,rx_outstanding\n";
        std::set<std::pair<uint32_t,uint32_t>> seen;
        for (const auto& x : l.transfers) if (seen.emplace(x.source,x.jettyId).second) {
            auto jetty = l.Ctrl(x.source)->GetUbFunction()->GetJetty(x.jettyId);
            Ptr<UbTransportChannel> tx,rx;
            if (strategy == "multicast") {
                const auto [group,rank] = l.multicast.tasks.at(&x - l.transfers.data());
                const auto& members = l.multicast.groups.at(group).members;
                auto it = std::find_if(members.begin(),members.end(),[&](const auto& m) { return m.rank == rank; });
                Require(it != members.end(), "missing native child"); tx = it->tx; rx = it->rx;
            } else {
                tx = l.Ctrl(x.source)->GetTransportChannelManager()->GetTp(l.Tpn(x.source,x.target));
                rx = l.Ctrl(x.target)->GetTransportChannelManager()->GetTp(l.Tpn(x.target,x.source));
            }
            Require(jetty->IsIdle() && !jetty->GetActiveWqeCount() &&
                    jetty->GetTaSsnSndUnaForTest() == jetty->GetTaSsnSndNxtForTest() &&
                    tx->IsSafeForExplicitDestroy() && rx->IsSafeForExplicitDestroy() &&
                    !tx->GetOutstandingUnackedSegmentCount() && !rx->GetOutstandingUnackedSegmentCount(), "native endpoint/window not drained");
            f << x.source << ',' << x.target << ',' << x.jettyId << ',' << jetty->GetTaSsnSndUnaForTest() << ',' << jetty->GetTaSsnSndNxtForTest() << ',' << jetty->GetActiveWqeCount() << ',' << tx->GetPsnSndUna() << ',' << tx->GetPsnSndNxt() << ',' << tx->GetOutstandingUnackedSegmentCount() << ',' << rx->GetPsnSndUna() << ',' << rx->GetPsnSndNxt() << ',' << rx->GetOutstandingUnackedSegmentCount() << '\n';
        }
        Require(bool(f), "native state write");
    }

    void WriteResult()
    {
        auto& l = layer; uint64_t allReady = 0, allSender = 0;
        std::ofstream targets(out + "/targets.csv");
        targets << "expert,physical,rank,payload_bytes,ready_ps,ready_duration_ps,sender_complete_ps,received_sha256,received_fnv1a64\n";
        for (uint32_t rank = 1; rank <= fanout; ++rank) {
            const uint32_t pid = l.e + rank - 1; const auto index = l.pIndex.at(pid);
            const auto ready = l.uniqueEvents.at({"weight_ready",int(pid),int(rank),0,uint64_t(weightBytes)});
            uint64_t sender = 0; for (auto task : l.auditReplicaMembers.at(pid)) sender = std::max(sender,senderTimes.at(task));
            const auto hash = Sha256(l.weightData[index]); Require(hash == sourceSha, "received SHA256 differs from source");
            Require(sender >= ready, "sender before target ready"); allReady = std::max(allReady,ready); allSender = std::max(allSender,sender);
            targets << "0," << pid << ',' << rank << ',' << weightBytes << ',' << ready << ',' << ready - l.At("weights_start") << ',' << sender << ',' << hash << ',' << Layer::Hex(Layer::Hash(14695981039346656037ULL,reinterpret_cast<const char*>(l.weightData[index].data()),weightBytes)) << '\n';
        }
        Require(allReady == l.At("weights_end") && allReady == l.stageIntervals[2][1], "all-target readiness aggregation");
        Require(l.taCount == predictedTas && l.verifiedSegments == predictedTas && l.transfers.size() == predictedEdges, "task/TA prediction mismatch");
        Require(l.verifiedBytes[0] == 0 && l.verifiedBytes[1] == 0 && l.stageReadyCounts[0] == 0 && l.stageReadyCounts[1] == 0 &&
                !l.spans.count("compute_start") && !l.spans.count("compute_end") && !l.spans.count("expert_start") && !l.spans.count("expert_end"), "weights-only fixture emitted compute/token work");
        uint64_t sourcePayload = mainBytes, sourceDataWire = 0, envelopes = 0, windowWaits = 0, emptyWaits = 0, barrierChecks = 0, groupComplete = 0;
        for (const auto& [key,value] : l.packetStats) { auto [node,port,kind] = key;
            if (node == 0 && (kind == "weight_write" || kind == "multicast_data")) sourceDataWire += value.second; }
        if (strategy == "multicast") {
            Require(l.multicast.groups.size() == 1, "single expert requires one group");
            const auto& q = l.multicast.groups.begin()->second.queue;
            sourcePayload = q->payloadSent; envelopes = q->envelopes; windowWaits = q->windowWaits;
            emptyWaits = q->emptyWaits; barrierChecks = q->barrierChecks;
            groupComplete = l.multicastCompletePs.at(l.multicast.groups.begin()->first);
            Require(sourcePayload == weightBytes && sourceDataWire == q->wireDataBytes && groupComplete >= allSender, "multicast source/completion metrics");
        }
        std::ofstream summary(out + "/fanout-summary.json");
        summary << "{\"schema\":1,\"status\":\"PASS\",\"workload\":\"single-expert-weight-fanout-only\",\"planner_executed\":false,\"tokens\":0,\"compute_events\":0,\"strategy\":\"" << strategy << "\",\"header_model\":\"" << headerModel << "\",\"ep\":64,\"expert\":0,\"source\":0,\"fanout\":" << fanout << ",\"weight_bytes\":" << weightBytes << ",\"ta_bytes\":1024,\"chunk_bytes\":4096,\"shard_cut\":" << l.weightOptions.shardCut << ",\"seed\":20261016,\"link_gbps\":100,\"link_delay_ns\":20,\"source_sha256\":\"" << sourceSha << "\",\"relay_candidate_count\":" << candidateRelays << ",\"relay_gain\":" << gain << ",\"relay_enabled\":" << (relayEnabled ? "true" : "false") << ",\"relay_direct_fallback\":" << (strategy == "chunk-streaming" && !relayEnabled ? "true" : "false") << ",\"weight_wqes\":" << l.transfers.size() << ",\"weight_tas\":" << l.taCount << ",\"sender_completions\":" << l.senderCount << ",\"logical_receiver_bytes\":" << uint64_t(fanout)*weightBytes << ",\"main_logical_send_bytes\":" << mainBytes << ",\"relay_logical_send_bytes\":" << forwardedBytes << ",\"source_wire_payload_bytes\":" << sourcePayload << ",\"source_data_wire_bytes\":" << sourceDataWire << ",\"source_full_native_child_equivalent_data_wire_bytes\":" << uint64_t(fanout)*(weightBytes+78*((uint64_t(weightBytes)+1023)/1024)) << ",\"weights_start_ps\":" << l.At("weights_start") << ",\"all_receivers_ready_ps\":" << allReady << ",\"all_receivers_ready_duration_ps\":" << allReady-l.At("weights_start") << ",\"all_senders_complete_ps\":" << allSender << ",\"multicast_group_complete_ps\":" << groupComplete << ",\"multicast_envelopes\":" << envelopes << ",\"multicast_window_wait_queries\":" << windowWaits << ",\"multicast_empty_wait_queries\":" << emptyWaits << ",\"multicast_barrier_queries\":" << barrierChecks << ",\"simulator_events\":" << Simulator::GetEventCount() << ",\"executed_graph_fnv1a64\":\"" << l.GraphHash() << "\",\"payload_persisted\":false,\"all_port_credit_conservation\":true,\"native_windows_drained\":true}\n";
        Require(bool(targets) && bool(summary), "result write");
    }

    void Run()
    {
        Prepare(); auto& l = layer;
        Require(!std::filesystem::exists(out) || std::filesystem::is_empty(out), "output must be fresh/empty");
        std::filesystem::create_directories(out); l.InitAudit(); l.WriteArtifacts(out);
        if (l.logLevel != "summary") { l.log.open(out + "/events.csv"); l.log << "time_ps,event,stage,id,node,offset,bytes,task\n"; }
        if (l.logLevel == "debug") {
            l.admissions.open(out + "/ta-identity.csv"); l.admissions << "time_ps,task,jetty,logical_ssn,offset,bytes\n";
            wire.open(out + "/wire.csv"); wire << "time_ps,event,node,port,wire_bytes,cells,kind\n";
        }
        l.Topology(out); Observe();
        Simulator::Schedule(PicoSeconds(Layer::startPs), &Layer::Start, &l);
        Simulator::Stop(Seconds(10)); Simulator::Run();
        for (const auto& x : l.transfers) Require(x.nextOffset == x.bytes && x.pendingResponses.empty() && x.sent && x.ready && x.senderDone, "unfinished native transfer");
        Require(l.dispatchStarted && l.receivedTokens == 0 && l.pendingWeights == 0 && l.senderCount == l.remoteCount && senderTimes.size() == l.transfers.size(), "unfinished fanout");
        for (auto ready : l.weightReady) Require(ready, "missing final weight");
        l.pairJetties->CheckIdle(); l.FinalAudit();
        if (strategy == "multicast") {
            l.multicast.CheckDrained(); for (const auto& [task,jetty] : l.multicastJetties) Require(jetty->IsIdle(), "multicast jetty not idle");
            l.WriteMulticast(out);
        }
        WritePorts(); WriteNativeState(); WriteTaskEvidence(); WriteHeaderAccounting();
        l.WriteNetworkStats(out); WriteResult();
        // Retained only as a compatibility audit artifact. fanout-summary.json is
        // the benchmark authority; its all-receiver metric is not MoE latency.
        l.WriteSummary(out);
        l.admissions.close(); l.log.close(); wire.close();
        UbUtils::Get()->Destroy(); l.traceOn = false; Simulator::Destroy();
        std::cout << "PASS weights-only fanout=" << fanout << " strategy=" << strategy << " header=" << headerModel << '\n';
    }
};
}

int main(int argc, char** argv)
{
    Time::SetResolution(Time::PS); Fanout benchmark;
    benchmark.layer.payloadBudgetBytes = UINT64_C(8)*1024*1024*1024;
    benchmark.layer.weightTaskLimit = 1000000;
    CommandLine cmd;
    cmd.AddValue("out", "Fresh private output directory", benchmark.out);
    cmd.AddValue("strategy", "direct/chunk-streaming/multicast", benchmark.strategy);
    cmd.AddValue("headerModel", "full/compact-oracle/ideal-oracle", benchmark.headerModel);
    cmd.AddValue("fanout", "Number of target ranks: 1,2,3,4,8", benchmark.fanout);
    cmd.AddValue("bytes", "Weight bytes, default 18 MiB; smaller values are correctness fixtures", benchmark.weightBytes);
    cmd.AddValue("logLevel", "summary/events/debug", benchmark.layer.logLevel);
    cmd.AddValue("fault", "Existing Layer fault injection for negative controls", benchmark.layer.fault);
    cmd.AddValue("payloadBudgetBytes", "Logical payload guard, maximum 8 GiB", benchmark.layer.payloadBudgetBytes);
    cmd.AddValue("weightTaskLimit", "Weight-task guard, maximum 1000000", benchmark.layer.weightTaskLimit);
    cmd.Parse(argc,argv);
    try { Require(!benchmark.out.empty(), "missing output directory"); benchmark.Run(); }
    catch (const std::exception& error) {
        if (benchmark.layer.traceOn) UbUtils::Get()->Destroy();
        std::cerr << "FAIL fanout: " << error.what() << '\n'; return 2;
    }
    return 0;
}
