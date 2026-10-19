# ns-3-ub 协议处理时延与 Multicast 公平性审计

## 结论

**当前研究不必为了“补上软件层固定处理时延”而先实现完整原生组播 WQE/TA。推荐有明确验收门槛的轻量方案 A；现有 network-only PoC 本身还不能直接与 UltraEP Direct/Chunk 做公平性能对照。**

理由是当前真实 Qwen3 实验中，WQE 创建、提交、TA 构建和 Payload 校验只消耗宿主机 CPU；发起端协议派发和目标端事务执行的配置延迟均为 **0 ns**。但原生路径仍产生真实的分段、协议头、Transport ACK、事务 Response，以及受窗口/队列约束的发送过程。这些都会影响模拟网络时间，不能用“延迟都是零”推导出“绕过协议没有影响”。

最重要的完成口径区别：

- WRITE 的**发送端成功通知**须等目标事务成功执行、其 Response 回传并通过验证，再满足 Jetty 的完成前缀条件；Transport ACK 本身不能让 WRITE 成功。
- UltraEP 当前的 **Chunk Ready、Weight Ready、Relay 转发和 Layer End**由目标端执行完成及覆盖检查推进，不以发送端 WQE 通知为显式门槛。最终 PASS 另外检查发送端全部完成与状态回收。
- 因此不能把每个 Response RTT 简单加到 Layer Latency，也不能因为它不是显式屏障就删除它：回包竞争与窗口释放仍影响后续传输。

本轮仅阅读源码与已完成实验的配置/证据，没有修改运行源码、参数、协议，没有编译或运行新的仿真实验。

## 1. 审计版本、证据与定位约定

公开交付基线：[5f3fccf8e09b08c60963f1c4a69cf9f3de9c714b](https://github.com/ponedo/ub-test/commit/5f3fccf8e09b08c60963f1c4a69cf9f3de9c714b)。原生源码重建为 `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b` 加该交付的 `accepted-unicast-baseline.patch` 与 `network-replication.patch`。本机原生快照 HEAD 为 `cc3b9e29d2f59fa9cb5b94217bab989d44dc0ae7`；它是本地原生仓库提交，不冒充外层 GitHub Commit。

以下定位采用两种根目录：

- **N/**：上述重建后的 ns-3-ub 源码根目录。
- **P/**：公开 `ponedo/ub-test` 根目录；所有应用路径以 `experiments/` 开头。

表中的 `文件:行号` 均对应实际已读文件，不是推测的上游最新版。原生仓库并未完整嵌入外层 GitHub；8 个组播改动文件可在 [上轮源码快照](../ub-network-multicast-poc/native/src/unified-bus/model) 阅读，其余原生文件按上述基线和补丁定位。不要把不存在的 `ponedo/ub-test/ns-3-ub/...` 当作源码链接。

本轮实际检查：

1. 源码调用路径、默认属性、设置点及事件调度点。
2. 已完成的 512/1024/2048 Token × L0/L37/L52 × 3 策略共 **27 个案例**的私有归档，校验 archive/config/input SHA256，仅输出安全的 runtime 投影与标量头部，见 [effective-config-evidence.json](effective-config-evidence.json)。没有公开逐 Token 数据。
3. 发送命令均未携带协议时延属性覆盖；参数值通过生成器、文本输入、对象构造逐段追踪。
4. 源码锚点与前后源码一致性检查，见 [source-anchor-checks.json](source-anchor-checks.json) 和 [validation.json](validation.json)。这些是静态/历史配置核验，不能冒充新的运行测量。

## 2. 实际配置如何进入对象

真实执行链不是“看同目录 fixed-config 就结束”：

1. `P/experiments/qwen-real-batch-scaling/run_size.py:38–50` 调用 `qwen-real-minimal/prepare.py`，执行器命令仅有 input/out/capacityMetrics、pair、summary 和容量预算。
2. `P/experiments/qwen-real-minimal/prepare.py:61–79` **实际读取 `qwen-prefill-token-scaling/fixed-config.json`**，继承时延/网络参数，再覆盖 H=4096、I=1536、activation dtype=2、weight dtype=1。相邻 `qwen-real-minimal/fixed-config.json` 是说明性配置，不能单独作为执行依据。
3. `P/experiments/direct-weight-forward/adapter.py:62–73` 序列化 runtime；No Balancing 的 planning/reroute 清零。`P/experiments/multi-npu-relay/adapter.py:72–79` 加入 Relay 参数和策略，并生成最终 input.txt。
4. `P/experiments/pair-jetty/pair-layer.cc:97–106` 读取标量；`:203` 设置每个端口速率；`:246` 设置每条链路传播时延；`:250–283` 配置 Pair Jetty 和目标执行回调。
5. 27 个实际归档的 config/input 内容与 manifest 哈希相符，时延值一致。没有调用 `SetTargetExecutionDelay`，没有对 Controller 两项协议时延或 switch processing 做覆盖，故采用下列源码默认。

### 当前 Direct / Chunk 的有效时延

| 项目 | 实际值 / 行为 | 配置与消费位置 |
|---|---|---|
| WQE 创建 | 无独立模拟延迟 | N/src/unified-bus/model/protocol/ub-function.cc:113–139 `CreateWqe` |
| WQE 提交/校验 | 无独立提交服务延迟 | 同文件:155–241 `SubmitWqe` |
| InitiatorProtocolDispatchDelay | **0 ns**；若设置正值为每 WQE 首次派发门槛，后续 TA 不重复收费 | N/src/unified-bus/model/ub-controller.cc:26–37；protocol/ub-transaction.cc:710–774 `StartDispatchGate` |
| TA 准备/入队 | `ScheduleNow`，零时间事件；容量等待可为正 | N/src/unified-bus/model/protocol/ub-transaction.cc:914–1025,1355–1435 |
| TargetExecutionDelay / m_targetExecutionDelay | **0 ns**；正值时每完整 TA 请求一次 | N/src/unified-bus/model/protocol/ub-transaction.cc:202–213,1968–2044；.h:653–655 |
| 应用 weight_completion_ns | **0 ns** | 消费配置:238；pair-layer.cc:279–282 |
| reorder_ns / slow_relay_ns | **0 / 0 ns** | 消费配置:249–251；pair-layer.cc:280–282 |
| InitiatorProtocolCompletionVisibilityDelay | 默认 **0 ns**；当前 pair-layer **不经过其消费路径** | N/src/unified-bus/model/ub-app.cc:506–526；P/experiments/pair-jetty/pair-jetty-manager.h:31–35 |
| Switch InPortProcessingDelay | **0 ns** | N/src/unified-bus/model/ub-switch.cc:79–84,454–484；pair-layer 未覆盖 |
| AllocationTime | **5 ns / 仲裁轮** | N/src/unified-bus/model/ub-switch-allocator.cc:75–89,158–177 |
| 端口数据率 / link propagation | **100 Gbit/s / 每链路20 ns** | pair-layer.cc:203,246；N/src/unified-bus/model/ub-port.cc:805–840；ub-link.cc:174–195 |
| IFG / packet-rate pacing | **0 / NONE** | N/src/unified-bus/model/ub-port.cc:165–201 |
| 仿真 Planning / Reroute | balanced **200 / 100 ns**；No Balancing **0 / 0** | 消费配置:224–241；direct adapter:62；pair-layer.cc:368–377 |
| Expert setup | **100 ns / 有负载的物理 Expert**，另加实际 Assignment FLOPs / 假设500 GFLOP/s | pair-layer.cc:316–323；不是协议处理延迟 |

这里“消费配置”指 `P/experiments/qwen-prefill-token-scaling/fixed-config.json`。有效值也在归档投影内验证。

**Completion visibility 陷阱：**该 Controller 属性由 `UbApp::OnTaskCompleted` 在正值时调度 `OnTaskCompletedVisible`；pair-layer 没有使用 UbApp，而是直接把 `Layer::SenderComplete` 绑定到 Jetty。只改该属性不会使当前应用通知变慢。不能将它当作现有比较里已付出的额外延迟。

**模拟时间与 CPU：**`N/src/core/model/default-simulator-impl.cc:119–134` 在取出事件时推进模拟时钟，再执行 callback；`:212–229,265–270` 分别实现按 delay 调度和零延迟 ScheduleNow。普通 C++ 分配、循环、复制、校验不自动推进时钟。应用的 `Validate` 用 `std::chrono` 计宿主机验证时间（pair-layer.cc:292），与 `online-validation.inc:129` 的 layer_latency_ps 分开。

## 3. Direct / Chunk 协议事件时间线

这是一条由源码证明的因果时间线，**不是本轮新测的延迟曲线**。两策略共用协议路径，区别是 Weight Transfer 图、WQE 大小及 Relay 依赖。

```
Layer::Send(task) @ t0
  构造实际 Payload → CreateWqe → SubmitWqe                同一模拟时刻
  → StartDispatchGate                                   当前 +0 ns（每 WQE 一次）
  → EnqueueRtpWqe → RunRtpTx → PrepareNextWqeSegment
  → TryAdmitRtpSegment                                   ScheduleNow / 窗口等待
  → WqeSegmentTriggerPortTransmit
  → 源 NPU 原生 allocator → egress → UbPort → UbLink      仲裁、序列化、20 ns传播
  → Switch admission → input processing → VOQ
  → allocator → egress → UbPort → UbLink                 当前processing0ns，真实队列/链路
  → 目标 Transport 收包、按 PSN 排序、完整 TA 组装
      ├─ Transport ACK 入原生返回队列                    不代表 WRITE 执行成功
      └─ HandleInboundTaUnit → ExecuteInboundTransaction
           → TargetExecutionDelay                       当前 +0 ns
           → 应用逐字节检查、done(success)               当前应用服务延迟 +0 ns
                ├─ BuildTransactionResponse → 反向 RTP 真实网络
                └─ target_complete → Coverage → Ready
                      → Weight Ready / Relay / Compute / Combine 等依赖
Response 抵达发起端
  → 校验 Task / Jetty / SSN / 端点 / opcode / Payload
  → 标记本 TA 完成 → 推进 Jetty 连续完成前缀
  → WQE 全部分段已发送且其实际最后 SSN 已越过完成前缀
  → SenderComplete（当前无 UbApp visibility wrapper）
```

具体路径定位：

- 创建/提交：`N/src/unified-bus/model/protocol/ub-function.cc:113–241`。
- 发起端 gate / preparation / admission：`N/src/unified-bus/model/protocol/ub-transaction.cc:685–809,914–1025,1311–1435,1687–1724`。
- Transport packet 构造/发出：`N/src/unified-bus/model/protocol/ub-transport.cc:807–856,1104–1163,2419–2445,2636–2640`。
- Switch 收包分流：`N/src/unified-bus/model/ub-switch.cc:845–883`。TA 数据与 TP 响应依据 **TP opcode** 分流，不能只看 TAACK 字样。
- TA 组装和向事务层提交：`N/src/unified-bus/model/protocol/ub-transport.cc:1256–1340,2333–2391`。
- 目标延迟/执行/生成 Response：`N/src/unified-bus/model/protocol/ub-transaction.cc:1953–2112`。
- 反向 Response 入传输队列：同文件 `:1439–1578`；该回包不是直接 Schedule 一个发送端成功。
- initiator 响应验证与完成：同文件 `:1921–1950,2114–2177`；`ub-function.cc:1446–1593,1629–1641`。

### 非零时间不能简单累加

AllocationTime=5ns 是仲裁流水线延迟，host 与 switch 都有 allocator；`UbPort::TransmitComplete` 附近的预取可与当前序列化重叠（ub-port.cc:1004–1012）。不要把所有包的 5ns 相加当作 Layer Latency。每跳发射使用实际 packet 字节计算序列化，link 在 `txTime + propagation` 时交付；竞争、信用与窗口返回使等待时间依赖运行状态。

同样，正值 DispatchDelay 是独立 operation 的并行延迟，不是有限 CPU 发起速率；正值 TargetExecutionDelay 是每 TA 管线延迟，不是独占的内存/执行引擎。当前源码不能用这两个参数单独证明真实硬件协议处理吞吐。

## 4. WRITE、Response 与完成条件

### 4.1 必须等待什么

`N/src/unified-bus/model/protocol/ub-transaction-rules.cc:28–75` 的 WRITE 规则要求事务 Response，成功响应使用 TAACK、零 Payload。目标执行 callback 成功后才由 `RunInboundTransaction` 建立 Response；重复 callback 有 guard（ub-transaction.cc:2025–2043）。

`UbTransportChannel::ShouldCompleteOnTpAck`（ub-transport.cc:1343–1360）明确：Transport ACK 仅释放 wire segment；requiresResponse 的请求不能在这里报告成功。Response 本身通过反向 RTP、原生队列和链路返回，验证后才更新 TA/Jetty 完成状态。

当前修复后的 `UbJetty::IsWqeCompleted`（ub-function.cc:1629–1641）检查：

- WQE 的所有待分段工作已发完；
- 有实际最后 admitted TA SSN；
- 这个实际 SSN 已小于 Jetty 的 `sndUna` 连续完成前缀。

这既避免多个 WQE 交错 SSN 时提前成功，也保留共享 Jetty 的前缀约束：当前 WQE 可能等待其他 WQE 的较早 SSN。不能仅用该 WQE 的一个末段或 TP ACK 判断完成。取消/失败关闭前缀空洞后重查后续完成的既有修复位于 ub-transaction.cc:2889–2909，本轮没有修改。

### 4.2 ACK 与 Response 不能混淆

`BuildTransportResponsePacket`（ub-transport.cc:2066–2102）也添加 ATAH/TAACK，但 TP opcode 为 Transport ACK。真正事务 Response 经可靠 TA 数据路径返回并进入 `ProcessInboundTaResponse`。所以在日志里看到“TAACK”不够，必须同时看 TP opcode、segment kind 和事务关联身份。

Response 零 Payload 仍有真实线速头部；`GetPayloadBytesThisPacket`（ub-transport.cc:54–63）明确不把内部调度用的一字节进度变成虚假线上 Payload。Response 也可能受反向传输容量和信用限制。

### 4.3 Layer Latency 到底在何处结束

`P/experiments/pair-jetty/pair-layer.cc:269–282` 先调用 done(success) 入队 Response，然后在相同 callback 内记录目标完成、更新逐 TA 覆盖。只有全部覆盖完整才 Ready；`nb-tracker.h:25–45` 定义该检查。

- `Ready` 与 `FinalWeight`：pair-layer.cc:325–347，推进完整权重与 Relay 依赖。
- `Gate`：`:367`，等 planning、reroute、weights 均完成。
- Dispatch target ready 启动本 NPU Compute：`:340`；Compute 完成提交 Combine：`:317–323`。
- 所有 Token 的 Top-k 贡献在目标端齐备时 `layer_end`：`:341`。
- `online-validation.inc:102,129` 检查最终 token 时刻并计算 layer_end−layer_start。
- `SenderComplete`（pair-layer.cc:58–64）记录通知和检查 ready，不触发计算/Relay；退出验收另查 senderCount/idle（`:383–392`）。

这意味着推荐组播路径也应分别记录 receiver-ready、group sender-complete 和最终 drain，而不是把所有接收者通知的 RTT 偷偷增加到原来 receiver-ready 驱动的 Layer 关键路径。

## 5. Network PoC 省略了什么

当前 PoC 的 Direct 对照也是单目标 `SubmitNetworkPacket`，**不是 UltraEP 的 WRITE Direct**。之前 64KiB 的网络复制结果不能直接当作 UltraEP 协议栈加速结果（network-poc.cc:150–159）。

| 环节 | 当前 UltraEP Direct / Chunk | Network Multicast PoC | 对时间或语义的影响 |
|---|---|---|---|
| WQE 创建/提交 | 原生、独立 Task、Pair Jetty | 无 WQE；对象/包 metadata | 当前创建 CPU 时间不计模拟时间；资源/顺序仍不同 |
| TA 分段 | 每 TA 1024B；由 WQE/TA 归属与 SSN 驱动 | 测试端直接切包，普通1024B | 当前该大小下一 TA 一 data packet；不能推广为所有尺寸 |
| 发起端协议 gate | 0ns / WQE | 无 | 当前无固定时间节省；未来正值需同粒度建模 |
| 发送队列/窗口 | Pair TP 源仲裁、TA/packet窗口、浅发送管线 | 每出口独立 generated FIFO，最多1024包 | 发送节奏、排队和公平性不同，不能只补定时器 |
| 线上头部 | WRITE/TP/网络/DL真实序列化 | 只有4B DL，bitmap等为PacketTag | wire bytes/序列化不同；信用按实际包长取整 |
| 网络队列/流控 | 原生 allocator/VOQ/egress/CBFC/link | 复用原生网络部分 | 机制在，但当前配置不一致，见下表 |
| 目标事务执行 | 0ns native+0ns app；每TA验证 | sink 收实际Payload | 当前固定服务延迟相同为0，但无原生事务身份/错误语义 |
| Transport ACK | 原生RTP ACK；与事务成功区分 | 无 RTP ACK | 回流控制报文/窗口释放不同 |
| Transaction Response | 执行后反向RTP返回 | 无 | 返向流量、相关状态与完成条件不同 |
| 接收 Ready | 目标执行+逐段范围完整+group依赖 | 测试对象收齐观测 | 接入时必须保留逐目标覆盖/前置条件 |
| 发送成功 | 经过验证的Response和Jetty完成前缀 | 无组事务成功接口 | 不能由交换机复制完成伪造成功 |
| 重传/拥塞控制 | 当前 EnableRetrans=false，UB_CC_ENABLED=false | 无事务重传/TP拥塞控制 | 不必为无故障固定配置实现当前未启用功能；CBFC仍必须在 |

PoC 入口/复制/sink：`N/src/unified-bus/model/ub-switch.cc:1964–2086`；目标集合由 rank→port 映射查找，不走原生单目的路由解析。PacketTag 不计入真实传输字节，这是既有 PoC 的理想化范围，不是实际 UB 组播 Header。

### 实际线上字节，而非只看 Payload

在当前普通 WRITE、CC关闭、无可选 userData 扩展的路径下，源码序列化给出：

| 报文 | 字节构成 | 总线速字节 |
|---|---|---:|
| WRITE 请求 | DL4 + UB IP-based6 + IPv4 20 + UDP8 + TP16 + BTAH8 + MAETAH16 + Payload | Payload + **78 B** |
| 事务 Response | 前述非TA头54 + ATAH8，零Payload | **62 B** |
| 普通 TPACK | 独立Transport响应路径，CC-off，无selective扩展 | **62 B** |
| PoC 数据包 | DL4 + Payload；其他信息在免费PacketTag | Payload + **4 B** |

所以1024B的原生WRITE TA请求为1102B，PoC为1028B。按当前160B cell向上取整，这两种数据包都消耗7 cells，并非本配置的数据包信用需求已不同；其他包长可能跨不同cell边界，原生额外ACK/Response也另占信用（`N/src/unified-bus/model/protocol/ub-cbfc.cc:227–237`）。PacketTag自身有28B的tag序列化方法，但这些字节不计入packet线上大小，不能把它当作已经收费的Header。事务Response还经过RTP数据路径、产生Transport ACK；CBFC控制帧又是另一个层次。这里不把ACK数量固定为某个每WQE常数，须按实际发送、响应、队列/确认规则统计。

序列化证据：

- `N/src/unified-bus/model/protocol/ub-transport.cc:955–980,1069–1163`：数据/事务响应构造与size计算；`:2065–2113`：独立Transport响应构造。
- `N/src/unified-bus/model/protocol/ub-ta-codec.cc:26–57,111–126`：userData不在时不加UDETAH；`ub-function.cc:168–197`：本WRITE的memoryAccess。
- `N/src/unified-bus/model/protocol/ub-header.cc:454–456,613–615,1051–1053,1524–1526,2484–2486,2817–2819`：DL/IP-based/TP/BTAH/MAETAH/ATAH大小；相应常量在`ub-header.h:288–289,967–968,1156–1157`。
- `N/src/internet/model/udp-header.cc:148–150`、`ipv4-header.cc:25–34,373–377`：UDP8与无options IPv4 20。
- `N/src/unified-bus/model/protocol/ub-congestion-control.h:115–122`：CC关闭选ACK_WITHOUT_CETPH；`ub-tag.h:11–29`与`ub-switch.cc:1988–1995`：PoC metadata和4B DL。

TA与TP分段是两个参数：当前Jetty TA为1024B，而`N/src/unified-bus/model/ub-datatype.h:39–40`的TP Payload MTU为4096B，因此本配置一TA恰好装一个请求data packet。4KiB Chunk需要4个TA，不是一个4KiB网络包；更改TA/MTU时必须重新计算，不能把本次一对一关系写死。

### 当前存在的配置差异

| 参数 | UltraEP 实际 | PoC 普通案例（pressure） |
|---|---:|---:|
| host/switch 端点数 | EP64+1 switch | 5端点+1 switch |
| 速率 / 单链路传播 | 100Gbps / 20ns | 相同 |
| switch input processing | 0ns | 10ns |
| VL | TP priority直接映射 **7** | **1** |
| 每 ingress VL reserve | 1MiB | 16KiB（2240B） |
| physical egress cap | 512KiB | 4096B（1040B） |
| 初始 CBFC cells | 6553 | 102（14） |
| CBFC cell | 160B | 160B |
| credit return grain data/control | 4 / 32 cells | 1 / 1 |
| 独立信用返回 threshold | 1024 cells | 1 |
| Packet-rate pacing / IFG | NONE / 0 | 继承相同 |
| allocator | SP默认，5ns | SP默认，5ns；另有DWRR独立测试 |

配置来源：`N/src/unified-bus/model/ub-switch.cc:59–84,210–218`（CBFC/SP/处理时延）、`ub-queue-manager.h:23–25`和`.cc:30–51`（入口空间）、`ub-port.cc:46–51,170–201,270–313`（出口/间隔/CBFC）；`P/experiments/ub-network-multicast-poc/network-poc.cc:86–112`。精确默认字段锚点见 source-anchor-checks.json。应用 priority=7：pair-layer.cc:215–218 → `ub-transport-channel-manager.cc:136–162` → `ub-transport.cc:1157–1163,1903`；PoC priority=1：ub-switch.cc:1975–1976,1993。

当前 CC=false 关闭拥塞控制行为，不关闭信用/窗口：`protocol/ub-caqm.cc:168–173`，`ub-transport.cc:225–268`，`ub-function` Jetty 窗口。RTP仍请求ACK（ub-transport.cc:1139）；不应把“禁用重传/CC”误写为“无可靠完成依赖/无流控”。

## 6. 两种接入方案

### 方案 A：受约束的轻量组播适配器（推荐先设计并验收）

推荐的是一个有逐目标状态和真实网络反馈的**失败关闭、无故障研究模式**，不是给当前 PacketTag PoC 随便补两个常数。

必须保留/明确决定：

1. **统一网络配置和非权重流量路径。** 复用同一EP64拓扑、VL/仲裁、队列、CBFC、带宽、传播与allocation参数；Dispatch/Combine继续走原生路径。本轮不改变它们。
2. **固定工作粒度与字节模型。** 保留1024B逻辑TA覆盖、4096BChunk和实际权重字节；明确组播数据头/bitmap/identity的线速成本，不能继续把Tag零成本隐去。网络内复制节省源端重复数据是处理变量，其他头部简化必须显式披露/控制。
3. **逐目标 completion。** 每个 operation/chunk/segment 保留目标身份、offset/length、exact-once 覆盖、Payload检查、成功/错误状态。receiver-ready按完整目标执行定义；源端group success必须等所有必要目标反馈抵达。接收失败/遗漏应非零失败，不能补成功。
4. **反馈必须占用真实返回网络。** 声明每个目标的反馈粒度、真实字节、ACK/Response的关系与何时释放窗口；通过原生返回队列/链路发送，不能用固定RTT或本地回调代替。要比较现有RTP基线，就必须控制其Transport ACK和Response造成的返向负载。若采用合并反馈，它是额外协议处理变量，须独立报告，不能声称只测复制收益。
5. **保留有界注入与发送节奏。** 原生每TP浅活跃发送深度2、packet/TA outstanding限额1000、每Jetty TA上限512，与PoC每出口1024包FIFO不同。适配器要明确组→目标的资源/窗口映射，并实现有限背压/重试提交，不能一次性灌入全部专家权重或无限队列。一个18MiB Expert仅数据已含18,432个1024B单元，超过现有测试注入FIFO。
6. **可配置延迟保留，但当前取0。** dispatch按operation一次、target按完整TA一次；不凭空增加一个原native没有的CPU串行服务模型。未来模型变更应同时作用对照。
7. **应用依赖保持一致。** target覆盖推进weight/relay ready；group-sender completion、drain单独验收。不能把“收到所有反馈后再启动计算”混入当前依赖图。

建议需要触及的位置（**仅设计，本轮未改**）：

- `P/experiments/pair-jetty/pair-layer.cc`、`online-validation.inc`：增加显式权重传输策略接口、逐目标状态、同口径验证与summary，不改Planner/Compute。
- 独立应用层 multicast adapter / completion tracker：operation与target维度、有限注入状态、feedback收发。
- `N/src/unified-bus/model/ub-switch.{h,cc}`、`ub-tag.h`：让PoC入口可表达一致VL/packet metadata与受控线速头部，并提供合法反馈/接收接口；必要时独立header类。保留现有分支信用归属。
- 原生`ub-port`/`ub-link`/`ub-queue-manager`/allocator 的带宽、排队与信用算法应直接复用，不复制实现或改变单播。

**关键验收门槛：**先做单目标退化对照，让轻量路径在同输入下对齐原生单播的字节、分段、反馈事件、窗口开闭、receiver-ready及sender-complete；再做多目标。若不能对齐或明确量化差异，该模式只能标为近似/理想化组播研究，不能拿裸PoC数据宣称与原生Direct/Chunk严格公平。

发送上限的源码：`N/src/unified-bus/model/protocol/ub-function.cc:1020–1034`与`.h:345–348`（Jetty512）；`ub-transport.cc:259–273,2557–2599`（TP1000/1000及浅活跃发送深度2，常量在:39）。这些不是固定CPU延迟。ACK/CNP的优先级及对窗口检查的豁免在`:856–888,2760–2793`。新方案不能仅用一个限速timer替代其因果反馈。

### 方案 B：原生多目标 WQE / TA

优势是更容易把目标错误、事务Response关联、WQE完成纳入原生统一接口。成本是远超加一个目标bitmap：当前WQE、Jetty、TP与Response关联都按单远端设计（见前轮 [TRANSPORT_JETTY_AUDIT.md](../ub-multicast-feasibility/TRANSPORT_JETTY_AUDIT.md)）。需为每个目标明确序号/窗口与完成状态，避免把B的Response用于C；共享Jetty连续前缀、取消/失败清理也必须重新验证。

预计涉及（仅候选，不预先断言全部必须改）：

- `protocol/ub-function.{h,cc}` / WQE、Jetty admission、完成与取消；
- `protocol/ub-transaction.{h,cc}`、事务规则/关联身份、逐目标响应聚合；
- `protocol/ub-transport.{h,cc}`、TA codec/header、TP管理中的endpoint/PSN/SSN状态；
- `ub-switch.{h,cc}` 与组播header/metadata，将原生data packet映射为多个有效目标上下文；
- 应用接口与在线验证器。

如果要求丢包、重传、目标失败和取消后继续服务，则还涉及`ub-retrans`/状态清理；本轮设计不声称现有单播重传可自动变成多目标重传。可以保留原有单播路径并新增group operation，但不能靠把单播success通知复制N次完成设计。

### 成本与公平性判断

| 维度 | A 轻量适配 | B 原生多目标 |
|---|---|---|
| 适配当前单交换机、无故障性能研究 | 合适，前提是补齐并验证上述网络/反馈/窗口合同 | 可用，但范围更大 |
| 固定协议时延 | 可复用同配置；当前端点固定值为0 | 原生继承，不产生额外“天然真实”硬件时延 |
| 协议流量与发送节奏 | 必须显式实现/校准，不能只加timer | 更利于复用，但多目标序号/资源仍需设计 |
| 完成/错误语义 | 有界、逐目标、fail-closed，不能声称完整可靠UB | 更完整，但须大量新的原生正确性回归 |
| 开发风险 | 中等，主要是模型遗漏与资源调度差异 | 高，触及单播假设及完成/生命周期 |
| 本轮推荐 | **先A的单目标等价验证和合同设计** | 若A必须重造RTP才能匹配，或研究目标转向可靠协议，再转B |

现有PoC还绕过正常拥塞事件hooks（`N/src/unified-bus/model/ub-switch.cc:503–525,1895–1932,2061–2085`），所以后续若开启CC必须重审，不能认为它已继承全部拥塞语义。

暂可不实现：多交换机路由树、丢包重传/成员故障恢复（仅在明确无丢包无故障且检测异常即失败的研究范围）、通用SEND/READ/Atomic、完整GroupJetty硬件接口、实际控制面安装机制。动态组配置和metadata成本若暂设理想值必须单独标注，不能当成已测UB硬件能力。

## 7. 本轮验证与边界

- 27个历史成功案例的配置与命令逐项核验；未重新跑256或任何大规模案例。
- 生成器→runtime→文本输入→原生对象的取值链完整，不只引用默认值。
- 来源锚点检查与保护源码前后字节核验；报告中的方案均未实施。
- 公开只含文档、标量配置证据、源码锚点和验证摘要；不含原始Routing/请求/逐Token映射/Payload。
- 不从本审计给出新的组播Layer Latency、Speedup或“协议开销占比”。固定0ns也不代表真实硬件处理零开销。
- 未运行native回归；本轮没有运行源码改动，因此不会将上轮48/49的结果冒充本轮测试。

**最终回答：不必为了当前为零的端点固定延迟而先扩展完整功能层/事务层；但要与现有原生 Direct/Chunk 公平对照，必须补齐或明确控制网络字节、反馈、发送窗口/仲裁和完成依赖。推荐先做范围受控的A，并以单目标等价性为进入性能比较的门槛。裸network-only PoC加两个延迟常数不满足这个门槛。**

## 参考依据

- 上轮网络PoC报告与源码、重建补丁：[ub-network-multicast-poc](../ub-network-multicast-poc/REPORT.md)。
- 前轮单目标身份与可靠性审计：[ub-multicast-feasibility](../ub-multicast-feasibility/REPORT.md)。
- 当前应用与输入生成器：`experiments/pair-jetty`、`qwen-real-minimal`、`qwen-real-batch-scaling`。
- 原生`doc/adr/0025-single-target-execution-delay.md:24–45`解释target延迟为一次非独占管线延迟；本报告同时核对消费源码。
- 所有设计建议是拟议扩展，非UB规范或真实NPU硬件支持声明。
