# Trace 入队顺序与公平性验证

基线 `4320edac4c9b7ff41fe5da1f5524b72b72f65466`，ub-test / SystemC 2.3.4 /
GCC 14.2.0 / Debug / 1 ps。全部性能来自真实 SystemC 事件；本次没有改 Generator、
链路、协议处理、FIFO 容量或 RR/DRR 核心算法。默认入口保留。

## 结论

Phase 2 High 的约 0.623 主要来自 **CSV 分组经串行 Doorbell 放大的早期入队优势，
以及下游不可撤回的 23 个在途位置**，不是证据所支持的 RR/DRR 选择算法错误。
同 ready=0 只说明工作可用，不保证各 Jetty 同时进入调度队列。若把 CSV 行顺序视为
无关序列化细节，默认入口就存在应披露的建模偏差；若它代表实际 Doorbell 顺序，
该结果是有因果解释的入口/流水线现象。

只把相同 ready 的跨 Jetty 行改为轮转，已能大幅改变默认模式的早期 Jain；反向分组
会把先发优势转到 Jetty 15。可选 epoch-rr 入口在本实验中使逐 WR 时间、PSN 和顺序
对三种 CSV 排列完全不变，控制后 RR 与 DRR 的窗口 Jain 相同且接近 1，但不是强制等于 1。

旧 MoE 结论须限定为原始分组入口与指定早期窗口；不能把旧约 0.623 当作 RR/DRR 的
稳态能力。控制入口后仍没有 DRR 总吞吐优势，也没有普遍更优的 P50/P99。
FIFO 同样受入口轮转改善，不能把入口改动的效果归因于 DRR。

## 时序与容量证据

High / 原 CSV / RR，全部 WR ready、eligible、submit 均为 0 ns，但：

| WR / Jetty | enqueue ns | dequeue ns | dispatch ns | q1 accept ns | wire tx_start ns |
|---|---:|---:|---:|---:|---:|
| 0 / 0 | 1 | 1 | 2 | 2 | 21 |
| 22 / 0 | 23 | 32 | 33 | 1039.88 | 21591.56 |
| 128 / 1 | 129 | 1039.88 | 1040.88 | 2058.76 | 22610.44 |
| 1936 / 15 | 1937 | 15304.20 | 15305.20 | 16323.08 | 36874.76 |

例如 WR0 enqueue 在 delta=3 / event_seq=6203；dequeue 在同一 ns 的 delta=4 /
seq=6204。WR22 dispatch 在 delta=106 / seq=6813，但 q1 accept 到 delta=2320 /
seq=11881 才发生。原始 `.timeline.csv.xz` 保存完整稳定顺序，无需猜测同时事件的先后。

100 ns 时已选中的 WR0..22 各占一个位置：链路正在串行化 WR0；q11/Encap/q10/Nth/
q9/Rtph/q8/Retransmit/q7/Congestion/q6/TP/q5/TPG/q4/BTAH/q3/Tap/q2/Order/q1
依次持有 WR1..21；scheduler 持有 WR22 并阻塞输出。即 **11 个深度 1 FIFO +10 个
模块内部持有项 +1 个 scheduler 持有项 +1 个链路服务项=23**。不是 23 个额外 FIFO。
第一包在 21 ns 开始，1018.88 ns 串行化后于 1039.88 ns 释放链路，反压才允许后续选择。

源码定位：默认 CSV 扫描 `simulators/nano_ub/trace_e2e.cpp:218`；Doorbell
`include/nano/ub/tx.h:140`（151 读、152 等 1 ns、156 写）；调度入口/选取/阻塞输出
`include/nano/ub/fair_scheduler_sc.h:56`、`:66`；流水连接与深度
`simulators/nano_ub/trace_e2e.cpp:120`；真实串行化
`include/nano/experimental/serialized_link.h:33`。观察器在 trace_e2e.cpp:19，
新入口在 :260；`timeline_checks.json` 保存位置快照及各级容量核验。

## 统一比较

两负载、三种排列、两入口、三策略共 36 组。排列只改变同 ready 的跨 Jetty 顺序，
逐 WR 全字段和 Jetty 内相对顺序完全保留。窗口选择规则预先固定为全部 36 组的
最长共同持续积压区间，结果是 **[1940,38738) ns**，无策略单独选窗。

这比 Phase 2 High 的 [1938,104637) ns 短，故本表原入口 High RR Jain 是 0.176882，
并非历史窗口的 0.622615；默认原始事件完全相同，差别来自比较口径。

| 负载 / CSV 排列 | csv FIFO | csv RR | csv DRR | epoch FIFO/RR/DRR |
|---|---:|---:|---:|---:|
| moe_high / original | 0.062500 | 0.176882 | 0.174255 | 0.965326 |
| moe_high / reverse_groups | 0.062500 | 0.174255 | 0.174255 | 0.965326 |
| moe_high / round_robin | 0.965034 | 0.965034 | 0.965034 | 0.965326 |
| moe_skew / original | 0.062500 | 0.176876 | 0.176876 | 0.965326 |
| moe_skew / reverse_groups | 0.062500 | 0.176876 | 0.176876 | 0.965326 |
| moe_skew / round_robin | 0.965034 | 0.965034 | 0.965034 | 0.965326 |

窗口不足以覆盖任意整数个完整 WR 轮次，且 WR 原子服务不可抢占，因此没有要求 Jain=1。
High 原入口 RR 的最大窗口份额约 58.47%，epoch 模式约 8.31%；全部逐 Jetty wire/payload
窗口份额和全程份额见 `per_jetty.csv`。全程 wire Jain 在所有排列/策略/入口中保持
High=0.999825、Skew=0.999279：全部负载最终完成，全程总量近均衡不代表早期公平。

同一原 CSV 下 High makespan 从 2055489.96 变为 2055504.96 ns，Skew 从 978702.76
变为 978717.76 ns，均增加 15 ns；对应吞吐 High 99.477689→99.476964 Gbps、
Skew 99.455994→99.454470 Gbps。新模式等待首批 16 个 WR 入队，将首次选择从
1 ns 延到 16 ns，这是真实入口等待成本，不是性能提升。High 新模式 RR/DRR P50
均为 1032065.60 ns，P99 为 2038849.60 / 2038689.088 ns；Skew P50 均为
514707.52 ns，P99 为 971319.7696 / 970529.0368 ns。完整精度与 scheduler 等待见汇总。

## 工程边界与验收

新模式按最早 eligible ready 组、持久 Jetty 轮转、有界批次和真实队列信用入队；
一批实际 admitted 后才允许下一次选择，默认批上限 64。不能参与的依赖阻塞 Jetty
不加入屏障，满队列等待真实 dequeue；未来 ready 由独立定时线程记录。同时间完成
若发生在快照之后则参与下一批。批容量不足时不承诺全 Jetty 原子入队；详情、成本、
delta 语义、字段定义及复现见 [METHOD.md](METHOD.md)。

验收：原 15 CTests、16 E2E、24 Phase 1、16 Phase 2 测试及 21 组 Phase 2 仿真保留
并通过；21 组共 42 个原 event/WR 文件全字节一致。新增 11 测试覆盖容量、ready 分组、
依赖、同时间竞争、跨 Jetty 排列、重复性和空输入。36 组均验证完整 payload、无丢失/
重复/非法乱序、实际完成和 ACK 回收；新增审计独立检查 PSN、ACK 字节时序、传播、
FIFO 守恒/容量、批次屏障、dispatch/wire 顺序。三策略 High 新模式完整日志重复一致。

payload 仍由实验侧带字节缓冲逐块复制和校验；64 B header/ACK 是计费假设，不是完整
wire 编码。每 WR 单 PSN/TASSN，64 B 块不是 UB 分包。仍为单源共享链路/接收服务及
隔离目标内存，不模拟完整多 NPU 网络、分包恢复或硬件 DMA/内存性能。
