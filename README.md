> 入队顺序与公平性验证见 [报告](docs/ingress/REPORT.md)，可选入口 `--ingress-mode epoch-rr`；默认行为及 Phase 2 原始结果保留。

> 2026-10-13: 通用 WR Trace → SystemC → 统一评估已实现，见 [Phase 2 报告](docs/phase2/REPORT.md)，一键复现 `scripts/run_phase2.sh`。

> 2026-10-12: 可运行的 FIFO/RR/DRR SystemC 端到端实验见 [E2E_REPORT](docs/E2E_REPORT.md)，入口为 `scripts/run_e2e.sh`。下文保留原项目说明。

# Nano-UB

纯 SystemC 实现的华为 Unified Bus (UB) 与 RoCEv2 RC 开源模拟器，用于并排对比验证 UB 的三大架构主张：无连接状态伸缩、原生加载/存储延迟、分级排序。

---

## 目录结构

```
nano-ub/
├── CMakeLists.txt          # 顶层构建 (SystemC + C++17)
├── .gitignore
├── README.md
├── docs/                   # 设计文档与开发计划
│   ├── DESIGN.md           # 架构设计（英文）
│   ├── DESIGN.zh-CN.md     # 架构设计（中文）
│   ├── PLAN.md             # 增量式开发计划
│   └── RESULTS.md          # 基准测试结果
├── spec/                   # 协议规范（PDF）
│   ├── Annex17_RoCEv2.pdf
│   └── UB-Base-Specification-2.0.1-zh-clean.pdf
├── include/nano/           # 协议头部和类型定义
│   ├── common.h            # 公共常量与枚举
│   ├── flit.h              # 内部 flit 元数据（64 B）
│   ├── eth_link.h          # EtherLink 链路模型
│   ├── ub/
│   │   ├── tx.h            # UB TX 流水线元件
│   │   └── rx.h            # UB RX 流水线元件
│   └── roce/
│       ├── tx.h            # RoCE TX 流水线元件
│       └── rx.h            # RoCE RX 流水线元件
├── src/                    # 可执行文件入口
│   ├── eth_link.cpp        # EtherLink 实现
│   ├── main_*.cpp          # 各里程碑测试入口
│   └── bench_*.cpp         # 性能 benchmark
├── tests/
│   └── test_flit.cpp       # flit 单元测试
└── scripts/
    └── compare.sh           # 对比脚本
```

---

## 依赖

- **SystemC** ≥ 2.3.4 (Accellera)
- **C++17** 编译器 (GCC ≥ 9, Clang ≥ 10)
- **CMake** ≥ 3.16

在 Ubuntu/Debian 上安装 SystemC：

```bash
sudo apt install libsystemc-dev
```

---

## 构建

```bash
cmake -B build
cmake --build build
```

所有可执行文件输出到 `build/` 目录。

---

## 自学路线

如果你的目标是用这个项目自学 UB 协议，建议先读：

```text
docs/TUTORIAL.zh-CN.md
```

教程会按“Flit → 链路 → RoCE 对照组 → UB Load/Store →
UB URMA → 分级排序 → micro-benchmark”的顺序学习，而不是一上来陷进
所有源码细节。

---

## 运行

### 正确性测试

```bash
# 基础类型
./build/test_flit

# 链路模型
./build/main_linktest

# RoCE 管线
./build/main_roce_tx       # TX 路径
./build/main_roce_pingpong # 双节点 WRITE+ACK
./build/main_roce_read     # RDMA READ
./build/main_roce_full     # 完整 RC (SEND+CAS+FAA)

# UB 管线
./build/main_ub_ls_tx       # Load/Store TX
./build/main_ub_ls_pingpong # Load/Store 双节点
./build/main_ub_urma_tx     # URMA TX 完整路径
./build/main_ub_urma_pp     # URMA 端到端
./build/main_ub_ordering    # 排序 (Fence+ROI+ROT+UNO)
```

### 性能 Benchmark

```bash
./build/bench_full_latency --payload-bytes 64 # host-visible PCIe/片上总线口径
./build/bench_state_size       # 状态伸缩: UB O(local+remote) vs RoCE O(local*remote)
./build/bench_ordering_cost    # Fence/ROI/ROT/UNO 排序成本
./build/bench_loss_recovery    # Go-Back-N 丢包恢复模型
./build/bench_micro summary    # OpenURMA 风格 SystemC micro-benchmark
bash scripts/microbench.sh     # 生成 eval/results/sc_*.csv
bash scripts/compare.sh # 对比输出
```

---

## 架构概要

### 流水线模型

NIC 被建模为**有向处理元件图**，通过 FIFO 通道连接。每个元件是单用途处理块：从输入 FIFO 读 flit → 处理 → 写 flit 到输出 FIFO。

两种拓扑：

| 拓扑 | 元件数 | 说明 |
|------|--------|------|
| **UB** | ~40 | 传输/事务分离、4 服务模式、3 执行标签、旁路路径 |
| **RoCE** | ~20 | 标准 RC QP 模型 |

### 三大支柱

1. **状态分离**：NIC 状态按 O(local + remote) 而非 O(local × remote) 伸缩
2. **原生加载/存储**：片上总线绕过 PCIe，小操作延迟大幅降低
3. **分级排序**：排序保证按需选择，非传输协议固定属性

---

## 开发里程碑

| # | 里程碑 | 状态 |
|---|--------|------|
| M00 | SystemC 空转验证 | ✅ |
| M01 | 基础类型 + Flit | ✅ |
| M02 | EtherLink 链路模型 | ✅ |
| M03–M06 | RoCE RC 完整管线 | ✅ |
| M07–M08 | UB Load/Store 旁路路径 | ✅ |
| M09–M10 | UB URMA 传输层 + 端到端 | ✅ |
| M11 | UB 分级排序 | ✅ |
| M12 | 对比框架 | ✅ |

详情见 [docs/PLAN.md](docs/PLAN.md)。

---

## 参考

- *UB-Base-Specification 2.0.1* — 华为技术有限公司, 2025
- *InfiniBand Architecture Specification Volume 1, Release 1.5* — IBTA, 2024
- *OpenURMA* — Bojie Li, 2026. https://github.com/bojieli/OpenURMA
