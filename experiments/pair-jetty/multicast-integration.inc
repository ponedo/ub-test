    // Only strategy 3 enters this path. Logical tasks and their audit remain unchanged.
    void SetupMulticast(){
        for(uint32_t task=2*assignments.size();task<transfers.size();++task){auto& x=transfers[task];Require(x.offset==0&&x.bytes==weightBytes&&x.dependencies.empty()&&!P(x.sourcePhysical).replica,"multicast direct child graph");multicastTasks[P(x.physical).expert+1].push_back(task);}
        Require(multicastTasks.size()<=multicast.limit,"multicast lifetime operation limit");
        std::vector<uint32_t> ports;for(uint32_t i=0;i<n;++i)ports.push_back(i);nodes[n]->GetObject<UbSwitch>()->EnableNetworkReplication(ports);
        for(auto&[id,tasks]:multicastTasks){std::vector<lightweight::GroupManager::Member> members;auto src=transfers[tasks.front()].source;
            for(auto task:tasks){auto& x=transfers[task];Require(x.source==src&&x.source!=x.target,"multicast main source");
                const uint32_t txid=n*n+1+2*task,rxid=txid+1,jid=n*n+1+task;Require(uint64_t(n)*n+2ULL*task+2<=UINT32_MAX,"multicast endpoint range");
                Connection c;c.ownerNodeId=src;c.node1=src;c.node2=x.target;c.port1=c.port2=0;c.tpn1=txid;c.tpn2=rxid;c.priority=7;c.metrics=0;
                Ctrl(src)->GetTpConnManager()->AddUnilateralConnection(c,src);Ctrl(x.target)->GetTpConnManager()->AddUnilateralConnection(c,x.target);
                Ctrl(src)->GetTransportChannelManager()->CreateTp(src,x.target,0,0,7,txid,rxid,UbCongestionControl::Create(UB_DEVICE));
                Ctrl(x.target)->GetTransportChannelManager()->CreateTp(x.target,src,0,0,7,rxid,txid,UbCongestionControl::Create(UB_DEVICE));
                auto tx=Ctrl(src)->GetTransportChannelManager()->GetTp(txid),rx=Ctrl(x.target)->GetTransportChannelManager()->GetTp(rxid);TrackTp(src,tx);TrackTp(x.target,rx);
                auto fn=Ctrl(src)->GetUbFunction();Require(!fn->GetJetty(jid),"multicast jetty collision");fn->CreateJetty(src,x.target,jid);Require(Ctrl(src)->GetUbTransaction()->JettyBindTp(src,x.target,jid,false,{txid}),"multicast child bind");auto jetty=fn->GetJetty(jid);jetty->SetTaSegmentBytes(segment);jetty->SetClientCallback(MakeCallback(&Layer::SenderComplete,this));x.jettyId=jid;multicastJetties[task]=jetty;++jettyCount;members.push_back({x.target,task,tx,rx});
            }
            multicast.Add(id,src,weightBytes,segment,DynamicCast<UbPort>(nodes[src]->GetDevice(0)),members);multicast.groups.at(id).queue->grantObserver=[this](uint32_t id,bool control){if(!control)groupGrantTimes[id].push_back(Simulator::Now().GetPicoSeconds());};
        }
        multicast.CheckCapacity(nodes);
        multicast.onComplete=[this](uint32_t id){Require(multicastCompletePs.emplace(id,Simulator::Now().GetPicoSeconds()).second,"duplicate multicast completion");};
        for(uint32_t rank=0;rank<n;++rank){nodes[rank]->GetObject<UbSwitch>()->EnableNetworkSink(rank,Callback<void,uint32_t,uint32_t,Ptr<Packet>>([this,rank](uint32_t id,uint32_t seq,Ptr<Packet> p){multicast.Receive(rank,id,seq,p);}));auto port=DynamicCast<UbPort>(nodes[rank]->GetDevice(0));port->SetReceiveHandler(Callback<void,Ptr<UbPort>,Ptr<Packet>>([this,rank](Ptr<UbPort> port,Ptr<Packet> p){multicast.ReceiveNative(rank,port,p);}));}
    }
    void WriteMulticast(const std::string& out){
        std::ofstream groups(out+"/multicast-groups.csv");groups<<"group,expert,source,task,target,physical,bytes,receiver_ready_ps,sender_complete_ps,group_complete_ps\n";
        for(auto&[id,tasks]:multicastTasks)for(auto task:tasks){auto& x=transfers[task];groups<<id<<','<<P(x.physical).expert<<','<<x.source<<','<<task<<','<<x.target<<','<<x.physical<<','<<x.bytes<<','<<taskAudit[task].finish<<','<<multicast.senderTimes.at(task)<<','<<multicastCompletePs.at(id)<<'\n';}
        std::ofstream stats(out+"/multicast-stats.csv");stats<<"group,source,fanout,payload_bytes,wire_bytes,envelopes,window_wait_checks,empty_wait_checks\n";for(auto&[id,g]:multicast.groups)stats<<id<<','<<g.source<<','<<g.members.size()<<','<<g.queue->payloadSent<<','<<g.queue->wireDataBytes<<','<<g.queue->envelopes<<','<<g.queue->windowWaits<<','<<g.queue->emptyWaits<<'\n';
        std::ofstream ports(out+"/multicast-ports.csv");ports<<"node,port,wire_tx_bytes,peak_egress_bytes,consumed_cells,returned_cells,restored_cells,free_cells,pending_cells,blocked_queries\n";for(uint32_t rank=0;rank<nodes.size();++rank)for(uint32_t p=0;p<nodes[rank]->GetNDevices();++p){auto port=DynamicCast<UbPort>(nodes[rank]->GetDevice(p));auto fc=DynamicCast<UbCbfc>(port->GetFlowControl());Require(bool(fc)&&!port->GetUbQueue()->GetCurrentBytes(),"multicast port drain");Require(portInitialCredit.at({rank,p})-int64_t(fc->GetConsumedCells())+int64_t(fc->GetRestoredCells())==fc->GetTxFreeCells(7),"multicast credit balance");auto peer=DynamicCast<UbPort>(nodes[rank==n?p:n]->GetDevice(rank==n?0:rank));auto peerFc=DynamicCast<UbCbfc>(peer->GetFlowControl());Require(fc->GetConsumedCells()==peerFc->GetReturnedCells()&&peerFc->GetReturnedCells()==fc->GetRestoredCells()+uint64_t(peerFc->GetCrdToReturn(7)),"multicast cross-link credit conservation");ports<<rank<<','<<p<<','<<portTxWire[{rank,p}]<<','<<portQueuePeak[{rank,p}]<<','<<fc->GetConsumedCells()<<','<<fc->GetReturnedCells()<<','<<fc->GetRestoredCells()<<','<<fc->GetTxFreeCells(7)<<','<<fc->GetCrdToReturn(7)<<','<<fc->GetBlockedQueryCount()<<'\n';}
        auto sw=nodes[n]->GetObject<UbSwitch>();auto s=sw->GetNetworkReplicationStats();Require(s.admitted==s.released&&s.branches==s.branchDequeues&&!s.parentBytes&&!s.branchBytes&&!s.descriptors&&!sw->GetQueueManager()->GetSwitchBufferOccupancy().total_buffered_bytes,"multicast branch drain");
    }

    void RecordPacket(uint32_t node,uint32_t port,Ptr<Packet> packet){
        portTxWire[{node,port}]+=packet->GetSize();UbNetworkReplicationTag tag;std::string kind;
        if(packet->PeekPacketTag(tag)&&tag.nativeEnvelope)kind="multicast_data";
        else if(nodes[node]->GetObject<UbSwitch>()->GetPacketTypeForTest(packet)==UB_CONTROL_FRAME)kind="credit";
        else {auto copy=packet->Copy();UbDatalinkPacketHeader dl;UbIpBasedNetworkHeader net;Ipv4Header ip;UdpHeader udp;UbTransportHeader h;copy->RemoveHeader(dl);copy->RemoveHeader(net);copy->RemoveHeader(ip);copy->RemoveHeader(udp);copy->RemoveHeader(h);
            if(UbTransportChannel::IsTransportResponseOpcode(h.GetTPOpcode()))kind="transport_ack";
            else {UbTransportChannel::ReceivedDataPacketContext ctx;Require(packetParser&&packetParser->ParseReceivedDataPacketForTest(packet->Copy(),ctx),"statistics native decode");if(ctx.transactionHeader.GetUbTransactionOpcode()==uint8_t(UbTransactionOpcode::WRITE)){Require(ctx.flowTag.GetFlowId()<transfers.size(),"statistics task");kind=transfers[ctx.flowTag.GetFlowId()].stage==2?"weight_write":"token_write";}else kind="transaction_response";}
        }
        auto& stat=packetStats[{node,port,kind}];++stat.first;stat.second+=packet->GetSize();
    }
    void ObserveQueue(uint32_t node,uint32_t port,bool enqueue,uint32_t size){auto& q=queueTiming[{node,port}];uint64_t now=Simulator::Now().GetPicoSeconds();Require(now>=q.last,"queue observation clock");q.residencePs+=q.count*(now-q.last);q.last=now;if(enqueue)++q.count;else{Require(q.count>0,"queue observation unmatched dequeue");--q.count;++q.departed;}portQueuePeak[{node,port}]=std::max(portQueuePeak[{node,port}],uint64_t(size));}
    void WriteNetworkStats(const std::string& out){
        std::ofstream packets(out+"/packet-counts.csv");packets<<"node,port,kind,packets,wire_bytes\n";for(auto&[key,value]:packetStats){auto[node,port,kind]=key;packets<<node<<','<<port<<','<<kind<<','<<value.first<<','<<value.second<<'\n';}
        std::ofstream queues(out+"/queue-stats.csv");queues<<"node,port,peak_egress_bytes,wire_tx_bytes,dequeued_packets,total_egress_residence_ps\n";for(auto&[key,peak]:portQueuePeak){auto& q=queueTiming[key];Require(!q.count,"queue observation outstanding packets");queues<<key.first<<','<<key.second<<','<<peak<<','<<portTxWire[key]<<','<<q.departed<<','<<q.residencePs<<'\n';}
        if(strategy==3){std::ofstream grants(out+"/multicast-grants.csv");grants<<"group,sequence,grant_ps,since_previous_grant_ps\n";for(auto&[id,times]:groupGrantTimes)for(size_t i=0;i<times.size();++i)grants<<id<<','<<i<<','<<times[i]<<','<<times[i]-(i?times[i-1]:At("planning_end"))<<'\n';}
    }
