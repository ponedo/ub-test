# Multicast WRITE v2 单目标丢包与原生重传验证

## 结论与适用范围

在原 dot 云主机完成原生源码审计、最小适配及八个有界场景。结论：本次单交换机、GBN、后链路 TP 入口丢失场景下，首次数据可以使用共享 Payload v2 Envelope，随后由原生 TP 触发普通单播 WRITE 重传。没有新增组播 ACK、组播 PSN、重传定时器或可靠传输状态机。

这不是完整硬件/任意丢包可靠性证明。故障点在交换机拆包并经过下行物理链路之后、接收端正常信用处理之后、TP 处理之前。重复包实验是重复向 TP 交付同一个实际收到的包，不是额外复制一帧上链路。重传本身完整经过真实 A→Switch→B 队列与链路。未验证源 Envelope 在 A→Switch 丢失、链路信用帧损坏、非尾部丢包、多个并发组、Selective/CC 开启、多交换机或硬件实现。

原生重试耗尽只有断言终止，没有完整的 WQE 失败通知与安全回收语义。因此：原生成功恢复路径得到实证；长期失败的生产式处理仍是 UNSUPPORTED，不能声称已具备完整权重分发服务的失败处理能力。

## 基线与源码

项目父版本：3587954cccecaaf59e9578c5645c745bf78583e5。原生基线和重构方法见 [AUDIT.md](AUDIT.md)、[README.md](README.md)。本轮从原主机保留的 accepted native 重建，核验108项原生基线、108项历史项目文件，以及8项 v2 变更源码哈希。原 v1/v2 交付文件不变，新增文件只在本目录。

[AUDIT.md](AUDIT.md) 引用具体路径、函数和行号，覆盖 descriptor/PSN/window、ACK 推进、RTO/NAK/SACK、原生重排队列、TA/WQE 完成以及 CBFC 的边界。原生 EnableRetrans 默认关闭，但已有 GBN 和 Selective 重传代码。原 v2 安装边界明确拒绝启用重传，本次新适配器仅解除受支持 GBN 路径的限制并分离调度。

[adapter-retrans.h](adapter-retrans.h) 继承原 v2 编码/Tag 兼容关联，控制包优先，其次单个原生 pending GBN retry，最后全员 ready 的首次发送。调用原生 GetNextPacket 取得重传，sndNxt 不变，绝不重新合包。保留原生未确认工作时让外层队列仍可被调度器发现；唤醒仍由原生 RTO→TriggerTransportTransmit 完成，没有新增轮询/重传计时器。

[transport-fault-seam.patch](patches/transport-fault-seam.patch) 只增加默认空的有界测试回调。没有修改原生 ACK/RTO/发送窗口/接收去重/完成算法。Wire Envelope v2 格式没有变化。原生 FlowTag、CorrelationTag、ExplicitPayloadTag 的恢复仍只是 ns-3-ub 兼容步骤，不是组播线上协议字段；发送端到交换机的仿真元数据关联仍不等于免费硬件能力。本轮没有扩大到移除 Tag 依赖。

## 配置与结果

单个源 A=0、目标 B/C/D=1/2/3、交换机=5；沿用旧夹具一个空闲节点/端口，不产生额外流量。12KiB/目标、1024B TA、12个请求 PSN（0–11）、100Gbps、20ns 链路。CBFC 开启，CC 与既有 v2 一样关闭。双向原生 GBN 开启、fast retrans 关闭，使用已有静态5µs RTO与4次预算。尾部 PSN11 损失仅留一个未确认分段，不能由此声称 GBN 是选择性重传。

以下时间为绝对仿真时间，提交在0.1µs；不是完整 MoE Layer 延迟。

| 场景 | 故障及原生行为 | A→B WRITE重传 | 组完成时间µs | 结果 |
|---|---|---:|---:|---|
| normal | 无故障，12个首次 Envelope | 0 | 1.673 | 成功 |
| data-once | B PSN11 丢1次，原生RTO重传 | 1 | 6.8382 | 成功 |
| duplicate | B PSN11 重复TP交付1次 | 0 | 1.678 | 成功，无重复执行/完成 |
| ack-once | B最后TPACK丢1次，收到TAACK后完成；随后重传清理TP | 1 | 1.673 | 成功且最终TP排空 |
| response-once | B最后TAACK丢1次，B→A原生反向重传 | 0（反向1） | 6.6818 | 成功 |
| persistent-bounded | 同一B分段持续丢，14µs受控停止 | 2 | 无 | BOUNDED_INCOMPLETE |
| persistent-exhaust | 初发+3次重传均丢 | 3 | 无 | 21.54696µs原生断言终止 |
| retrans-disabled | 同样单次丢包但关闭原生重传 | 0 | 无 | 14µs停止，恢复不支持 |

持续丢包两种实验中 C、D 均成功，状态未被撤销，B和组不报告成功。原生耗尽进程返回−6、断言位置 ub-retrans.cc:1216，没有触发宿主资源保护；它不是“优雅失败回调”。14µs快照中 B 的 UNA=11/NXT=12，仅1个未确认 segment、1个descriptor、1个原生timer；这些是仍未完成的协议状态，不冒充已回收。关闭重传对照则同样未完成，但没有descriptor/timer。

## 实际重传路径证据

[data-once packets.csv](results/cases/data-once/packets.csv) 记录同一原生身份：TP 101→201、PSN11、SSN11、WRITE、1024B Payload，首次与重传Payload校验一致。该重传没有 Envelope：

- 6.55196µs：原生 retry 被 A 队列取得、入真实出口、物理发送。
- 6.66012µs：Switch 入口收到。
- 6.66512µs：Switch 至 B 出口入队并物理发送。
- 6.77328µs：B 物理收到，经原生 TP/TA 完成实际 Payload。
- 6.8332µs：A 收到 TPACK，原生窗口前进。
- 6.8382µs：A 收到 TAACK，B WQE 和整组完成。

C、D 各只收到12个原始数据分段，没有不必要重传。Packet UID 可能由 Payload fragment 复用，验证器不是仅凭 UID 匹配，而是联合 TP/PSN/SSN/类型/任务/Payload及重传时间区间，逐跳核验。

[response-once packets.csv](results/cases/response-once/packets.csv) 则显示 B 在6.62688µs通过原生出口重传TAACK，经过 Switch 后6.6818µs到 A。A侧 WRITE重传计数为0不能误读成“没有重传”。

## 完成与排空的关键区别

[ack-once windows.csv](results/cases/ack-once/windows.csv) 显示：TAACK到达后 B WQE在1.663µs、组在1.673µs完成；此刻请求TP仍有PSN11未确认及descriptor/timer。原生RTO触发后在6.55196µs实际重传，B去重后重发TPACK，A在6.8332µs排空请求TP。

这符合原生事务响应驱动的 WRITE 完成语义，不是凭“目标已收到数据”伪造发送完成。但“WQE成功”不能等同“TP可销毁/全部资源已排空”。后续集成必须保留正常原生TP生命周期，不能在组成功回调立即销毁TP或假设没有后续包。本轮没有连续组复用/提前销毁的验证。

## 正确性、队列与资源

五个成功场景的 B/C/D 最终12KiB Payload均逐字节与源数据一致；每目标仅12次TA执行、1次WQE完成，整组仅完成一次。重复包通过原生同PSN去重，不重复执行目标事务。请求与反向响应 descriptors/timers最终归零，TP UNA=NXT=12、TA UNA=NXT=12；关联表、缓存、VOQ/出口队列归零，未放宽检查。

CBFC使用真实上下行包长，所有10个端口逐对验证 consumed=peer.returned=restored+peer.pending。默认阈值批量返还会留下 pending credit，例如 data-once 的 B 仍有11 cells待返还；因此不是“全部信用已归还/自由信用重置”。本轮故障微基准 blocked_queries=0，不声称施加了背压压力；旧无丢包压力回归另行检验。

[verify.py](verify.py) 检查故障准确身份、逐跳物理重传、最终实际Payload、PSN/SSN、重复/提前完成、完整端口集合与信用账本、原生最终状态及耗尽真实进程结果。[test-verifier.py](test-verifier.py) 以实际 data-once 证据做1个有效输入和15个错误证据测试，全部按预期接收/拒绝，防止只凭PASS下结论。关闭Python断言的运行被拒绝。

## 回归与执行状态

本轮完成：

- v1/v2原14个正向场景、Codec/关联测试和预期反馈/损坏负例通过。14个场景的模拟完成时刻、包/字节数、压力计数等与上一版逐项完全一致，见 [v2-parity.json](results/v2-parity.json)。旧v2压力场景369次CBFC阻塞，DWRR压力684次，原生窗口2场景仍通过。
- 历史原生单播/共享队列7组精确对比通过；Full Multicast5正例和3预期拒绝通过；交换机复制PoC原有矩阵、并发组播9例，以及64-assignment小型no-balancing/direct/two-stage/chunk旧回归通过。没有新增MoE集成或跑大模型。
- 最终加强的证据验证器对八个场景重验通过；1有效/15错误证据测试通过；优化Python被拒绝。补丁在原v2两个文件上独立重放后逐字节一致。
- 本轮没有重跑原生完整49套件，不把上一版48/49结果算作本轮结果。新增native变化仅为默认空测试注入接口，旧行为由上述完整计划内回归覆盖；原ACK/RTO算法文件未修改。

原生库重建2339.13秒，峰值进程RSS857684KiB，无保护停止。初次夹具编译因继承枚举缺少namespace限定失败，修正后通过，失败记录保留。后续历史pair-layer编译峰值约1.24GiB。所有仿真与编译均顺序运行，沿用3600s/阶段、6GiB进程树RSS、7GiB地址空间及磁盘/可用内存保护。公开结果保留必要的Events和摘要，不上传原始Payload、二进制、大型Debug或宿主完整信息。

## 已知限制和最小后续修改范围

- 原生重试耗尽需未来另行授权设计失败传播、取消与终态资源清理；当前最小复现是 persistent-exhaust。没有擅自修改核心语义。
- 物理链路信用丢失、源Envelope丢失及元数据关联回收不在本轮已验证范围。当前是后链路TP入口丢失实验。
- 仅尾部分段单目标、单组、GBN、无CC。其他位置丢包可能重传更多未确认分段；不能外推成任意丢包只重传一个包。
- 仿真共享关联、Tag兼容和硬件成本限制沿用v2。没有接入完整MoE、改变Planner/Chunk或扩展拓扑。

## Knowledge Sources

固定原生源码及 AGENTS.md、doc/agents/implementation-workflow.md、README.md、QUICK_START.md、队列背压与观测知识卡；已验收v2报告与原生补丁；本轮实际包、状态和资源证据。无外部第三方结论替代实验。
