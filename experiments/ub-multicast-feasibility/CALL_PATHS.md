# 调用路径与扩展位置

以下箭头是源码调用关系，不是本轮运行的事件时间线。路径均相对被审计原生树。只有最后两图是拟议扩展。

## 单播提交与事务分段（实际实现）

```text
UbFunction::SubmitWqe [protocol/ub-function.cc:155–241]
  → UbJetty::CanAcceptWqe [1058–1072]
  → UbJetty::PushWqe [1386–1424]
  → segment generation [1287–1378] / CommitWqeSegmentAdmission [1192–1236]
  → UbTransaction::TryAdmitRtpSegment [protocol/ub-transaction.cc:1218–1325]
      → pick one admissible TP member, not all members
  → UbTransportChannel::BuildRtpDataPacket [protocol/ub-transport.cc:1043–1067]
```

上述缩写文件全部位于 `src/unified-bus/model/`。一个 WQE/segment 复制一个 src/dest；未绑定目的地址的 Jetty 不等于多目标 WQE。

## 单播网络数据通路（实际实现）

```text
UbPort::Receive → DispatchReceive → HandleWithUbSwitch
 [ub-port.cc:875–912]
 → UbSwitch::SwitchHandlePacket [ub-switch.cc:717–745]
    → restore incoming link credit once
 → HandleURMADataPacket [751–768]
 → ForwardDataPacket [973–1005]
    → ResolveURMAOutput [1093–1111]
    → UbRoutingProcess::GetOutPortInternal [protocol/ub-routing-process.cc:450–532]
       → select ONE candidate
 → SendPacket [1344–1346]
 → ForwardDataPacketAfterAdmission [449–478]
 → MoveInPortProcessingToVoq [482–495]
 → FinalizeForwardedPacketEnqueue [498–531]
 → per-output allocator [ub-switch-allocator.cc:652–710]
 → UbEgressQueue [ub-port.cc:59–110]
 → DequeuePacket [532–565] → TransmitPacket [790–842]
 → UbLink::TransmitStart [ub-link.cc:174–203]
 → destination port receive
```

CTP/LDST 有自己的解析/目的端判断，但仍采用单输出选择，详见 NETWORK_SWITCH_AUDIT.md。不能将候选路由或 TP group 误读为广播。

## 传输 ACK 与事务完成（实际实现）

```text
Receiver SinkTpDataPacket [ub-switch.cc:819–881]
 → ResolveInboundTp [ub-transport-channel-manager.cc:238–299]
 → RecvDataPacket [protocol/ub-transport.cc:2353–2391]
    ├→ transport ACK [BuildTransportResponsePacket:2066–2113]
    │   → sender TP ACK progress [1689–1714,1732–1763]
    │   → only ACK-completable rules [ShouldCompleteOnTpAck:1343–1360]
    └→ completed TA [CompleteInboundTaUnits:2334–2346]
        → ExecuteInboundTransaction / RunInboundTransaction
          [protocol/ub-transaction.cc:1969–2043]
        → target execution callback
        → BuildTransactionResponse [2057–2100]
        → ProcessInboundTaResponse [2114–2177]
        → ProcessWqeSegmentComplete [1921–1950]
        → RecordSegmentSuccess [1859–1918]
 → Jetty SSN contiguous prefix [protocol/ub-function.cc:1446–1505]
 → CheckAndRemoveCompletedWqe / IsWqeCompleted [1518–1548,1629–1641]
 → ApplyWqeTerminal [1567–1593]
```

这不是“所有 ACK 都等待目标执行”的图。事务规则决定是否必须等待 Response。一个目标失败时的有界通知路径仍有缺口，不能以未来多目标聚合掩盖。

## 网络复制 PoC（设计，尚未实现）

```text
one source payload → normal source link → switch incoming credit processing
 → versioned group / recipient resolver
 → atomic replication reservation OR explicit pending branch mask
 → independent Packet copies + one ingress credit owner
    ├→ B VOQ → allocator → bounded egress → physical link → B sink
    ├→ C VOQ → allocator → bounded egress → physical link → C sink
    └→ D VOQ → allocator → bounded egress → physical link → D sink
```

每个下行有独立带宽、排队和信用；上游只归还一次原始入站信用。只证明网络复制，不产生可靠组 WQE 成功通知。

## 可靠组播 PoC（设计，尚未实现）

```text
frozen membership + operation ID + epoch
 → per-target execution / transport contexts
 → shared multicast payload path (requires new wire/identity reconciliation)
 → B/C/D individual target execution responses
 → validate (operation,epoch,target,segment)
 → per-target missing-segment retry / terminal outcome
 → all required targets SUCCESS ? exactly-one group SUCCESS : explicit failure
 → retire payload, branches, response state and leases after defined drain
```

多个原生单播 child WQE 的聚合是先行正确性 oracle；它与真正的 shared multicast payload path 分开，不减少源端数据发送量。
