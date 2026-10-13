# Phase 2：通用 WR Trace → SystemC → 统一事件评估

实现完成于 ub-test 的独立 worktree，基于 Phase 1 提交
`d04812bb969fdac5457ae601b796ad8979fe8fda`。使用本地可读的工程、原始事件与
SystemC 2.3.4，编译器 GCC 14.2.0、C++17、Debug，时间分辨率 1 ps。
SystemC 来自官方固定提交 `5fc1469339775b54b1fcc2020ac744a58be5b50e`。
所有新性能数据来自实际 SystemC 事件；未使用独立分析模型替代协议仿真。

## 实现与语义

- `simulators/nano_ub/run.py`：严格读取通用 WR Trace 1.0；校验能力边界，显式映射
  节点、Jetty、目标内存；输出版本化内部 TSV 和运行说明。仿真器不读取 MoE sidecar。
- `simulators/nano_ub/trace_e2e.cpp`：新入口接到现有真实 TX、PSN/重传缓冲、字节链路、
  RX、内存与返回完成链；`ready_ns` 精确定时，依赖等待真实完成，同 Jetty 不越序，
  不同 Jetty 可绕过依赖阻塞。观察事件不消耗额外仿真时间。
- `UbMemory.external_write`：只替换实验目标的存储后端，保留原 4 ns 服务和完成路径。
  原有 1 MiB 固定内存及默认模块行为保留；实验按目标隔离内存并检查全部真实字节。
- `evaluation/analyze.py`、`evaluation/results_schema/README.md`：统一事件和指标，
  原始 CSV、结果定义、全局与逐 Jetty 指标均保留。
- `scripts/run_phase2.sh`：构建、旧实验回归、输入/顺序测试、七场景三策略、原始事件对照、
  重复运行、统一统计的一键入口。

这是**单源、多 Jetty、共享前向/返回链路和接收资源**的抽象。各目的节点身份与内存
地址空间真实隔离，但共用 TP/PSN、RX 和内存服务；不代表完整多 NPU all-to-all 拓扑。
泛化配置为 data-write；WR Trace 1.0 没有 transport Fence/ODR/CQE 控制字段，应用 sidecar
里的最后 SQE 标志不在本次模型内。未知 CSV 字段直接拒绝。原有 Fence、排序、ROT 测试
保留并回归；通用依赖不是对完整 Fence 协议的替代。

边界：单源、最多 1024 活跃 Jetty、60000 WR（避免 TASSN wrap）、单 WR 1..16 MiB、
总 payload ≤128 MiB、ready ≤1 秒；超过边界报错，不截断。空 trace 支持。

## 基线恢复

Synthetic mixed（64/256/1024 B，每 Jetty 256 WR，八 WR 一组、t=0）和 equal
（256 B）各三策略的新输入结果，与原端到端实验逐事件、逐 WR 完全一致。
每个 mixed 策略对齐 16,896 条旧事件及 768 个 WR。只增加 ready/eligible 观测事件，
映射列被剔除后原事件没有变化。共六组精确对照记录见
`experiments/phase2/output/baseline_comparison.json`。

旧 16 组实验的 32 个 event/WR CSV，加原汇总与逐 Jetty CSV，共 34 文件字节一致。
新统一评估采用线性插值 `(N-1)*q`，旧脚本用 nearest-rank `ceil(q*N)-1`，所以在
**同一组时间戳**上 mixed DRR P50 从旧 8212.84 ns 变成 8225.64 ns，P99 从
31012.20 ns 变成 30953.8832 ns。这是分位数定义差异，不是仿真行为变化。

## 实测结果

下表延迟为 ready→返回完成；吞吐为总有效 payload / 全局 makespan。P50/P99 单位 us，
采用统一线性插值定义。完整精度、queue wait、逐 Jetty P50/P99 在输出 CSV/JSON 中。

| 场景 | 策略 | payload Gbps | P50 us | P99 us | wire Jain |
|---|---|---:|---:|---:|---:|
| mixed | FIFO | 87.046 | 15.898 | 30.954 | 0.621216 |
| mixed | RR | 87.046 | 15.798 | 31.205 | 0.599007 |
| mixed | DRR | 87.046 | 8.226 | 30.954 | 0.999864 |
| MoE low | FIFO | 96.604 | 7.961 | 16.133 | 无有效共同窗口 |
| MoE low | RR | 96.604 | 8.130 | 16.133 | 无有效共同窗口 |
| MoE low | DRR | 96.604 | 7.961 | 16.133 | 无有效共同窗口 |
| MoE high | FIFO | 99.478 | 1027.658 | 2035.633 | 0.062500 |
| MoE high | RR | 99.478 | 1032.051 | 2038.835 | 0.622615 |
| MoE high | DRR | 99.478 | 1032.051 | 2038.505 | 0.622615 |
| MoE skew | FIFO | 99.456 | 490.869 | 968.770 | 0.062500 |
| MoE skew | RR | 99.456 | 514.186 | 971.305 | 0.170933 |
| MoE skew | DRR | 99.456 | 513.679 | 970.514 | 0.170933 |

MoE low/high/skew 分别为 77 / 2066 / 1009 WR，总 payload
196416 / 25559424 / 12167232 B。三策略各场景 makespan 相同，分别
16265.64 / 2055489.96 / 978702.76 ns。high/skew 多数 WR 接近同一大小，
RR 是强基线；未观察到 DRR 总吞吐提升，也没有普遍的 P50/P99 优势。

Synthetic burst 和 Poisson 也通过同一输入与评估接口。burst 三策略同为 85.622 Gbps；
Poisson FIFO 86.012775、RR/DRR 86.014817 Gbps，此微小有限批次差异不应解释为
稳态优势。Poisson DRR P50 较低而 P99 较高，完整值见汇总。

### 公平性窗口与流水线效应

公平性是实际线字节/有效 payload 服务的 Jain，不是完成 WR 数量的 Jain。
Synthetic 保留原 2–6 us 窗口。MoE 的初始诊断窗口因 FIFO 提前耗尽部分 Jetty 而失效；
最终规则使用三策略队列事件求**全部活跃 Jetty 持续积压区间的最长共同交集**，
向内取整为 ns。不使用已算出的 Jain 来挑窗口，也不删除不利 Jetty。

- high：`[1938, 104637)` ns；skew：`[947, 38738)` ns。
- low：不存在共同持续积压区间，Jain 为 null。burst/Poisson 的固定窗口也无效。
- 每个结果保存窗口、选择规则、最小队列深度、线/有效字节；汇总强制三策略共用有效性。

RR/DRR 在 high、skew 的 wire Jain 一样，分别约 0.623 / 0.171。原因不只是调度器：
Trace 按 Jetty 分组进入 doorbell，后面 Jetty 的队列建立前，已有 23 个 Jetty 0 WR
被选入下游流水线。RR high 首个其他 Jetty 的 tx_start 为 22610.44 ns，skew 为
23455.24 ns；后续调度不能撤回已进入流水线的工作。因此有限早期窗口包含显著预先
排队效应。FIFO 在所选窗口只发送 Jetty 0，Jain=1/16，虽其余队列持续积压。
这些是本次有限 trace/流水线的观察，不是对 RR 稳态公平性的否定。

## 验收与复现

```sh
./scripts/bootstrap_systemc.sh
source .deps/env.sh
./scripts/run_phase2.sh
```

已有兼容 SystemC 时可设置 `SYSTEMC_PREFIX`、`CMAKE_BIN`、`CTEST_BIN`；无需 sudo。
构建目录默认 `build-phase2`，产物默认 `experiments/phase2/output`；可用 `BUILD_DIR` /
`RESULT_DIR` 改到独立目录。运行时不访问应用账号或远端存储。

验收证据都保存在 `experiments/phase2/output`：

- 原 15 CTests、16 E2E，原三个 mixed 确定性重复运行；`legacy_validation.txt`。
- 24 Phase 1 测试；`phase1_tests.txt`。
- 16 Phase 2 输入/依赖/乱序/容量/大 WR/目标隔离/评估测试；`phase2_tests.txt`。
  8300 个单 Jetty WR 触发实际源 FIFO 和调度器队列反压；1048577 B WR 超过旧内存界限；
  目标地址均为零的不同目的地正确隔离；损坏/漏完成事件被评估器拒绝。
- 七个场景从固定种子重新执行 Generator，Trace 与 sidecar 全部逐字节匹配 Phase 1；
  `generator_comparison.json`。SystemC 消费本次新生成的通用 CSV。
- 21 组 generic Trace 仿真；`trace_validation.txt`。
- 六组旧 raw-event/WR 精确对照；`baseline_comparison.json`。
- 三策略 high 重复运行的原始 event/WR SHA256 完全一致；`determinism.json`。
- 原 34 CSV 字节对照；`legacy_byte_comparison.txt`。

每组保留 `input.tsv`、`run.json`、完整 `systemc.events.csv`、`systemc.wr.csv`、
`metrics.json`。`summary.csv` / `summary.json` / `per_jetty.csv` 提供统一汇总。

## 不超出模型的结论

100 Gbps、50 ns 传播、64 B header/ACK、512 B DRR quantum 都是显式实验参数。
WR 原子调度，每 WR 一个 PSN/TASSN；64 B serializer 块不是协议分包。
完整字节复制与检查不等于 cache、DMA/PCIe、设备内存带宽或真实 NIC 性能模型。
ACK 合并成功事务完成与包确认，精确退休但未实现完整独立 TPACK/丢包定时器恢复；
本实验不注入丢包，不宣称可靠传输覆盖超过原仿真器。

结果说明调度器能改变共享瓶颈前的服务顺序、逐 Jetty 延迟和有限窗口字节分配，
但不能提升已有满载串行链路的总服务能力。MoE 数据与 synthetic mixed 的 DRR 优势
不能互相替代。没有扩展到独立的新协议、训练全流程或硬件性能预测。
