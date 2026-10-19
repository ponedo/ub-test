# 轻量 UB Multicast 适配器与单目标等价验证

## 结论与交付范围

实现了一条**复用原生 per-target WRITE/TA/TP 状态、共享物理发送 Payload**的轻量组播路径。没有新增 UB 标准 Group WQE，也没有复制一套 ACK/Response 算法。

先完成单目标交换机复制路径校准，再把**实际共享源队列**用于单目标重新校准：7 组 A/B 的完整线上字节、事件时间线、TP/Jetty 窗口快照、端口信用统计、实际 Payload 文件逐字节一致。之后才运行多目标；三目标、动态成员、出口竞争、窗口阻塞/恢复与 CBFC 背压均通过，重复/缺失/错误反馈按预期失败。

重要边界：初版同时只接收一个 group operation，可有多个 TA 在途；动态成员案例在前一组发送端完成后开始下一组。没有证明多组并发公平性、CC 开启、重传、MPI/RemoteLink 或 UltraEP 整体性能。不能把本实现称为 UB 标准原生组播。

基线公开 Commit：`696574dc4430836d75431493f738c54a2dd70f07`。原生基线为前轮 network PoC 重建源码，本地基线 HEAD `cc3b9e29d2f59fa9cb5b94217bab989d44dc0ae7`。本轮原生实现与收尾的本地 Commit、补丁和限定源码哈希见 [source-provenance.json](source-provenance.json)。重建方法见 [README.md](README.md)，增量原生改动见 [patches/lightweight-adapter.patch](patches/lightweight-adapter.patch)。

## 1. 实现结构

### 原生复用与新增部分

| 内容 | 实现方式 |
|---|---|
| WQE/TA、请求分段、TP/Jetty窗口、SSN/PSN | 每个目标有独立原生 child WQE/TP/Jetty，直接调用原实现 |
| Packet 构造与每目标关联身份 | 原生 `GetNextPacket` 产生，保留该目标自己的 native header、Flow/Correlation/ExplicitPayload 信息 |
| 共享数据发起 | `adapter.h::SharedSource` 一个有界仲裁入口；所有活跃 child 的下个 data packet 可发送后，在同一 allocator commit 中取出并合并 |
| 源端物理 Payload | 每个 envelope 只包含一份 Payload；各 child 的实际 Payload 必须一致 |
| 网络复制 | `UbSwitch::HandleNetworkPacket → CompleteNetworkProcessing` 的父包/分支 VOQ 路径 |
| 网络队列、仲裁、CBFC、链路 | 复用原生；各输出分支占用真实出口队列和信用 |
| 目标端 | 从真实收到的 envelope 字节重建自己的原生 packet，验证 `ResolveInboundTp` 精确身份后交给原生 `RecvDataPacket` |
| Transport ACK / Transaction Response | 完全由原生处理并通过反向真实网络返回；源端通过原生 `SwitchHandlePacket` 处理 |
| 组完成 | 原生 child 发送端成功回调逐目标汇总；所有成员成功且数据全部提交才产生 `group_complete` |

SharedSource使用`UbIngressQueue`的本地完整报文队列类别（枚举`CTP`）接入allocator；这不是启用CTP协议服务，内部child仍是原生RTP WRITE。

原生代码只改动 `ub-switch.cc`、`ub-tag.h`，增加校准/封装两种显式 discriminator，允许该路径使用一致 VL，并保持正确的信用/目标回调顺序。普通未标记单播及旧 raw PoC 路径保留。共享队列、envelope编解码、完成汇总与测试位于本实验目录，不修改 Planner、Compute 或现有 UltraEP 策略。

### 调用路径

```
Source：每目标原生 child WRITE → 原生 TA admission / window
   → SharedSource（原生 allocator 的一个 ingress slot）
       控制报文：原样发出
       数据：所有 child 可发送 → 原生 GetNextPacket → 一份 Payload + 付费元数据
   → 原生 egress / CBFC / UbPort / UbLink
Switch：一份父包 → 每目标 VOQ branch → 原生仲裁 / egress / CBFC / link
Target：完整 envelope 信用处理一次 → 验证/解码真实字节
   → ResolveInboundTp → 原生 RecvDataPacket → 原生目标 executor
   → 实际 Payload / Offset / TA 与 Chunk 覆盖验证
   → 原生 Transport ACK / Transaction Response → 真实返回链路
Source：原生接收/完成 → child成功 → 全成员 group_complete
```

没有通过固定 RTT、假的延迟事件或本地 target 回调直接制造发送端成功。

## 2. 单目标等价门槛

候选并非简单转调用完整原单播路径：真实 packet 在交换机进入父包/分支复制路径，测试断言 admitted/branches/released 均非零且一一对应，资源最终清零。端点仍复用原生 WRITE 以避免另写近似协议。

只包含一个目标时，现有原生目的地址已足以表达成员集合，不加冗余 envelope。local Tag 只选择校准路径，不改变线上字节。源端共享队列、窗口与控制报文逻辑仍实际执行。

目标端必须在处理入站 CBFC 之前移除 singleton selection Tag，再进入正常原生收包；这样不会重复恢复 piggyback credit 或重复返还 ingress credit。交换机校准路径还保留原生 route resolution、traversal trace 和 enqueue/dequeue hooks。

7 组实际共享队列对照：

| 场景 | 配置重点 | 结果 |
|---|---|---|
| small | 64B / 1 WQE | 完整字节及事件一致 |
| multi-ta | 4096B / 4 TA | 一致 |
| concurrent | 3个并发WQE，每个16KiB，TA1024B | 一致 |
| fragmented-ta | TA8192B，大于TP MTU4096B | 一致 |
| window | TP/TA测试窗口2，8个WQE，目标延迟1000ns | 一致 |
| backpressure | 有限小队列/信用，实际发生CBFC阻塞 | 一致 |
| delayed-switch | 入口处理10ns，验证父包延迟保留 | 一致 |

正常案例保持原生固定值：100Gbps、20ns/链路、VL7、SP、allocation5ns、入口处理0ns、CBFC默认、IFG0、PacketRateControl NONE、CC/RTO关闭。变化案例的两臂使用相同配置，不把某臂资源调大。

每组比较 `wire.csv`（含实际 wire hex）、`events.csv`（含 TP/TA窗口）、`ports.csv` 和所有实际接收 Payload 文件，采用真实文件 bytes equality；FNV 只是附带字段，不是字节相等的唯一证据。见 [results/singleton-parity.json](results/singleton-parity.json)。公开保留64B案例的完整A/B证据，其余完整数据保留私有且可复现。

示例：64B在100ns提交；receiver-ready为172.720ns，sender-complete为237.640ns，两臂完全相同。所有时间是实际ns-3事件；10ms仿真watchdog不作为完成时间。

## 3. 多目标协议与线上字节

本适配器保守地把每个目标需要的头部及原生关联信息都编码入实际 envelope，不使用免费 bitmap 冒充协议头。

格式（实验自定义、非 UB 标准）：

- 外层 DL：4B。
- envelope 固定字段：28B，包含 magic/version标识、group ID、sequence、Payload length、成员数、64-bit bitmap。
- 每个目标：rank与prefix length共8B；原生WRITE header prefix78B；FlowTag8B、CorrelationTag42B、ExplicitPayload marker1B。共 **137B/目标**。
- Payload 只出现一次。

所以物理大小为 **32 + 137 × 目标数 + Payload bytes**。三个目标、1024B Payload为 **1467B**；两个目标为1330B。完整 envelope 在各输出分支仍保留，不在交换机免费压缩成员记录。

这是保守的模型格式，不代表真实硬件所需最小Header。Correlation等字段原生本来使用本地Tag，本方案把它们明确收费，以便目标从收到的字节重建自己的上下文。局部父包引用/分支ownership Tag仍是仿真管理状态，不描述为标准wire header。

目标 native decoder只看到重建的原生packet，其实际Flow/Correlation属于该目标，而非全部复制第一个目标身份。Native Transport ACK、Response及Response的Transport ACK仍沿各自真实返回路径传输。没有免费ACK聚合。

## 4. 有界发送、完成和信用

### 发送窗口

SharedSource安装在专用、尚未发起work的child TPs上；拒绝重复TP/rank、不一致端口/VL、非静止上下文及启用重传/CC的配置。没有动态接管已在仲裁或egress中的流。

`IsEmpty`按所有child是否有work判断，`IsLimited`才做all-ready barrier。先服务原生CNP/ACK；data只有在每个child的原生窗口均允许、下一packet大小匹配时才取出。实际取包发生在allocator commit，保持原生PSN/segment推进；不提前弹包再以timer伪造发送。

当前多目标仅一个活跃group、每child一个WRITE，因而各child按同一逻辑范围推进；取包后的identity/Payload断言是fail-closed检查，未实现回滚。其他请求类型、不同Payload或多组任意交错不能悄悄继续。

SharedSource占用一个RR ingress slot，而不是每child各占一个；all-ready barrier可能等待最慢成员窗口。这是组播资源策略的一部分，必须在后续性能研究中保留说明。已经进入交换机的不同分支仍独立排队。

专门的TP窗口案例把 packet window设为1，但仍保留TA上限512、TP segment上限1000，避免“没有待发packet”被误当成真正的TP窗口阻塞。实测 **154次 window-limited检查**，TP在途峰值1，TA在途峰值3，随后恢复并最终清零。检查次数不等于阻塞时间或丢包数。

### 完成语义

- receiver-ready：每个目标的所有TA执行且Payload/range覆盖完整。
- chunk-ready：每个目标对应4KiB范围覆盖完整，不早于其全部TA完成。
- sender child-complete：原生WRITE Response验证和原生Jetty完成条件满足。
- group-complete：所有声明成员的child成功，exact-once；未选中目标不得计入。
- 最终检查所有native child及背景流idle、TP状态可销毁、队列和父包/分支清零。

### 信用与buffer

源端只为一份真实envelope消耗一次source信用；switch父包只在最后分支dequeue时释放一次上游信用。每分支独立消耗下游信用。目标先为**整个收到的envelope**处理/返还信用，再交给原生TP处理重建packet，不再次调用原生switch sink的DL信用流程。

每端口验证 consumed cells = 实际发送非credit-frame字节按160B向上取整；returned cells = 实际收到数据frame字节按相同规则；initial − consumed + restored = free。对低于原生return阈值的pending credit如实记录，不将其强行刷成全部initial来掩盖差异。物理egress、ingress peaks均不超过配置，所有数据队列最终为空。

## 5. 实际多目标结果

时间均为真实事件。源接口100ns提交，以下第一组时间用绝对模拟时刻展示；group耗时另减submit。

| 案例 | Payload只发送一份 | source data wire bytes | 物理分支 | 结果 |
|---|---:|---:|---:|---|
| 三目标16KiB | 16,384B | 23,472B | 48 | PASS |
| 动态两组各8KiB：{B,C}→{C,D} | 16,384B合计 | 21,280B | 32 | PASS |
| B出口竞争，组16KiB | 16,384B | 23,472B | 48 | PASS |
| TP window=1，组32KiB | 32,768B | 46,944B | 96 | PASS |
| 小队列/CBFC压力，组16KiB | 16,384B | 23,472B | 48 | PASS |

三目标普通案例：

- B/C/D各收到16,384B，逐字节与源匹配。
- 三者receiver-ready均为 **2.315080µs**。
- 三个native child sender-complete分别为2.390000、2.395000、2.400000µs。
- group-complete为 **2.400000µs**，从100ns提交算耗时 **2.300000µs**。
- 16个source envelopes、48个switch branches、48个事务Response反馈。Transport ACK和信用帧另行计数，不与事务Response混为一谈。

竞争案例中，C/D receiver-ready为2.295080µs，B为3.679640µs，组完成3.744560µs。证明实际分支队列竞争；没有人为给目标安排固定收齐时间。

压力案例：入口/egress均1600B，初始10cells、return grain1、threshold1，三目标1467B envelope可装入。记录 **582次CBFC blocked查询**；最终完成且守恒，未扩大容量或禁用流控。

资源与各目标时刻详见结果CSV/JSON。典型单次测试宿主机wall约0.25s，主要含资源轮询粒度；实际CPU另列。不能把这个host wall与微秒级模拟完成时间混淆。

## 6. 故障注入与独立验证

在实际source receive边界，先完成真实网络传送，再注入：

- duplicate：把同一收到的Response packet复制，重新进入完整receive/decoder/validator路径两次；第二次被重复身份检查拒绝。
- missing：丢弃一份已到达的Response，保留其他目标实际进度；最终watchdog检查发现组未完成，返回非零，未产生group success。
- wrong：修改实际packet的TP source identity字节，重新进入同一receive/decoder路径；成员身份检查拒绝。

三例都是 **EXPECTED_REJECTION**，不能写成正常仿真PASS。duplicate/wrong证明适配器入站校验拒绝，不冒充原生错误包恢复/去重算法测试。没有实现丢包重传或成员故障恢复。

独立 `verify-multi.py` 不调用adapter代码：读取实际Payload、应用事件、wire与window/credit记录，检查逐目标TA/Chunk范围、Top-level group完成、实际反馈数量、source单份数据、付费metadata大小、每条物理链路的序列化+20ns传播、窗口上限与回收。另以5种修改后的证据检验验证器：Payload损坏、提前group完成、遗漏反馈、错误线上大小、提前chunk-ready。

## 7. 回归与源码范围

- 旧 network-only PoC：13个正向案例和4个预期拒绝通过；相对上轮已验收证据，**118个输出文件逐字节一致**（含targets/ports/summary/arbitration及实际Payload），见network-parity.json。
- 原生QUICK：**48/49 suite通过**。`unified-bus-examples`仍在原有dependency-visibility案例失败：官方tools的`parse_trace.py`缺失，task timing CSV不可用；基线与候选均缺该文件，前轮已有实际基线复现，本轮错误断言相同。未伪造49/49，失败suite后续子例不计PASS。
- 旧应用四策略No Balancing、Direct、Two-Stage、Chunk：基线与候选分别重新编译、运行，同输入的所有simulation summary字段一致，仅排除host verification_wall_ns；独立postflight通过。
- 独立验证器5种证据破坏全部检出。
- 既有347份保护源码/配置中，345份不变，仅预期的`ub-switch.cc`、`ub-tag.h`改变；Planner、原生ACK/Response/Transaction实现、已有应用未变。

完整状态见 [results/validation-summary.json](results/validation-summary.json)。宿主机资源表包含预期拒绝的非零returncode，不能把这三行FAIL当作正常成功，也不能隐藏它们。

测试期间始终顺序执行build/test，使用既有资源保护。没有运行真实Qwen性能扫描。Native层只做两处文件的opt-in扩展，没有改原有ACK/Response算法、WQE完成修复、网络带宽/拓扑或NPU Compute。

## 8. 未支持行为与模型限制

1. 本轮是单交换机、本地UbLink、无故障、CC/重传关闭的研究原型。不会自动宣称MPI/RemoteLink、动态销毁或可靠重传正确。
2. 同时只支持一个group operation，多个TA可在途；动态成员在前组成功之后改变，native端点长期保留。多group并发及共享源NPU的复杂调度未验收。
3. 多目标验证使用普通WRITE、1024B TA。单目标验证另覆盖8192B TA/TP分段，但不据此宣称多目标任意TA粒度已支持。
4. 每目标仍保留native child WQE/TP/Jetty，所以此版本优化物理发送Payload，不声称消除所有NIC状态或宿主机CPU工作。
5. 自定义metadata较保守，全部收费，不能当作真实UB组播Header格式或最优编码。控制面安装/真实硬件处理吞吐未建模。
6. 单目标精确等价证明公共退化路径；多目标的共享RR slot、all-ready barrier和额外metadata是明确的模型选择，不等于已证明对任意背景流量均等价。
7. 没有接入UltraEP Planner/Weight策略，也没有给出MoE Layer Speedup。
8. 错误注入以明确非零退出结束；未实现失败后继续复用同一适配器的取消/恢复状态机。超时案例不会生成成功summary。

源码、补丁、复现命令和小型证据随本目录交付。完成发布核验后停止，等待验收。
