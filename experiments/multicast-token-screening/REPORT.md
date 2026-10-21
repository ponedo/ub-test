# 256 Tokens 快速验证：Chunk Streaming 与 Multicast v2

## 结论

**仅运行的两个 N256 正式用例均 PASS，已复现 Multicast 比 Chunk 慢的性能反转。** Multicast 的 WeightDuration 为 **896.326667 µs**，Chunk 为 **691.082182 µs**，相差 **+205.244485 µs（+29.698998%，1.296990×）**。

这是每种策略各一次的确定性配对结果，不证明重复运行稳定性或全局最小 token 数。按本轮范围到此停止：未运行 N512、N1024、新 N2048，也未运行 No Balancing、Direct 或新的参数消融。下列时延是模拟时间，不是宿主机耗时或硬件测量。

| 证据 | Tokens | Replicas | 自然分组数 | Chunk Weight (µs) | MC Weight (µs) | MC / Chunk | MC − Chunk (µs) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 本轮新配对 | 256 | 44 | 21 | 691.082182 | 896.326667 | 1.296990 | +205.244485 |
| 已验收历史参考，未重跑 | 2048 | 53 | 未在此重列 | 552.893591 | 717.182855 | 1.297144 | +164.289264 |

N256 的 21 组 fanout 为 **1×3、2×15、3×2、5×1**；MC 实测 331,776 个 envelope、755,712 个原生展开分支，另有 55,296 个 singleton 原生包。两策略共享字节一致的 plan / assignments，未手工调整副本或 fanout。精确数据见 [results.csv](results.csv)；历史值见[原始 512-window 基线](../multicast-controlled-ablation/analysis/data/timing.csv)。

## 固定条件与输入

- Qwen3 serialized L37、EP64、128 experts / top-8；真实路由固定取既有请求顺序前 256 tokens（22 + 224 + 10），无打乱、复制、填充或合成分布。这是离线拼接，不是观测到的联合 serving batch；传输内容仍是验证用合成字节。
- 3136 Gbps 逻辑聚合端口、**20 ns 链路传播**、原始 **5 ns 仲裁服务**；Jetty TA window 512、原生 TP packet window 1000、Roofline 100 TFLOP/s / 2692 GB/s。每个副本仍传完整 18 MiB 专家权重，token 数减少不等于权重字节按比例缩小。
- 保留完整 Layer 和正确性检查，以 receiver-ready 的 `weights_end − weights_start` 为主指标。恢复并核验基线 `3521a64fd300938af3af4573a9793c4cde8d9649` 的 10,977 个应用 Git blobs 和 3,430 个 native 文件；因旧云快照没有匹配运行二进制，按已核验源码重建。4 项既有运行时/模型检查、26 项纯 harness 检查通过；两次正式运行期间源码、二进制、输入与 harness 身份不变。

方法见 [README](README.md)、[预注册分析](preregistered-analysis.md)及[恢复记录](restoration/)。

## 当前关键路径与反馈证据

两策略各只有一个末尾 receiver-ready 依赖：Chunk 是 **23→59，最后一个 4 KiB relay chunk**；MC 是 **22→59，完整 18 MiB 专家传输**。没有把旧 N2048 的源 3 / group 8 预设为关键路径，也没有搬用旧场景的服务下界。

| 实际关键源的交换机返回口 | TX busy (µs) | 仲裁 pending，排除 TX (µs) | 未覆盖 idle (µs) | 合计 Weight (µs) | TX 或仲裁覆盖 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Chunk：64/23 | 66.368734 | 608.541483 | 16.171965 | 691.082182 | 97.659907% |
| MC：64/22 | 28.317708 | 867.830735 | 0.178224 | 896.326667 | 99.980116% |

- 全局返回口按 ACK/response VOQ 驻留总和排名：Chunk 前三为 57、62、58；MC 为 22、4、36。Chunk 的最大排队热点并不是末尾关键源。MC 的实际关键返回口 22 则同时排名第一，接近全阶段持续服务，支持“反馈返回路径是重要约束”的解释，但不证明唯一因果机制。
- 仲裁请求服务均为 5 ns。关键源上行口的相位结束结果，Chunk 成功 / NoIngress / Rejected 为 **110,574 / 13,816 / 0**；MC 为 **108,045 / 64,454 / 715**。这些是事件 cohort，不是互斥墙钟分解；请求开始和结果结束可跨阶段边界。Rejected 是仲裁重新验证结果，不能当作重传或丢包。
- 同一物理前向口 64/59，两者均发送 18,432 个 weight 包；平均 weight VOQ 驻留为 **6.732580 / 6.692517 ns（Chunk / MC）**。因此当前差异不能直接套用旧场景“目标 59 前向队列显著恶化”的解释。其它同口控制及源/目标端口见 [critical-ports.csv](critical-ports.csv)。
- 全 Layer 按 opcode 精确扣除 token 后，返回权重反馈数为 **2Ow + Iw**：Chunk 源 23 的 Ow=36,864、Iw=18,432，合计 92,160；MC 源 22 的 Ow=92,160、Iw=0，合计 184,320。relay 的入站 Iw 不能漏算。它们是完整生命周期工作量，不是 Weight 阶段计数或时延下界；原生 class 0 识别 stage-2 weight 流量，class 1 是测得的 ACK/response 合并类；不能仅因事件落在 Weight 相位就把全部响应称为 weight-only，精确的 weight-only opcode 值来自上述全生命周期 token 扣除。[feedback.csv](feedback.csv)
- 两者 Jetty 最大占用均达到 512；Weight 阶段 full-window Jetty-time / 暴露 Jetty-time 分别为 **0.627271% / 17.976358%**，不是墙钟停顿比例。未使用直到固定 10 s 仿真停止的全观察期分母，避免完成后空闲时间稀释指标。 局部检查更明确：Chunk 的关键 relay 源 23→49/59 各自最大占用只有 15、满窗时间为零；MC 源 22 的五个 child 都达到 512，各自满窗累计 806.134–830.327 µs（各观察 896.327 µs）。这支持局部反馈/窗口压力，但没有重建逐 TAACK 释放周期，不能确定其唯一因果份额。

另一个与旧场景不同的细节：MC 关键源到最后 native dequeue 的 idle 为 30.248540 µs，低于 Chunk 的 66.946295 µs，不能沿用“MC 更多 idle 导致反转”的旧叙述。这些证据显示当前结果与反馈服务约束相容；没有新的干预实验，不能把 +205.244485 µs 唯一归因于窗口、无效回调、前向排队或某一机制。完整有界聚合见 [diagnostics.json](diagnostics.json)。

## 为什么 N256 Chunk 反而比历史 N2048 慢？

自然布局变了，而非把原有传输图缩成 1/8。旧末尾依赖为 36→17 与 50→27 两个完整专家传输；当前是 expert 45 的 relay 23→59，依赖源 22 向 23、32 的对应 chunk。44 个副本少于 53 个，并不保证新的关键路径更短。

以下比较各自真实关键源，从 weights_start 到该源最后一次 **native dequeue** 的互斥时间，末尾再加 dequeue→receiver-ready。它是不同自然关键资源间的精确记账，不是同端口受控干预。

| 时间项 (µs) | 历史 N2048：源 36 或 50 | 新 N256：源 23 | 新 − 旧 |
| --- | ---: | ---: | ---: |
| TX busy union | 164.167221 | 115.267125 | −48.900096 |
| 仲裁 pending，排除 TX | 388.672779 | 508.815171 | +120.142392 |
| 未覆盖 idle | 0.000000 | 66.946295 | +66.946295 |
| 最后 native dequeue→receiver-ready | 0.053591 | 0.053591 | 0.000000 |
| WeightDuration | 552.893591 | 691.082182 | **+138.188591** |

即更少的 TX busy 被更多仲裁等待和 idle 超过，新增时间位于最后 native dequeue 之前。末尾 53.591 ns 不是单独的物理链路时延。现有聚合不能把 66.946295 µs idle 唯一解释成 relay 依赖或 AllReady 等待，也不能把上表三项当作可独立回收的优化收益。历史依据为 [partitions.csv](../multicast-controlled-ablation/analysis/data/partitions.csv) / [critical.csv](../multicast-controlled-ablation/analysis/data/critical.csv)。

## 验证、宿主机成本与边界

完整 online payload/目标字节检查、graph/postflight、独立协议检查和 Roofline verifier 均 PASS；两策略最终 combine 校验一致。每例 2,722 个 Jetty、842,256 次 TA admission / accepted TAACK / SSN progress 精确对齐且排空，全部 128 条有向链路 TX/RX 包数和字节守恒，预期 WRITE 与反馈工作量相符。MC 的 envelope/branch、retry 与注入丢失检查也通过。

这为无额外 WRITE、无重试、无丢失提供强一致性证据，但没有导出的通用 Chunk drop counter，不能声称逐个潜在丢包事件均直接测量。全 65 节点聚合保留；非匹配 source/group selector 4294967294 只关闭选定 TA/RTT 细节，其零计数不用于证明全局相关性完整。

| N256 策略 | 完整 Layer 模拟时延 (µs) | Simulator wall (s) | CPU user+system (s) | Peak RSS (GiB) |
| --- | ---: | ---: | ---: | ---: |
| Chunk Streaming | 727.245670 | 577.271775 | 576.966275 | 2.597851 |
| Multicast v2 | 932.419197 | 475.007116 | 474.750517 | 2.672943 |

两次串行 simulator 合计 wall **1052.278892 s**、CPU **1051.716792 s**，均单线程观测、无保护触发。这些成本不包含一次性源码恢复/构建、单元检查、preflight 或 postflight。历史 N2048 默认 512-window 的 Chunk / MC simulator wall 分别为 **973.049485 / 670.278451 s**，合计 **1643.327935 s（27 分 23 秒）**；本轮合计约 **17 分 32 秒**，观测上少约 **9 分 51 秒（35.967%）**。[host-resources.csv](host-resources.csv) 保留精确值。恢复后的主机和全节点观察范围与旧选定节点观察不同，这不是严格同机同观察配置的加速比，也不能宣称 tokens 减少八倍带来八倍宿主机加速。

未发布原始路由 trace、逐 token 数据、payload、完整 transfer/config 或逐包环形日志。3136 Gbps 在此仍是保留每包 5 ns 单端口仲裁的模型，不代表真实硬件组播吞吐。
