# Nano-UB 最小 SystemC 端到端调度实验

日期：2026-10-12。环境：ub-test。所有实现位于独立目录；没有推送远端。

## 已完成什么

`JettyFairScheduler` 已实际接入 `bench/scheduler_e2e.cpp` 的 UB URMA WRITE 发送、链路、接收、目标内存和返回完成路径。FIFO/RR/DRR 使用同一条流水线、同一负载、同一资源参数，仅调度策略不同。测量来自 `sc_time_stamp()`；未使用上传的 `results.csv` 或独立 C++ 微基准生成结果。

输入压缩包大小 70,982 B；SHA256：
`d9d57e8e22a6b8936f28d7ae2fe465fa76f9e08a66d1a0e60b5475856437505a`。
三个输入和原始 ZIP 在新环境均成功下载。仓库与工作区 `.agents` 中未发现额外 AGENTS.md/技能指令。SystemC 2.3.4 从 Accellera 官方 Git 仓库构建，提交 `5fc1469339775b54b1fcc2020ac744a58be5b50e`，C++17；无 sudo。CMake 4.4.4 安装于独立目录。完整来源见 `eval/e2e/provenance.json`。

## 原有限制与本次改动

- 原 `EtherLink` 每个 Flit 固定等待 50 ns，传播与服务时间合并，与 `mem_len` 无关；不足以评估字节调度。本实验新建 `SerializedLink`，100 Gbps 全双工，两方向分别串行化，传播延迟固定 50 ns、与串行化重叠。原 `EtherLink` 没有修改。
- 假设每个 WRITE 为 64 B 封装加真实 payload，返回 ACK 为 64 B。每个最大 64 B 的串行化单元均有独立 SystemC 等待、字节复制和事件记录。发送端源负载经链路复制、接收端重组，再由目标内存写入；不是只按 `mem_len` 延时而不搬运数据。
- 这些单元是**串行化分块，不是 UB 传输分包**。整个 WR 仍对应一份 Flit 元数据、一个 PSN 和一个 TASSN；无跨 WR 抢占。64 B 封装不是 UB 精确线长，也未实现真实头部编码、多包 UB 分段/重组。源数据和接收数据使用实验侧负载存储，按唯一目标地址关联元数据。负载字节正确性逐字节验证。
- 原 `UbMemory` 默认只写 16 B 且 WRITE 无完成输出。新增显式启用的 `bulk_write` 和 `complete_writes`，仍在原内存模块 4 ns 服务事件后提交；接入完整负载并驱动原 CompletionGen/Reorder/TAACK 模块。未启用时维持原行为。内存服务仍固定 4 ns，不能据此推导真实内存带宽。
- TPG 原先把 RC ID 改成 TP 通道号。本实验显式启用 `preserve_rc_id`，三个 Jetty 保留 RC ID 1..3，共用原有单 TP 通道及全局 PSN/TASSN 分配。没有实现多 TP 通道状态。
- 返回路径接通 Decap → NTH → RTPH ACK 分流 → BTAH → 完成消费；补充 BTAH 对 0x11 TAACK 的识别，CompletionGen 保留 RC、地址、长度、ODR 和仿真相关令牌。实验将事务完成与包 ACK 合并，返回 ACK 同时送调度器、发起端排序器和重传缓冲。
- 重传缓冲显式启用“只回收匹配 PSN”的模式，避免原“任意 ACK 清空全部缓冲”；原默认模式保留。本实验不覆盖丢包、超时、NAK、重传、PSN 回绕。原重传模块本身没有实现其注释所述的完整 GoBackN 恢复。
- 调度器改成独立入队/出队线程。最初接入发现单线程被下游阻塞时只看到极少可调度请求，公平性窗口检查失败；修复后才生成本文数据。所有中间 FIFO 深度为 1，调度队列每 Jetty 深度 4096，源入口容量 4096；原 Doorbell 仍按每 WR 1 ns 入场。
- Fence 改成按具体 `sim_wr_id` 匹配，重复目标地址不会误释放；等待本 Jetty 所有前序 WR 完成，并阻塞后续直到该 fenced WR 完成。这是比规范 Read/Atomic 示例更保守的实验屏障，**不宣称实现完整 Fence 依赖语义**。`sim_wr_id` 是新增仿真元数据，不是 UB 线头字段。
- 排序器实验模式阻塞等待前序 RO/SO 的完成，避免原单 pending SO 被后续 SO 覆盖，NO 完成不减 RO/SO 计数。采用原模块的全局保守排序域，不是完整按 RC 的 UB ROI 实现；默认旧行为保留。性能负载无 Fence、无 RO/SO 依赖。
- 修复 M12 的 `sc_main` 缺少 return，原环境中该未定义行为实际触发非法指令。CMake 增加官方 SystemCLanguage config 查找，保留 pkg-config 回退。

用户提供的 UB 2.0.1 中文 PDF：PDF 第 220 页说明 Fence 为应用/处理器机制，其示例等待先前 Read/Atomic 响应；第 228 页说明 WRITE 响应应保留 INI_RC_ID。这里只用来核对边界，不把教学实现等同完整规范。

## 实际路径与瓶颈

发送：Doorbell → JettyFairScheduler → OrderTrackerIni → BTAH → TPG → TP TX → CongestionWindow → RetransmitBuffer → RTPH → NTH → UbEncap → SerializedLink。

接收：UbDecap → NTH → RTPH → TP RX → PSN Reorder → BTAH → OrderTrackerTgt → TransDispatch → UbMemory → CompletionGen → CompletionReorder → TAACK → 响应封装 → 返回链路 → 发起端 ACK/TAACK 解析 → 完成消费及三个反馈口。

PSN 在调度之后分配，接收端原 PSN 检查仍执行；没有为了策略重排关闭顺序检查。UbEncap/响应封装为原 11 ns，其他原流水线段一般 1 ns。混合与等长负载在预先固定的 2–6 us 窗口内前向链路占用均为 100%，三个 Jetty 均持续有积压。将同一 DRR 混合负载链路速率降到 50 Gbps，测得总完成时间从 31,621.48 ns 变为 63,077.80 ns，payload 吞吐从 87.046 变为 43.637 Gbps，支持本负载主要受新增链路服务约束。

## 固定负载与指标

无随机数。每个 Jetty 256 个 WRITE，共 768 个，所有 WR 在 t=0 进入容量充足的源入口。按每 Jetty 连续 8 个 WR 的突发交替提交。目标地址不重叠，payload 是 WR ID 和字节偏移的确定性函数；每个 Jetty 的序号严格递增。

混合负载：Jetty 1/2/3 分别为 64/256/1024 B，共 344,064 payload B。等长对照：全部 256 B，共 196,608 B。DRR quantum 512 B，记账 64+payload B。FIFO 按全局到达顺序，RR 每次一个完整 WR，DRR 按上述字节成本。

- 延迟：**源入口提交**到**发起端解析后消费成功 TAACK**。包含 Doorbell 排队、调度、正反向流水线、链路、目标内存与返回完成时间。P50/P99 为全部 WR 的 nearest-rank 分位数，不是仅链路延迟。
- batch payload Gbps：总完成 payload bits /（最后完成时间 − 最早提交时间）。包含启动和排空；不是稳态流量，也不含封装开销。每 Jetty batch Gbps 使用同一全局分母，有限批次下最终各流传完固定字节，因此此值不用于判断调度公平性。
- 公平性：在预先固定的 **2,000–6,000 ns** 内，从实际 `tx_chunk` 事件计算每 Jetty 占用的线字节，窗口边界按块的服务时间交集分摊；Jain = (Σx)²/(3Σx²)。同时报告 payload Jain，后者不等于按线字节调度的目标。分析器检查所有 Jetty 整个窗口始终有积压，且余量大于 1；队列计数来自实际 enqueue/dequeue 时刻。
- 吞吐与分位数取自真实事件，不来自独立公式生成的合成流水线。未测量硬件性能、主机 CPU 开销或动态状态内存开销；记录了每 Jetty 调度队列峰值。

## 结果

| 负载 | 策略 | payload Gbps | P50 ns | P99 ns | 窗口线字节 Jain | 窗口 payload Jain |
|---|---|---:|---:|---:|---:|---:|
| 混合 | FIFO | 87.046 | 15,892.84 | 31,012.20 | 0.62122 | 0.54827 |
| 混合 | RR | 87.046 | 15,754.60 | 31,212.64 | 0.59901 | 0.53388 |
| 混合 | DRR | 87.046 | 8,212.84 | 31,012.20 | 0.99986 | 0.94759 |
| 等长 | FIFO | 79.362 | 9,988.52 | 19,639.72 | 0.99710 | 0.99709 |
| 等长 | RR | 79.362 | 9,988.52 | 19,639.72 | 0.99999 | 0.99999 |
| 等长 | DRR | 79.362 | 9,988.52 | 19,639.72 | 0.99978 | 0.99976 |

这个负载中，DRR 改善线字节份额和总体中位数，**没有提高总吞吐**，总体 P99 与 FIFO 相同。混合负载 Jetty 3（1024 B）的 P50 从 RR 的 15,964.52 ns 增至 DRR 的 20,480.36 ns；因此不能说所有流延迟都改善。等长时 RR 和 DRR 总体吞吐/延迟一致。窗口 Jain 的微小偏差来自 quantum、WR 原子性及有限窗口边界。

公平性目标必须区分：RR 在该混合窗口完成的线端 WR 数为 32/32/33，请求数 Jain=0.99979，确实接近等请求份额；其线字节份额约为 8.267/20.480/71.253 Gbps，与 WR 大小差异相符，不能据此称 RR 对请求不公平。DRR 的线字节份额为 33.792/33.365/32.843 Gbps，接近等线字节目标；对应完成 WR 数为 132/53/15，请求数 Jain=0.65174，它并不追求等请求数。由于各流固定封装与 payload 比例不同，等线字节也不等于等有效负载字节。

尾延迟代价也需逐流看：混合负载小 WR 的 P99 从 RR 的 31,089.76 ns 降至 DRR 的 8,414.04 ns；大 WR 的 P99 两者均为 31,447.40 ns，但其中位延迟如上增加。不能仅用总体 P50/P99 宣称每个 Jetty 都受益。

本实验窗口内所有流持续积压；**没有测量间歇流**，不能把低需求流未用满等份额视为不公平，也不能把这个有限突发结论推广到交互式、开关型或不同权重的业务需求。

混合负载各策略最大单 Jetty 队列峰值分别为 FIFO 244、RR 243、DRR 249 WR；逐流窗口服务速率、请求计数、峰值和 P50/P99 见 `per_jetty.csv`。

## 验证

- CTest 15/15：原 M00–M11、修复的 M12、独立 core 测试、新 M13 边界测试。
- 15 个基础端到端运行：三策略 × mixed/equal/fence/ordering/rot。其中性能场景各 768 WR，正确性场景各 24 WR。另有 50 Gbps 瓶颈验证，共 **16 个 E2E 运行**。
- 每个运行检查全数完成、无重复派发/执行/完成、全 payload 正确、每 Jetty 派发/执行/完成顺序、PSN 连续且无重复、RC 和完成令牌不变、所有 ACK 回收完毕、无非法协议出口流量。
- Fence 检查明确的完成前后时间关系。RO/SO 场景覆盖多个 SO，检查每个 SO 不早于所有先前 RO/SO 完成；ROT 运行保留目标端 TASSN 检查。
- M13：相同目标地址的不同 WR、错误 Jetty、错误令牌、重复旧完成、深度 1 队列及输出反压、未知/重复 ACK 不回收其他包。
- 分析器独立对齐每 WR 汇总与原始事件，检查每个串行化块偏移、大小、PSN 和服务时间，确认事件无遗漏。
- 三策略 mixed 各重新运行一次，原始事件 CSV 与 WR CSV 均字节一致。没有以重复确定性运行冒充统计样本或置信区间。

## 复现与文件

需要 Linux、g++、make、Python 3、Git；没有 SystemC/CMake 时可安装到当前副本 `.deps`：

```bash
./scripts/bootstrap_systemc.sh
source .deps/env.sh
./scripts/run_e2e.sh
```

已有 SystemC 2.3.4/C++17 时：

```bash
SYSTEMC_PREFIX=/absolute/systemc/prefix ./scripts/run_e2e.sh
```

若 CMake/CTest 不在 PATH，通过 `CMAKE_BIN` / `CTEST_BIN` 指定。脚本使用 Debug 构建以保留原测试中的 assert，遇到任意失败立即停止。可设置 BUILD_DIR、RESULT_DIR、JOBS。

单场景：`./build-e2e/scheduler_e2e drr mixed eval/e2e/drr_mixed`。

- `eval/e2e/*.events.csv`：原始 SystemC 事件，时间单位 ps，包含入队/派发/分块链路/内存/ACK/完成。
- `eval/e2e/*.wr.csv`：每 WR 时间点和身份；`summary.csv` / `per_jetty.csv`：统计结果。
- `eval/e2e/ctest.log`、各场景 `.log`、`validation.txt`、`bottleneck_check.json`：验证证据。
- `changes.patch`：相对于输入项目包的代码和说明改动，排除原始事件数据等生成文件。
- 上传的独立 `results.csv`、原 `bench/scheduler_microbench.cpp` 和其他历史 `eval/results/` 均属于原有内容，不能作为本次 E2E 证据。

这是最小可运行的、无丢包、单 TP 通道、WRITE 场景实验。真实 UB 多包分段、故障恢复、完整多 RC 排序语义、其他操作类型、拥塞控制（原窗口仅 advisory）、长期稳定负载和 CPU/状态开销仍未覆盖。上述限制不会被本次“全部测试通过”消除。
