# Nano-UB: 基准测试结果

> 生成日期：2026-06-24
> NIC 时钟频率假设：200 MHz（周期 = 5 ns）

---

## 1. Host-visible 延迟：UB vs RoCE

### 测试条件

| 参数 | 值 |
|------|------|
| 操作 | remote fetch / READ 64 字节 |
| 链路延迟 | 100 ns（单向） |
| 拓扑 | 双节点直连（EtherLink） |
| 口径 | NIC pipeline + PCIe/片上总线宿主接口模型 |

### 结果

| 协议栈 | NIC pipeline | 宿主接口开销 | **host-visible 合计** |
|--------|:-:|:-:|:-:|
| UB Load/Store | 76 cycles = 380 ns | 60 ns（片上总线×2） | **~440 ns** |
| UB URMA | 80 cycles = 400 ns | 970 ns（MMIO+DMA读WQE+DMA写CQE+轮询） | **~1370 ns** |
| RoCE BF | 70 cycles = 350 ns | 470 ns（MMIO+DMA写CQE+轮询） | **~820 ns** |
| RoCE DMA | 70 cycles = 350 ns | 970 ns（MMIO+DMA读WQE+DMA写CQE+轮询） | **~1320 ns** |

Nano-UB 的 host-visible 模型在 200 MHz 假设下给出：

| 对比 | 比值 |
|------|------|
| RoCE DMA / UB LoadStore | **3.00×** |
| RoCE BF / UB LoadStore | **1.86×** |

> 该结果不再试图复刻 OpenURMA 的 headline 数字；当前目标是
> 在 Nano-UB 自己的 200 MHz 假设下保持 cycle/ns/throughput 口径一致。

### 分析

NIC pipeline 数字以 cycle 为主，ns 值由 200 MHz 统一换算得出。当前 MVP
中的主要阶段成本如下：

| 元件 | 周期 | 说明 |
|------|:-:|------|
| 一般元件 | 1 cy = 5 ns | LsEngine, BtahBuilder, Doorbell, QpTx 等 |
| UB Eth Encap | 11 cy | 较长的 UB 头部组帧（NTH+RTPH+BTAH） |
| RoCE Eth Encap | 4 cy | 较短的 RoCE 头部（BTH） |
| UbMemory | 4 cy | DRAM 访问延迟 |

OpenURMA 的 500 ns / 2236 ns 由 `twonode_sim`（`transport_analytical.cpp`）产生，这是一个**分析型时序模型**，额外包含了：

| 参数 | UB ld/st | RoCE DMA | 来源 |
|------|:-:|:-:|------|
| PCIe MMIO 门铃 | **0** | **150 ns** | CPU→NIC doorbell BAR 写 |
| PCIe DMA 读 WQE | **0** | **500 ns** | NIC→主机内存取 WQE |
| PCIe DMA 写 CQE | **0** | **250 ns** | NIC→主机内存写完成事件 |
| 片上总线 | **30 ns** | 0 | UB 独占优势 |
| CQE 轮询 | 0（寄存器） | 70 ns（主机 DRAM） | |

在当前 Nano-UB 参数中，RoCE DMA 的宿主接口开销为 **970 ns**，UB
Load/Store 的片上总线开销为 **60 ns**。UB 的 pipeline 比 RoCE 多
约 **30 ns**（380 ns vs 350 ns），但宿主接口少 **910 ns**，因此
200 MHz host-visible 口径下仍得到 **3.00×** 的端到端优势。

---

## 2. OpenURMA 风格 micro-benchmark

新增 `bench_micro` 和 `scripts/microbench.sh`，输出 OpenURMA
`eval/sc_microbench.sh` 风格的 CSV：

```bash
bash scripts/microbench.sh
```

生成：

| 文件 | 内容 |
|------|------|
| `eval/results/sc_tx_latency.csv` | ROI/ROT/ROL/UNO × NO/RO/SO TX latency |
| `eval/results/sc_throughput.csv` | 各 service mode 吞吐 |
| `eval/results/sc_per_element.csv` | TX pipeline per-element latency |
| `eval/results/sc_fence_cost.csv` | Fence 随 pending reads 的成本 |
| `eval/results/sc_so_blocking.csv` | SO 被 outstanding RO 阻塞的成本 |
| `eval/results/sc_payload.csv` | payload size sweep |
| `eval/results/sc_hol_blocking.csv` | HOL blocking smoke |

`bench_micro` 也支持单项运行：

```bash
./build/bench_micro tx_latency ROI SO
./build/bench_micro throughput UNO
./build/bench_micro payload 4096
./build/bench_micro per_element
```

---

## 3. 已补充的 OpenURMA 对齐评估

新增 `include/nano/eval/latency_model.h`，把 Nano-UB 结果拆成两个口径：

| 口径 | 含义 | 对应程序 |
|------|------|----------|
| micro-benchmark | TX latency、throughput、per-element、payload 等 | `bench_micro` |
| host-visible latency | NIC pipeline + PCIe/MMIO/DMA/CQE/片上总线 | `bench_full_latency` |

默认参数：

| 参数 | 值 |
|------|----|
| PCIe MMIO doorbell | 150 ns |
| PCIe DMA 读 WQE | 500 ns |
| PCIe DMA 写 CQE | 250 ns |
| CQE polling | 70 ns |
| UB 片上总线 | 30 ns/次 |

运行：

```bash
./build/bench_full_latency --payload-bytes 64
```

输出同时包含：

| 栈 | 说明 |
|----|------|
| `ub_loadstore` | UB §8.3 Load/Store，片上总线入口 |
| `ub_urma` | UB 异步 URMA，仍走 WR/CQE 类接口 |
| `roce_bf` | RoCE BlueFlame 类路径：MMIO + CQE |
| `roce_dma` | 传统 RoCE DMA 路径：MMIO + WQE DMA + CQE DMA + polling |

## 4. 状态规模、排序和丢包恢复

新增三个轻量评估入口：

```bash
./build/bench_state_size       # UB O(local+remote) vs RoCE O(local*remote)
./build/bench_ordering_cost    # NO/RO/SO/Fence/UNO/RTP 成本
./build/bench_loss_recovery    # Go-Back-N 丢包恢复分析
```

这些程序用于补足三类原先只在文档中描述、没有量化输出的主张：

| 主张 | 新增量化 |
|------|----------|
| 无连接状态伸缩 | `bench_state_size` 输出 local/remote 扫描 CSV |
| 分级排序 | `bench_ordering_cost` 输出 mean/p99/throughput |
| 可靠传输恢复 | `bench_loss_recovery` 输出 loss rate、重传数、goodput |

### 状态规模模型的口径

`bench_state_size` 是**纯数学/分析模型**，不是 SystemC 仿真测量值，也不是
真实 NIC SRAM/BRAM 占用。它只用于展示 UB 和 RoCE 的状态伸缩趋势：

```text
UB   = global + local_endpoints * JettyBytes
             + remote_hosts * TpChannelBytes
             + memory_regions * MrBytes

RoCE = global + local_endpoints * remote_hosts * QpBytes
             + memory_regions * MrBytes
```

当前假设的对象大小写在 `include/nano/eval/latency_model.h`：

| 对象 | 假设大小 |
|------|----------|
| Jetty | 96 B |
| TP Channel | 160 B |
| MR | 64 B |
| RoCE QP | 224 B |
| Global state | 4096 B |

因此 `state_size.csv` 只能说明：

```text
UB   趋势为 O(local + remote)
RoCE 趋势为 O(local * remote)
```

它不能证明真实 UB NIC 或真实 RoCE NIC 的具体 byte 数。

---

## 5. 两种仿真方式对比

| 维度 | Nano-UB（当前） | OpenURMA twonode | 差异 |
|------|---------------|-----------------|------|
| 流水线元件 | 真实跑 SystemC 元件 | 不跑元件，用阶段累加 | Nano-UB 更精确 |
| 每周期延迟 | 200 MHz 假设下换算为 5 ns/cycle | 使用其自己的评估频率与阶段模型 | 两者频率假设不同 |
| PCIe 模型 | 已有 host-visible 参数模型 | 参数化（150/500/250 ns） | 口径已可对齐 |
| 仿真速度 | 快（无 wait） | 慢（有 wait） | 各有取舍 |

后续若要进一步逼近 OpenURMA 的绝对数值，需要把 host-visible 参数模型
从分析程序下沉为 SystemC `HostInterface` 模块，并让每个请求在仿真中真实
经过 MMIO、DMA、CQE 和片上总线阶段。

---

## 6. 运行方法

```bash
# 运行单个 benchmark
./build/bench_full_latency --payload-bytes 64
./build/bench_micro summary
bash scripts/microbench.sh
./build/bench_state_size > state_size.csv
./build/bench_ordering_cost
./build/bench_loss_recovery

# 运行对比脚本
bash scripts/compare.sh
```

---

## 7. 通过的正确性测试

| 目标 | 测试内容 | 状态 |
|------|---------|------|
| `m01_flit` | Flit 构造、字段读写、ODR 标签 | ✅ 通过 |
| `m02_link` | EtherLink 延迟/丢包/确定性 | ✅ 通过 |
| `m03_roce_tx` | RoCE TX：WR→wire（RDMA WRITE） | ✅ 通过 |
| `m04_roce_pingpong` | RoCE 双节点 WRITE+ACK 往返 | ✅ 通过 |
| `m05_roce_read` | RoCE RDMA READ 端到端 | ✅ 通过 |
| `m06_roce_full` | RoCE 完整 RC（SEND+CAS+FAA） | ✅ 通过 |
| `m07_ub_ls_tx` | UB Load/Store TX | ✅ 通过 |
| `m08_ub_ls_pingpong` | UB Load/Store 双节点 | ✅ 通过 |
| `m09_ub_urma_tx` | UB URMA TX 完整路径 | ✅ 通过 |
| `m10_ub_urma_e2e` | UB URMA 端到端（READ+响应回传） | ✅ 通过 |
| `m11_ub_ordering` | UB 排序（Fence+ROI+ROT+UNO） | ✅ 通过 |
| `bench_full_latency` | host-visible 延迟模型 | ✅ 通过 |
| `bench_micro` | OpenURMA 风格 micro-benchmark | ✅ 通过 |
| `bench_state_size` | 状态伸缩 CSV | ✅ 通过 |
| `bench_ordering_cost` | 排序成本模型 | ✅ 通过 |
| `bench_loss_recovery` | Go-Back-N 丢包恢复模型 | ✅ 通过 |
