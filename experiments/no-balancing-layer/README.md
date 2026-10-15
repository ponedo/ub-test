# Phase 1 / Milestone 2 — No Balancing 单层 MoE Prefill

基于已验收 PoC `82fd5e0b12f1fa9ebcd70fadd924c208eaa86b20`，本目录实现单层 `Token Dispatch → Expert Compute → Token Combine`。placement 在输入时固定；每个 expert 只有一个 NPU 位置；整个运行不复制、不重新路由、不调度迁移 expert。没有 Planner、Relay 优化、多层或 Phase 2。

## 复现与版本

```bash
git clone -b ultraep/no-balancing-layer-20261015 https://github.com/ponedo/ub-test.git
cd ub-test
bash experiments/no-balancing-layer/run.sh
```

依赖固定 ns-3-ub `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`，tools `29009175f1778f76a22d929063c3a0821cb91e56`。脚本先运行原 PoC 的**全部回归**到本目录的 `evidence/poc-regression`，不改旧 PoC 文件或证据；复用其版本/干净状态检查与构建工具安装。然后只构建新 scratch 应用，依次运行 4、8 NPU，验证通过才继续 64 NPU，之后运行倾斜、空负载、本地、自定义与同 seed 重复案例，最后运行普通和 `-O` 测试。

可覆盖 `NS3_ROOT`、`BUILD_TOOLS`、`PYTHON`、`BUILD_JOBS`、`EVIDENCE`（目录请用绝对路径）。默认依赖路径 `/workspace/ns-3-ub` 和 `/workspace/build-tools`。这是可联网复现流程，不是离线依赖包。已有依赖 checkout 必须为固定提交且 tracked clean。重新运行会替换选定证据目录下同名结果。

## 输入与可配置参数

`cases.py` 生成**合成 trace**，不是实测 trace。默认 seed=20261015，通过 Python `random.Random(seed).sample` 生成不重复 top-k；初始 expert placement 为 `expert_id % NPU数`，token 初始源为 `token_id % NPU数`。保存：

- `config.json`：全部配置、固定 placement、逐 token 的 source 和有序 expert 列表。
- `input.txt`：同配置的 C++ 输入；验证器逐字段检查与 JSON 一致。
- `assignments.csv`：原始合成 assignment trace，记录 token/rank/expert/source/target/bytes/local。

NPU数、expert数、Top-k、token数、placement、token映射、seed、model_dim、ff_dim、dtype_bytes、segment_bytes、peak_gflops、util_permille、setup_ns、link_gbps、link_delay_ns 全部可配置。示例先生成配置，再修改 JSON 的参数/placement/mapping，然后重新生成输入：

```bash
python3.12 experiments/no-balancing-layer/cases.py --npus 8 --experts 16 --tokens 23 --top-k 2 --seed 42 --out /tmp/custom-layer
# 编辑 /tmp/custom-layer/config.json 后：
python3.12 experiments/no-balancing-layer/cases.py --config /tmp/custom-layer/config.json --out /tmp/custom-layer
cd /workspace/ns-3-ub
PATH=/workspace/build-tools/bin:$PATH PYTHONPATH=/workspace/build-tools \
python3.12 ./ns3 run --no-build \
'no-balancing-layer --input=/tmp/custom-layer/input.txt --out=/tmp/custom-layer'
# 从 ub-test 根目录：
python3.12 experiments/no-balancing-layer/verify.py /tmp/custom-layer
```

配置在 Python 与 C++ 两端验证：范围、非重复 Top-k、映射长度、placement 和资源参数。为完整逐字节模拟设置显式安全界限：N≤256、E≤4096、assignment≤100000、单阶段逻辑 payload≤256 MiB；测试覆盖到 64 NPU，不声称边界内任意大配置都已验证。仿真保守截止为 10 s，未完成会失败而非生成成功结果。日志、payload 和 TA 不采样，不使用未记录的大规模捷径。

## 网络与数据路径

简单星型拓扑：N 个 NPU + 一个中央 UB switch，每 NPU 仅一个共享端口、一条链路，默认 100 Gbps / 20 ns，单一最短路径。所有 expert 和 token 共享该 NPU 端口，不为每 expert 分配额外整机网络带宽。其他交换/协议参数使用固定提交默认值。此拓扑不代表 CM384 或真实产品互联。

远端 assignment 的 Dispatch 和 Combine 各提交一个独立 WRITE WQE，拆成 `ceil(model_dim*dtype_bytes / segment_bytes)` 个 TA，再由 UB 实际分包。RTP pair 仅为实际使用的远端 NPU 对建立，静态最短路径不变。每 WQE 使用独立 Jetty，TASSN 从 0 开始；原生 UB Port/Link/Transport/Transaction 完成通信，无固定延时假装网络到达。

本地 assignment 显式做本地 buffer 拷贝及字节校验，通过 ScheduleNow 事件交付；**本地拷贝延时为 0，不模拟内存带宽/争用**。本地字节单独计数，不进入网络 WQE/TA/ACK 指标。

目标 `SetTargetExecutor` 在 TA 重组之后校验 request identity、范围、长度和实际 ExplicitPayload 全部字节；调用 `done(success)` 后才记录目标 TA 完成并更新复用自 PoC 的区间 Tracker。完整 assignment 才触发 `data_ready`。请求 TA 接纳和反向 TAACK 响应接纳分别记录，不能混入 payload 统计。发送端 `sender_complete` 与目标端完成分开记录；计算不等待源端 ACK 或 UbApp phase 的额外可见性延迟。

## Expert Compute 解析模型

采用每 NPU 本层 Dispatch 齐备屏障：只有该 NPU 所有 assigned token 都到达，才开始该 NPU 的计算批次。批次内按 expert ID 顺序串行，各 expert 按实际 token 负载计时；不同 NPU 并行。因此每 NPU 至多使用一份有效峰值预算，不会每个 expert 同时独占整机峰值。空负载 NPU 记 `compute_idle`，不产生计算事件。

采用两层 dense MLP 的简化 FLOP 口径，FMA=2 FLOP，不含门控第三矩阵：

```text
FLOPs_e = assigned_tokens_e × 4 × model_dim × ff_dim
rate = peak_gflops × 10^9 × util_permille / 1000  [FLOP/s]
time_e_ps = setup_ns × 1000 + ceil(FLOPs_e × 10^6 / (peak_gflops × util_permille))
NPU_compute_time = sum(time_e_ps for active experts on this NPU)
```

默认 dim=256、ff=1024、dtype=2 B、TA=256 B、peak=1000 GFLOP/s、util=500‰、setup=100 ns/active expert。使用 Simulator 皮秒精度，避免默认纳秒量化改变公式。所有参数均为**模型假设，不是实测硬件数据**。不模拟 GEMM 数值、访存瓶颈、kernel overlap、动态批处理或通信计算资源争用。

相应 NPU 整个计算批次结束后，才发送其所有 Combine 贡献。结果是对真正接收到的输入字节做确定性 expert-specific XOR 变换，**不是数值 MLP**。源 token 收齐全部 K 个唯一 expert 贡献并校验每个字节后完成；Combine 是完整贡献 gather/校验，**没有浮点加权 reduction**。Layer end 是所有源 token 完成，不等最后一个 sender ACK；仿真仍排空并确认所有 sender completion。

## 指标与已运行结果

LayerLatency = 最后 token 完成时间 − layer_start；起点为 1 ns。Dispatch/Combine envelope 为该阶段最早 send 至最后目标 data_ready；Compute envelope 为最早非空 NPU compute_start 至最后 compute_end。三者可能跨 NPU 重叠，**不可简单相加**。

重叠统计取远端通信 `[首 TA 接纳, 目标 assignment ready]` 区间并集，与 NPU compute interval 并集求交；不是链路逐字节忙碌时间。本地零时长交付不计入网络重叠。`compute_total_busy_ps` 是所有 NPU busy 之和，故可大于 LayerLatency。

| Case | NPU / token / assignment | LayerLatency µs | Dispatch envelope µs | Compute envelope µs | Combine envelope µs | 每阶段 remote / local payload B |
|---|---|---:|---:|---:|---:|---:|
| n4 | 4 / 8 / 16 | 17.821896 | 0.422320 | 17.215936 | 15.441144 | 5632 / 2560 |
| n8 | 8 / 16 / 32 | 11.460160 | 0.410560 | 10.832560 | 4.704944 | 15872 / 512 |
| n64 | 64 / 128 / 256 | 20.319648 | 0.622640 | 19.486688 | 17.912176 | 128512 / 2560 |
| skew4 | 4 / 8 / 16 | 35.675272 | 0.723000 | 34.154432 | 0.797840 | 6144 / 2048 |
| empty4 | 4 / 0 / 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| local4 | 4 / 8 / 16 | 8.588608 | 0 | 8.588608 | 0 | 0 / 8192 |
| custom4 | 4 / 7 / 14 | 12.599248 | 0.863400 | 12.080848 | 10.943184 | 5654 / 1542 |

64 NPU：251 个远端 assignment、5 个本地 assignment；两阶段合计 502 次发送端完成、1004 个目标 TA，Dispatch/Compute 重叠 0.412320 µs，Compute/Combine 重叠 2.981680 µs。每阶段 remote+local=256×512=131072 B；两阶段都执行真实完整字节校验。字节数为应用 payload，不含协议头、ACK、重传或链路开销；原生 traces 保留这些网络事件。

skew4 把全部 expert 初始放在 NPU0，固定保持，检查负载 `[16,0,0,0]`。custom4 使用不均匀 token 来源（5 个在 NPU0、2 个在 NPU2）、自定义 placement、514 B payload / 256 B TA 非整除末段、不同 compute/link 参数。同 seed 的 n4-repeat 与 n4 事件 CSV 完全相同。上述不同规模 workload 不构成硬件扩展效率对比。

## 验证与证据

`verify.py` 使用显式异常，`-O` 不会关闭验证；检查 input/JSON/raw trace 一致、T×K assignment 守恒、每 TA 四阶段 identity/offset/length/时序、反向响应、无提前/重复 ready、串行 expert 资源预算、计算公式、Combine 依赖、Top-k 和 Layer 屏障及未知事件拒绝。

16 项 Python unittest 在普通和 `-O` 下通过，包括非法 placement、重复/越界 top-k、非法源与模型参数、C++ 实际拒绝非法输入、丢贡献、重复 token 完成、错误 payload 长度/TA offset、提前计算/Combine、错误计算预算。另运行原 PoC 全部 Tracker、11 项普通/优化验证器测试、默认/变体网络和真实 payload 损坏负例。每个有效新案例还分别执行普通及 `-O` 严格验证。

证据目录保存每案例 config/input/assignments/events/summary、原生 UB packet/ACK/port traces 和 console，汇总 `run-ledger.json`；另有 build.txt、tool-versions.txt、tests.txt、tests-optimized.txt、reproducibility.txt。新源码与脚本仅位于本目录；旧 PoC 分支和 main 不改动，底层 ns3/tools 跟踪文件不改动。应用复制至 ns3 scratch 编译。

开发中严格验证曾发现两点，已修复并全套重跑：默认时间精度使计算公式取整不一致（显式 PS resolution）；同一个 TP 回调也报告反向 TA 响应（拆分请求/响应事件）。没有隐藏底层失败或调整模型以绕过验证。

当前验收边界是合成 trace、固定 placement、单层完整网络/解析计算流水和所列 correctness cases；不是数值 MoE 正确性、真实硬件性能、全部故障模式或大规模吞吐结论。到此停止，等待用户验收，不启动 Planner。

## Knowledge Sources

复用仓库 `poc/chunk-relay` 的实际 payload 和目标 TA 完成接口；固定 ns3 的 `ub-target-execution-test.cc`、`ub-node-test-fixture.h`、`ub-function.cc`、`ub-transport.cc` 作为 API 语义来源。检查了 ns3 AGENTS.md 与 openusim-plan-experiment/run-experiment 规则；该实验由显式用户授权，参数和边界先记录在 experiment-spec.md。没有引入未经验证的 UB 规范/硬件能力断言。

干净 checkout 复核：从实现提交 `985895b8b0a84a5b1d95dcc9595a62627837411f` 重新 clone，工作树干净；复用固定版本 ns3/tools 依赖，在独立 EVIDENCE 目录执行完整 run.sh。全部 PoC 与新测试通过，8 个案例的配置、输入、原始 assignment、事件和 summary 共 40 文件与原运行逐字节一致，SHA256 记录在 evidence/clean-checkout.json。本复核不是重新下载/重建所有依赖的离线安装测试。
