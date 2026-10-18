# 最小改动面与阶段门槛（仅设计）

本表是预计设计接点，不是补丁清单，也不是承诺文件数量/工期。实际实现应另行批准。`model/` 均指 `src/unified-bus/model/`。

| 阶段 / 接点 | 预计扩展 | 当前依据 | 风险 |
|---|---|---|---|
| 网络：`ub-switch.h/.cc` | 显式 opt-in 组播分类、冻结成员、解析 child 输出集合；保留原单播入口 | `ForwardDataPacket` 973–1005, `ForwardDataPacketAfterAdmission` 449–478 | 不能把多个单输出调用当作原子复制；避免回入端口/重复成员 |
| 网络：`protocol/ub-routing-process.h/.cc`、组表辅助类 | 新的输出集合解析与组版本；不要修改现有单输出 API 的语义 | `GetOutPortInternal` 450–532, `SelectOutPort` 595–608 | ECMP 候选路径不是复制树；多交换机回路/重复路径 |
| 网络：新序列化 multicast Header，关联 `protocol/ub-header.*` | Group/epoch 或 destination set，操作和分支身份；正确的 wire bytes | `src/network/model/packet.cc` `AddHeader` 257–265, `AddPacketTag` 949–953 | tag 免费字节导致带宽/信用测量失真；MTU 变化 |
| 网络：`ub-queue-manager.h/.cc`、`ub-switch-allocator.h/.cc` | 复制存储预留、共享入站 ownership、pending mask、独立分支 drain | QueueManager 185–261; RR allocator 652–710 | 单入站信用不能担保 N 倍存储；半发送后整包重试造成重复 |
| 网络：`protocol/ub-cbfc.h/.cc` / 流控事件上下文 | 原入站信用恰好归还一次，逐出口信用分别扣除；与 recovery tag 分离 | `OnIngressReleased` 147–156, `OnEgressEnqueued` 159–166 | 信用膨胀/死锁/错误 piggyback；PFC、DWRR、故障恢复都要回归 |
| 网络：`ub-port.*`、`ub-link.*` | 优先复用既有实现；只有统计/封装有缺口才添加接口 | `TransmitPacket` 790–842, `TransmitStart` 174–203 | 直接调用底层发包跳过队列；真实多分支链路计费遗漏 |
| 可靠性参照：新增 GroupOperation helper | 多个合法单播子操作的不可变成员及终态聚合 | `UbFunction::SubmitWqe` 155–241; `ApplyWqeTerminal` 1567–1593 | 此阶段不节省源链路字节；超时/失败边界不能假设原生完备 |
| 真正共享发送：`protocol/ub-function.*`、`ub-datatype.h` | 新 opt-in 组操作/成员结构，可外包为新 API；不要求立即新建 Group Jetty | `CanAcceptWqe` 1058–1072; `ub-function.h` 320–333,427–447 | Jetty ID 与组操作 ID 不可混用；一个 unbound Jetty 仍非多目标 WQE |
| 真正共享发送：`protocol/ub-transaction.h/.cc` | 每 target/segment 状态、响应归属、父操作终态、生命周期 | `OperationRecord` 618–645; `RecordSegmentSuccess` 1859–1918; `ProcessInboundTaResponse` 2114–2177 | 第一响应提前清理、旧 epoch 响应、部分成功、取消与晚到响应 |
| 真正共享发送：`protocol/ub-transport.h/.cc`、`ub-transport-channel-manager.*` | 对端上下文和每目标序号空间与共享包身份协调 | `ResolveInboundTp` 238–299; `TrackInboundTaPacket` 1168–1223; transport header 698–746 | 简单改目的 IP 不够；PSN/TPN/TA correlation 均需明确映射 |
| 真正共享发送：`protocol/ub-retrans.h/.cc` | 逐目标重传、有界失败和清理；保持原单播流程隔离 | `OnTimeout` 1201–1225; `ReTxTimeout` 2394–2402 | 当前 retry exhaustion 使用断言，不能直接假设有 FAILED 回调 |

## Group Jetty 是否必要

现有源 Jetty 可以是目的绑定或未绑定；`UbJetty::CanAcceptWqe` 只在 `HasBoundDest()` 时要求 WQE 目的相同（`protocol/ub-function.cc:1058–1072`）。因此不能武断宣称“必须新增 Group Jetty”。最小可靠性参照可以复用普通 Jetty/TP 和接收端执行机制，由独立父操作聚合子 WQE。真正共享发送仍要解决包内目的和每目标完成状态，Group Jetty 这个名字不会自动解决问题。

## 分阶段验收门槛

### Gate 0：本轮只读审计

执行源码哈希、限定范围搜索、引用锚点检查、文档审查；明确 UNKNOWN 和源树版本。结果不构成网络复制或可靠组播功能通过。到此停止等待验收。

### Gate 1：网络复制 PoC

固定 A→单交换机→B/C/D。A 上行只一份 payload；每个下行自己的正常队列和链路；逐目标校验字节。覆盖 fanout 0/1/3、一个堵塞出口、不同链路速率、存储不足、重复成员、非成员排除、信用归还、分支恢复和最终清理。显式定义复制缓存/成本，不在本门槛声称 WQE/事务可靠完成。只有成功后才加多交换机树/动态组。

### Gate 2：多目标可靠语义参照

普通 unicast children + parent 聚合。验证子操作独立成功/失败、父操作恰好一次完成、最慢目标的必要执行条件、取消、晚到响应、资源清理。响应要求取决于事务规则；本项目可靠权重分发 PoC 应明确要求目标执行完成。网络到达或一个目标 ACK 都不足以通过本门槛。

### Gate 3：共享发送与可靠组播

落实每目标 TA/TP 身份、重传、操作 epoch、target-specific outcome。逐目标注入 data/ACK/Response 丢失、乱序、重复、永久失败。确认 B/D 成功不错误完成 C，选择性重传和去重正确，失败不伪装成功，有界停止且状态释放。对写入副作用不承诺取消回滚；初始排除 READ/原子操作。

### Gate 4：动态组与性能实验

比较 A/B/C，计入组建立/生效屏障/retire、wire header、控制/ACK/retry 流量、复制引擎假设，固定相同成员与 payload。先测每边字节和全部目标完成，再测 UltraEP 收益。不能用模拟器初始化 CPU wall time 代替 simulated control-plane latency。

## 后续必须回归的单播范围（本轮未运行）

- `src/unified-bus/test/ub-test.cc`：既有 Jetty/TP 绑定、WQE 生命周期、队列/流控、并发分段完成测试。
- `src/unified-bus/test/ub-target-execution-test.cc`：目标执行延迟与响应依赖。
- `src/unified-bus/test/ub-reliable-rerouting-test.cc`：恢复信用标记、路由故障行为。
- `src/unified-bus/test/ub-structured-routing-test.cc`：单输出路由规则。
- `src/unified-bus/test/ub-packet-rate-control-test.cc`：出口字节/速率与 NOB 约束。
- `src/unified-bus/test/ub-transaction-rules-test.cc`、`ub-transaction-header-extension-test.cc`：ACK/Response 规则与报文解析。
- UltraEP 历史 Pair Jetty、多 WQE 交错/取消、No Balancing、Direct、Two-Stage、Chunk Streaming、日志在线验证/故障注入：相同输入输出与事件时间线对照。

这里列的是未来代码修改后的验收要求；本轮没有重新编译运行这些测试。
