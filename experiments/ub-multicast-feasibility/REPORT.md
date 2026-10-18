# ns-3-ub 网络原生动态组播可实现性审计

## 结论与决策

**可以把现有交换机、输出队列和链路模型作为网络复制 PoC 的基础，但当前被审计路径没有现成的一对多 UB 事务/可靠组播支持。** 交换机复制需要新增分支管理和准确的缓存/信用归属；可靠多目标完成需要单独设计，不能只调用 `Packet::Copy()`。

- **已实现：** 单输出端口路由、VOQ、受容量限制的物理出口队列、流控感知仲裁、按实际 Packet 字节数计算的链路序列化，以及点到点传播。依据：`src/unified-bus/model/ub-switch.cc:973–1005` (`ForwardDataPacket`)、`ub-switch-allocator.cc:652–710` (`UbRoundRobinAllocator::AllocateNextPacket`)、`ub-port.cc:59–110,790–842`、`ub-link.cc:174–203`。完整路径见 [网络审计](NETWORK_SWITCH_AUDIT.md)。
- **结构上可扩展，尚未实现/验证：** 在交换机产生多个独立 Packet 实例，然后每个分支走正常 VOQ→仲裁→出口→链路流程。不能绕过出口资源；不能把 CPU 的 COW 复制开销当成硬件复制引擎时间。依据：`src/network/model/packet.cc:120–150`、`packet.h:440–449`，以及上述单播路径。
- **核心风险：** 一次入站收到一个数据包，若直接三次调用原有发送流程，可能产生三次上游信用归还；必须先定义一个入站数据包、多分支存储、每出口独立下游信用的归属规则。依据：`ub-queue-manager.cc:185–261`、`protocol/ub-cbfc.cc:147–166`、`ub-switch-allocator.cc:652–710`。这是网络复制阶段的正确性问题，尚未运行 PoC 验证。
- **可靠性不能直接复用为组语义：** 现有目的地址、对端 TP、事务响应和 WQE 完成状态没有多接收者维度。B 的响应不能代表 C、D 成功。依据：`ub-transport-channel-manager.cc:238–299` (`ResolveInboundTp`)、`protocol/ub-function.cc:1058–1072,1290–1318`、`protocol/ub-transaction.h:618–645`、`protocol/ub-transaction.cc:1859–1918,2114–2177`；详见 [事务与可靠性审计](TRANSPORT_JETTY_AUDIT.md)。

**建议：网络复制 PoC 有条件 Go；直接作为可靠 Expert 权重组播投入性能实验 No-Go。** 先通过缓存、信用、队列、逐分支数据完整性测试，再建立独立的多目标可靠操作路径和完成语义。保留现有单播路径可行，但协议扩展绝不是配置开关或只增加一个 Group ID。此判断是工程方案，不是已实现功能。

## 审计版本与证据边界

- UltraEP-on-UB 外层项目基线：`6a870170b0519267efff6a73a6be38ee575280ae`。
- ns-3-ub 原生 Git HEAD/base：`d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`。
- 现有工作树由该基线及已验收反向索引/完成修复补丁恢复；目标源码版本记录为 `2fde39d02920e639f5b200d0c5262a517326deb8`。不能仅凭 HEAD 标识修改后的文件。
- `evidence/provenance.json` 记录恢复来源、补丁 SHA256，以及已验收快照中的五个文件与当前字节的核对；完整扫描源文件的 SHA256、大小及已有修改清单仅保留在云主机私有证据中，本次公开交付不包含 before/after 两份广泛源码清单；公开的比较摘要记录核验范围及结果。
- 本轮只执行只读目录、文本、源码哈希和引用验证；没有构建/运行组播功能，没有修改原生协议或 UltraEP 模型。已有单播回归是后续开发需要运行的清单，不能写成本轮组播测试通过。
- 行号均以这份原生工作树为准；详细审计中的 `model/` 简写表示 `src/unified-bus/model/`。

## 交付导航

1. [网络、交换机、队列、信用和 Packet 复制](NETWORK_SWITCH_AUDIT.md)
2. [WQE / TA / Jetty / Transport / ACK / Response 与完成语义](TRANSPORT_JETTY_AUDIT.md)
3. [动态组方案 A/B/C、控制开销、网络 PoC 与可靠组播 PoC](DESIGN_OPTIONS.md)
4. [调用路径及拟议扩展边界](CALL_PATHS.md)
5. [修改面、风险与分阶段验收](CHANGE_SCOPE_AND_GATES.md)
6. [复现只读审计、来源校验及 UNKNOWN](README.md)

## 三类信息严格分开

| 类别 | 本轮可以得出的结论 |
|---|---|
| UB 规范 | 只有独立核验的规范条款可以支持规范结论；详见设计文档规范边界。没有条款依据的能力为 UNKNOWN。 |
| ns-3-ub 实现 | 本次具体路径为单目的操作、单输出选择。有限范围的词法搜索没有找到原生组播实现；它不能证明整个 UB 规范不允许组播。 |
| 拟议扩展 | 多分支网络复制、版本化动态组、独立多目标可靠状态、失败及清理。全部是设计，不是已有能力。 |

## 关键设计取舍

方案 A 的预配置组适合固定接收集合或有命中的组缓存；方案 B 的报文携带集合适合频繁变化的成员，但必须计入 bitmap/list 和版本等真实 Header 字节；方案 C 可以在 Planner 后安装组表，但配置、生效屏障、旧版本回收等成本必须在仿真依赖图中显式出现。详细比较包括兼容性、改动范围、控制开销、可靠性、多交换机扩展和单播隔离，见 DESIGN_OPTIONS.md。

EP64 的接收者 bitmap 本体是 8 字节，只是集合编码大小，不是完整组播 Header。地址、操作 ID、epoch、分段、目标执行上下文等字段不能省略为“免费标签”。`PacketTag` 不增加 `Packet::GetSize()`；仅用标签携带集合会遗漏链路、缓存和信用成本（`src/network/model/packet.h:849–852`、`packet.cc:257–265,949–953`、`src/unified-bus/model/ub-port.cc:790–842`）。如果未来使用零字节 metadata，应明确称为理想化网络复制 oracle。

可靠方案先用多个原生单播子 WQE + 逻辑父操作聚合建立正确性参照，然后再研究共享源端传输的多目标数据路径。前者不能宣称节省 A 的上行权重字节。所有目标的事务执行成功才能完成父操作；传输 ACK 和目标端执行 Response 不可混用。组内某个目标永久失败时必须有明确失败结果和其余状态清理，不能把失败成员从成功条件中静默删除。

本轮没有网络复制、可靠组播或 UltraEP 组播的性能数据，不给出速度提升预测。完成本审计后等待用户验收，下一阶段才决定是否实施。
