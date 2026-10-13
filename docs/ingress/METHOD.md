# 入口实验的语义、观测和复现

## 可选入口，不改变默认路径

`--ingress-mode csv` 是默认值，保留 Phase 2 的 CSV 顺序扫描和源 FIFO 提交。
`--ingress-mode epoch-rr` 是实验性入口仲裁，不是 RR/DRR core 的修改。

每轮先等待两个 SystemC delta，形成明确快照；只考虑已经 ready、依赖均已实际完成、
同 Jetty 前序已经提交的队首。优先最早的 eligible `ready_ns`。依赖阻塞队首被排除，
因此较晚 ready 的独立 Jetty 可以前进；这是必要的依赖阻塞例外，不提前释放未来 WR。
如果最早 eligible 时间组只是因队列满而不能入队，不让较晚时间组绕过。

在最早组内，以实际逻辑 Jetty ID 升序对应的稠密映射做持久轮转；每 Jetty 每批最多
一个 WR。批上限默认 64，且不超过源 FIFO 深度；只选有真实调度队列信用的 Jetty。
上一批完全 admitted 后才组织下一批，所以不存在未计入信用的入口在途 WR。

组织一批时，仅关闭**下一次 dequeue**，仍通过原 Doorbell 和 q0；直到每个提交 WR
确实触发 scheduler `on_enqueue`，才开放 gate。下一轮的两个 delta 让 scheduler 获得
执行机会。已选中的 WR、1 ns 调度服务及被下游阻塞的输出不会撤销或抢占。

没有可提交项时 gate 保持开放，等待真实 dequeue 释放信用、ready 或 completion；
依赖阻塞 Jetty 不属于本批屏障。完成在某次快照之后、同一物理时间的更晚 delta 到达，
则参与下一批；不回写过去时间，也不假装该 completion 已在快照前发生。
`ready_clock` 独立线程精确记录 ready 时间，即使入口正在等本批 Doorbell 完成。

16 Jetty 的当前场景能在首批让所有符合条件者先入队再选择。超过 64 个参与者、
源 FIFO 小于参与者数量、调度队列满、或依赖未完成时，只提供**有界分批机会**，
不承诺原子整批入队。`--ingress-batch`、`--source-depth`、`--scheduler-depth`
可用于容量测试，默认分别为 64、4096、4096；链路及各级流水 FIFO 仍不改变。

成本来自真实 Doorbell 1 ns/WR 和等待本批完成：16 个 Jetty 首次 dequeue=16 ns，
默认为 1 ns。没有添加硬件仲裁延迟模型，delta 是仿真调度次序而非纳秒。
逐批等待可能限制小 WR 的入口吞吐，因此新模式不是无成本的性能“修复”。

## 时间和事件定义

保留原 `systemc.events.csv` 与 `systemc.wr.csv` 格式。额外
`systemc.timeline.csv` 记录 `event_seq`（稳定递增观察序号）、`delta`、`time_ps`、
事件、原始 WR/Jetty、PSN、epoch、gate 和队列可用项数；不重复记录大量 byte chunk。

- ready：原 trace 的时间；eligible：候选轮转扫描首次确认可参与当前时间组的队首（默认模式为原 CSV 扫描）。
  epoch 模式还要求属于当前最早时间组；批上限之后尚未扫描到的候选可能更晚记录，
  这不是全部条件刚转真的精确时刻，不能把两模式 eligible 差异解释为协议延迟。
- submit：实际写入源 FIFO；input_read：Doorbell 真正取走。
- q0 write/read：Doorbell 输出与调度器 ingress 取走；enqueue：实际写入调度队列。
- dequeue：策略已选中；dispatch：1 ns 调度服务结束，尝试向 q1 写入。
- q1_write_accept：阻塞写真正返回，区别于 dispatch。
- q1..q11 read/write_offer/write_accept：各级 FIFO 与模块持有项之间的转移。
- tx_start/tx_end：实际字节串行器边界；memory/complete 与 Phase 2 定义相同。

`ObservedFifo` 仅在原 `sc_fifo` 操作前后调用观察函数，未增加存储、wait 或通知。
`num_available()` 遵守 SystemC delta 更新语义，不能把同 delta 的快照值当作额外容量；
审计用 accept/read 的有序队列账本验证每级容量=1、无丢失/重复，而不是只看快照。
默认原事件和 WR 文件与旧结果全字节一致，是观察不扰动默认行为的回归证据。

## 排列、窗口与指标

使用 Phase 1 原样 High、Skew，各三种 CSV：原顺序；每个相同 ready 组按 Jetty
降序分组；每个相同 ready 组按 Jetty 升序每次取一个轮转。所有 WR 字段、每 Jetty
相对顺序、各 ready 时间不变，脚本对逐 WR 字典和局部序列做相等检查。Generator、
trace schema 和应用逻辑不修改。适配器仍按 CSV 顺序分配目标内存地址，因此排列会改变
内部地址分配；这些地址不是原 WR Trace 字段，模型没有地址相关服务时间，仍逐字节
校验目标隔离和完整 payload。2 工作负载 ×3 排列 ×2 入口 ×3 策略=36 组。

**主比较只使用一个共同窗口，覆盖全部 36 组，包括两种工作负载。** 固定算法：
从真实 enqueue/dequeue 求每组所有活跃 Jetty 队列严格为正的区间，再求 36 组交集，
选择最长区间（并列取最早），向内取整为整 ns；不看 Jain 分数来选窗口。
若不存在，Jain 报 null，不换参与者子集。此次得到 `[1940, 38738)` ns。

Phase 2 的 High `[1938,104637)` 和 Skew `[947,38738)` ns 仅作为历史诊断口径记录，
不是本次策略/排列/入口主比较的窗口；不可把不同窗口的 Jain 直接当成改善倍数。

Jain 和服务份额从真实 tx_chunk 时间覆盖量求 wire/payload 字节；窗口边界上的块按
服务时间重叠量分摊。P50/P99、全局 makespan、有效吞吐、逐 Jetty scheduler 等待均用
Phase 2 统一定义；scheduler 等待=enqueue→dequeue，包含入口 gate 等待。
`orders.csv` 保存每个 WR 的 dispatch/wire 排名及 dispatch→wire 时间。

同时记录整个有限批次的 wire/payload 字节与份额。所有 WR 最终完成，所以全程份额
由提供的负载决定；它能说明总量与无丢失，不能掩盖或否定早期饥饿/不均衡。

## 复现与只读审计

需要 Linux/Bash、Git、Python3 标准库、C++17 编译器、Make、CMake ≥3.16。
在本分支的干净 checkout 内：

```sh
./scripts/bootstrap_systemc.sh
source .deps/env.sh
# 输出到独立目录，保留随包原始证据
RESULT_DIR=results/ingress-reproduction ./scripts/run_ingress.sh
```

已有 SystemC 时设置 `SYSTEMC_PREFIX`、`CMAKE_BIN`、`CTEST_BIN`，直接运行脚本即可。
主脚本先完成 Phase 2 全套测试/实验，再比较其 21 组的 42 个原始 event/WR 文件，
接着运行新增测试、36 组实验和压缩事件审计。没有调用外部应用或 MoE 专用模拟器。

单组执行：

```sh
python3 -m simulators.nano_ub.run \
  --trace experiments/phase1/output/traces/moe_high.csv \
  --policy rr --semantics data-write --ingress-mode epoch-rr \
  --binary build-ingress/trace_e2e --output-dir results/one-epoch
```

不重跑仿真，只审计已保存的原始数据：

```sh
python3 -m experiments.ingress.audit experiments/ingress/output
```

新事件和边界日志以 `.csv.xz` 无损存储；可用 `xz -dc FILE.csv.xz` 或 Python `lzma`
读取。manifest 保留压缩前后 SHA256。审计在临时目录解压，复算共同窗口与所有全局/
逐 Jetty 指标，验证 FIFO 容量、epoch 屏障、PSN、ACK chunk 时序、传播和 dispatch/wire
顺序，不改原始证据，不运行仿真。结果在 `summary.csv/json`、`per_jetty.csv`、各组
`metrics.json`、`timeline_checks.json`、`orders.csv`；原 Phase 2 文件保持原样。
