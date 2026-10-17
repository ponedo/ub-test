# Pair Jetty 资源复用：阶段报告

## 实现边界

本阶段只增加应用层 Pair Jetty 管理和统一执行入口。ns-3-ub 固定在 `2fde39d02920e639f5b200d0c5262a517326deb8`，包含已验收的反向索引和两项 WQE 完成修复；没有新的原生协议补丁。

`pair-layer` 默认 `--jettyMode=pair`，也保留 `--jettyMode=per-wqe`。两种模式使用同一可执行文件、原生动态库、输入和验证器。原有三个应用程序仍完整保留，作为回归基线。

- 有向 `(source, destination)` 按实际传输图建 Jetty；反向独立，本地任务不建远程 Jetty。
- Dispatch、Combine、Direct、Two-Stage、Chunk Streaming 的同向任务统一复用；每项通信仍是独立 WQE。
- WQE Task ID 与 Jetty ID 分离，回调同时校验两者。
- 每个 Jetty 维护逻辑 SSN，每个 WQE 显式记录实际 SSN 对应的 payload offset；不再使用 `SSN × segment_size` 推导偏移。发送 trace 的 16 位 wire SSN 与目标端解包后的逻辑 SSN分别处理。
- Chunk Ready 仍由目标端 TA 完成聚合产生，Relay 依赖、权重就绪、Compute 和最终 Top-k 回收规则保持原样。
- 不增加串行化、Token Packing 或新调度策略。

## 正确性证据

Gate A 共 12 个真实网络测试通过，包括 2/3/4 节点有向 Pair、本地不分配 Jetty、并发单段/多段、交错、迟到任务、目标端延迟、重复通知、取消/失败唤醒和资源清理。

持续复用测试在一个 Pair 上执行 22,000 个三段 WQE、66,000 个请求 TA，实际跨越 16 位 SSN 回绕，峰值 63 个未完成 WQE。目标端用 payload 自带 task/offset 独立校验，66,000 个响应和 22,000 个成功回调精确对应。压力测试达到默认 512 个在途 TA 上限，无丢失、提前完成或重复成功。

Gate B：12 个 No Balancing 场景 × 两种模式，24 次运行全部通过。
Gate C：36 个 Direct/Two-Stage/Chunk Streaming 场景 × 两种模式，72 次运行全部通过。

所有成对场景的逻辑传输图、Routing、Placement/Quota、WQE/TA、Payload、Compute 负载和最终结果一致。48 个 legacy 模式场景与已验收输出的 3,552 个共同文件逐字节一致，summary 和 Layer Latency 也一致。独立审计详见 `review-audit.json`。

最终加强后的模式/身份验证器重新检查全部 96 个 B/C 输出通过。9 个应用错误注入均被对应 guard 拒绝，重复通知的正常运行及结果一致性通过；另外 2 个独立验证器篡改测试正确拒绝错误 Payload 和提前 Weight Ready。44/44 原生测试套件通过。完整旧项目回归链也通过：原有 Direct 26 次运行、Planner 三组普通/优化测试、完整 No Balancing / Chunk Relay 和跨执行器 legacy parity，整体 149.18 s。原生动态库和最终执行文件的 SHA256 在回归前后保持一致。详见 `evidence/correctness.json` 和原始回归日志。

## 性能测量口径

`evidence/performance.csv` 是实际 ns-3 进程的 Wall Time、用户+系统 CPU Time、峰值 RSS、Jetty/WQE/TA/event 数量和模拟 Layer Latency。独立验证器的时间/RSS 单独列出。每个模式每个规模一次顺序运行，没有把单次观察当成置信区间。

固定 EP64、128 Experts、Top-k=8、seed=20261016 的原有合成 Routing Trace。模型参数、128 B Assignment payload、1024 B TA segment、UB 网络和计算参数均未调整。这里容量样本为单 TA Assignment；多段并发另由 Gate A 和权重场景覆盖。

已完成的 50K Assignment 对照：

| 指标 | 每 WQE 一个 Jetty | Pair Jetty |
|---|---:|---:|
| ns-3 Wall Time | 104.28 s | 35.35 s |
| Peak RSS | 2,030,988 KiB | 400,672 KiB |
| Jetty | 98,386 | 4,030 |
| WQE / TA / sender completion | 98,386 | 98,386 |
| ns-3 events | 4,487,239 | 4,487,239 |
| Layer Latency | 1,353,604,768 ps | 1,353,604,768 ps |

本次单次观察约 2.95× 宿主机加速、RSS 降低约 80.3%。这不是 MoE Layer 加速。Jetty 数量从随远程任务数量增长，变成由实际有向通信 Pair 数量决定；EP64 的上界是 4,032，当前 trace 实际使用 4,030。

原生每 Jetty ACK window 仍为原有配置，没有通过减小窗口节省空间。减少对象数量自然减少窗口和生命周期管理状态；这里没有独立分配器计量，不能把所有 RSS 差额都归因于 ACK window。

### 100K 可选容量点

Pair 模式实际完成并通过严格验证：ns-3 94.53 s、Peak RSS 587,500 KiB；4,032 个 Jetty，196,794 个独立 WQE/TA/成功通知、9,003,745 个事件、12,500 个 Token。独立验证器另耗时 210.33 s、Peak RSS 1,390,076 KiB，未混入仿真器耗时。

Legacy 对照在 242.18 s 被原有 8 GiB 剩余磁盘保护停止，CPU 241.97 s、Peak RSS 3,916,176 KiB。它未生成最终完成统计和 Layer Latency，因此不报告 100K A/B 加速比或最终时序一致。没有 OOM 或原生协议错误证据。本轮保留该受保护停止的完整记录，不修改保护条件强行重跑。

随后只对本阶段已完成运行的 native trace 做无损格式压缩：先逐文件哈希、归档、完整读回校验，再以归档与 manifest 替换工作副本，释放空间供必要回归。所有日志字节可恢复，应用事件/Payload/结果仍保留；没有触碰以前阶段的数据。

### 全部实际资源记录

| Assignments | Mode | Status | Wall s | CPU s | RSS KiB | Jetty | WQE / TA | Layer ps |
|---:|---|---|---:|---:|---:|---:|---|---:|
| 5000 | pair | PASS | 3.01 | 2.86 | 178412 | 2894 | 9850 / 9850 | 136649168 |
| 5000 | per-wqe | PASS | 3.26 | 3.12 | 299216 | 9850 | 9850 / 9850 | 136649168 |
| 10000 | pair | PASS | 5.77 | 5.55 | 227712 | 3534 | 19674 / 19674 | 271031968 |
| 10000 | per-wqe | PASS | 7.77 | 7.62 | 507112 | 19674 | 19674 / 19674 | 271031968 |
| 20000 | pair | PASS | 12.03 | 11.98 | 283096 | 3918 | 39354 / 39354 | 543165776 |
| 20000 | per-wqe | PASS | 20.06 | 19.97 | 895884 | 39354 | 39354 / 39354 | 543165776 |
| 50000 | pair | PASS | 35.35 | 35.12 | 400672 | 4030 | 98386 / 98386 | 1353604768 |
| 50000 | per-wqe | PASS | 104.28 | 104.13 | 2030988 | 98386 | 98386 / 98386 | 1353604768 |
| 100000 | pair | PASS | 94.53 | 94.28 | 587500 | 4032 | 196794 / 196794 | 2709921648 |
| 100000 | per-wqe | disk_free_guard | 242.18 | 241.97 | 3916176 | 未完成 | 未完成 / 未完成 | 未完成 |

100K 两臂运行顺序为 Pair 后 legacy；其余规模为 legacy 后 Pair。所有任务顺序运行，没有并行性能作业。

## 通信时序结论

现有 48 个小规模场景及截至 50K 的 EP64 对照中，Pair 与 legacy 的 Layer Latency 相同。不能因此声称任何负载下均相同。

独立事件分析对每个 Pair 累计已 admission 的 TA，直到整个 WQE 成功时才全部减去，得到实际未确认 TA 数量的保守上界：小规模权重场景最大 168，EP64 5K/10K/20K/50K 分别为 18/36/73/165，均低于默认 512。100K Pair 的对应上界为 317，但其 legacy 对照未完成，不能据此代替 A/B 验证。这说明这些运行未触发共享 Jetty 在途窗口瓶颈，支持观察到的时序一致。该指标不是原生窗口占用的直接采样；达到或超过 512 时不能据此断言真实窗口饱和。

## 限制

- 只支持在所有 WQE 结束后销毁 Manager；不提供在途驱逐、动态重绑定或析构时取消任务。
- 本次应用正常 Forward 不引入取消/失败调度；这些原生终止语义由独立真实网络 lifecycle probe 覆盖。
- 没有新增网络丢包、链路故障或所有重传组合的验证。
- 不修改原有 Assignment/Payload 安全上限。宿主机运行保留 300 s、6 GiB tree RSS、7 GiB address space、8 GiB output-disk-free 等保护。
- 新旧资源模型不能混用来计算后续 UltraEP Speedup。后续实验应统一使用 `pair-layer --jettyMode=pair`。

原始证据采用可恢复的去重/XZ 格式交付：20 个小于 10 MB 的独立传输包，恢复 16,643 个文件、3,689,276,006 字节。已实际恢复至空目录并逐文件重新读取验证 SHA256；13,127 个旧 manifest 项和 3,465 个原生 trace 文件哈希与先前证据一致。完整应用事件、Payload 和原生日志均保留，原 gzip 容器只改为原始成员文件表示。恢复命令及安全检查见 README。

复现命令见 README。完成本阶段后停止，等待验收；不开始正式 Token Scaling。
