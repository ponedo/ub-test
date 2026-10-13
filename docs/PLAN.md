# 开发计划：增量式构建与验证

> 每步都是一个可编译、可运行、可验证的最小系统。
> 每步都在前一步基础上增量添加功能，不改动已验证部分。

---

## 概览

```
M00: SystemC 空转              ─── 工具链就绪
  │
M01: 基础类型 + flit              ─── 类型系统
  │
M02: EtherLink 链路模型            ─── 能"通信"了
  │
  ├─── M03: RoCE TX 最小路径       ─── 能发包了
  │       │
  │       M04: RoCE RX + ping-pong ─── 能收包了
  │       │
  │       M05: RoCE RDMA READ      ─── 双向操作
  │       │
  │       M06: RoCE 完整 RC        ─── 基线完成
  │
  └─── M07: UB Load/Store TX      ─── UB 旁路路径
          │
          M08: UB Load/Store ping-pong
          │
          M09: UB URMA TX 完整路径
          │
          M10: UB URMA 端到端
          │
          M11: UB 完整事务+排序
          │
          M12: 对比框架 + 验证
```

---

## M00 — SystemC 空转验证

**目标**：工具链通、SystemC 能跑、CMake 构建系统就绪。

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `CMakeLists.txt` | 顶层构建，找 SystemC 库 |
| 新建 | `src/main_empty.cpp` | 最小 SystemC 仿真入口 |
| 新建 | `env.sh` | 设置 SystemC 环境变量 |

### 实现

**`CMakeLists.txt`** — 找 SystemC 包，C++17 标准：

```cmake
cmake_minimum_required(VERSION 3.16)
project(nano-ub LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(SystemC REQUIRED)
add_executable(nano_empty src/main_empty.cpp)
target_link_libraries(nano_empty SystemC::systemc)
```

**`src/main_empty.cpp`** — 创建一个时钟，跑 100 周期后停止：

```cpp
#include <systemc.h>
SC_MODULE(ClockBlinker) {
    sc_in_clk clk;
    void tick() { std::cout << "@" << sc_time_stamp() << std::endl; }
    SC_CTOR(ClockBlinker) { SC_METHOD(tick); sensitive << clk.pos(); }
};
int sc_main(int, char*[]) {
    sc_clock clk("clk", 10, SC_NS);
    ClockBlinker cb("cb"); cb.clk(clk);
    sc_start(1000, SC_NS); // 100 个周期 × 10 ns
    return 0;
}
```

### 验证

```bash
source env.sh
cmake -B build && cmake --build build
./build/nano_empty
# 预期输出：@0 ns ... @990 ns 共 100 行，退出码 0
```

---

## M01 — 基础类型 + Flit 定义

**目标**：定义所有协议常量、位宽、枚举和内部 flit 数据结构，编译可通过。

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/common.h` | 公共类型、枚举、常量 |
| 新建 | `include/nano/flit.h` | 内部 flit 元数据定义 |
| 修改 | `CMakeLists.txt` | 添加头文件路径 |
| 新建 | `tests/test_flit.cpp` | flit 构造/字段读写单元测试 |

### 关键类型

```cpp
// include/nano/common.h — 枚举和常量
enum class NLP : uint8_t {
    TP_BYPASS = 0x01,
    RTP       = 0x10,  // 可靠传输
    UTP       = 0x11,  // 不可靠传输
};

enum class TPOpcode : uint8_t {
    UTP       = 0x00,
    RTP_DATA  = 0x01,
    TPACK     = 0x02,
    TPNAK     = 0x02,  // 同 0x02, RSPST 区分
    CNP       = 0x08,
};

enum class TAOpcode : uint8_t {
    SEND            = 0x00,
    WRITE           = 0x03,
    READ            = 0x06,
    ATOMIC_CAS      = 0x07,
    ATOMIC_SWAP     = 0x08,
    ATOMIC_STORE    = 0x09,
    ATOMIC_LOAD     = 0x0A,
    ATOMIC_FAA      = 0x0B,
    TAACK           = 0x11,
    READ_RESP       = 0x12,
    ATOMIC_RESP     = 0x13,
};

enum class ODR : uint8_t {
    NO = 0,  // 无序
    RO = 1,  // 相对有序
    SO = 2,  // 严格有序
};

// RoCE opcode
enum class RoCEOpcode : uint8_t {
    SEND_ONLY           = 0x04,
    RDMA_WRITE_ONLY     = 0x0A,
    RDMA_READ_REQUEST   = 0x0C,
    RDMA_READ_RESP      = 0x10,
    ACKNOWLEDGE         = 0x11,
    COMPARE_SWAP        = 0x13,
    FETCH_ADD           = 0x14,
};
```

```cpp
// include/nano/flit.h — 内部 flit 64B 元数据
#include <cstdint>
struct Flit {
    // Lane 0: 网络层摘要 (UB: NTH, RoCE: BTH 摘要)
    uint32_t dst_addr;    // DCNA[23:0] / DestQP[23:0]
    uint32_t src_addr;    // SCNA[23:0] / SrcQP
    uint8_t  nlp;         // NLP / opcode
    bool     valid;

    // Lane 1: 传输头字段
    uint32_t psn;         // PSN
    uint8_t  tp_opcode;   // TPOpcode / BTH opcode
    uint8_t  syndrome;    // RSPST / AETH syndrome

    // Lane 2: 标志位
    uint8_t  service_mode; // ROI/ROT/ROL/UNO
    bool     is_response;
    bool     is_last;      // A/F bit

    // Lane 3: 事务头字段
    uint8_t  ta_opcode;   // TAOpcode
    uint16_t tassn;       // INI_TASSN
    uint8_t  odr;         // ODR[1:0] 执行顺序标签
    uint32_t rc_id;       // INI_RC_ID

    // 扩展数据（地址/长度/操作数）
    uint64_t mem_addr;
    uint32_t mem_len;
    uint32_t rkey;
    uint64_t operand_a;   // swap/add
    uint64_t operand_b;   // compare (CAS only)
};
```

### 验证

```bash
cmake -B build && cmake --build build --target test_flit && ./build/test_flit
# 编译通过，单元测试全绿
```

---

## M02 — EtherLink 链路模型

**目标**：两个 NIC 之间通信的链路模型，可配置延迟/抖动/丢包，可独立验证。

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/eth_link.h` | EtherLink 头文件 |
| 新建 | `src/eth_link.cpp` | EtherLink 实现 |
| 新建 | `src/main_linktest.cpp` | 链路自测 |
| 修改 | `CMakeLists.txt` | 添加新目标 |

### 实现要点

```cpp
// EtherLink: 连接两个 NIC 的导线模型
SC_MODULE(EtherLink) {
    sc_fifo_in<Flit>  tx_from_a;   // NIC A 发出
    sc_fifo_out<Flit> rx_to_b;     // NIC B 接收
    sc_fifo_in<Flit>  tx_from_b;   // NIC B 发出
    sc_fifo_out<Flit> rx_to_a;     // NIC A 接收

    // 配置参数
    sc_time delay;       // 单向延迟
    double  jitter;      // 抖动 ±%
    double  loss_rate;   // 丢包率 0.0~1.0

    void forward(sc_fifo_in<Flit>& from, sc_fifo_out<Flit>& to);
    SC_CTOR(EtherLink) { /* 注册两个 SC_THREAD */ }
};
```

### 验证

```
NIC A (test)       EtherLink        NIC B (loopback)
  tx ───────────── delay τ ──────────→ rx
  rx ←─────────── delay τ ──────────── tx
```

- 发送 1000 个 flit，配置延迟 100 ns，确认接收端时间和 flit 内容正确
- 配置 10% 丢包，确认丢了 ~100 个
- 配置抖动，确认时间分布

---

## M03 — RoCE TX 最小路径

**目标**：主机提交一个 RDMA WRITE 工作请求，NIC 输出一个完整的 RoCEv2 线缆包。

### 元件链

```
Test WR Generator → Doorbell → QP TX → BTH Builder → Ethernet Encap → Wire sniffer
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/roce/tx.h` | RoCE TX 元件声明 |
| 新建 | `src/roce/doorbell.cpp` | Doorbell 实现 |
| 新建 | `src/roce/qp_tx.cpp` | QP TX 实现 |
| 新建 | `src/roce/bth_builder.cpp` | BTH Builder 实现 |
| 新建 | `include/nano/roce/eth_encap.h` | 以太网封装 |
| 新建 | `src/roce/eth_encap.cpp` | 以太网封装实现 |
| 新建 | `src/main_roce_tx.cpp` | TX 路径测试入口 |
| 修改 | `CMakeLists.txt` | 添加新目标 |

### 单步验证

```cpp
// Test WR: 构造一个 RDMA WRITE WR
auto wr = Flit{};
wr.ta_opcode = static_cast<uint8_t>(TAOpcode::WRITE);
wr.mem_addr  = 0x1000;  // 远端虚拟地址
wr.mem_len   = 64;      // 64 字节
wr.rkey      = 0x1234;
wr.valid     = true;

// 通过 Doorbell 注入
doorbell.wr_in.write(wr);

// 从 Wire sniffer 读输出
auto pkt = wire_out.read();
// 验证:
assert(pkt.valid);
assert(pkt.eth_type == 0x8915);  // RoCEv2 Ethertype
assert(pkt.udp_dport == 4791);
assert(pkt.bth_opcode == 0x0A);  // RDMA_WRITE_ONLY
assert(pkt.dest_qp == 1);
```

### 可打印输出

每走完一个元件，打印 flit 摘要，形成流水线可见的追踪日志。

---

## M04 — RoCE RX + ping-pong

**目标**：两套 RoCE NIC + EtherLink 互联，发起端 WRITE 数据到目标端，目标端 ACK 返回。

### 新增元件

```
RX: Ethernet Decap → QP RX → BTH Parser → Dispatch → Memory → Completion Gen → ACK/NAK Gen
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/roce/rx.h` | RoCE RX 元件声明 |
| 新建 | `src/roce/eth_decap.cpp` | 以太网解封装 |
| 新建 | `src/roce/qp_rx.cpp` | QP RX 实现 |
| 新建 | `src/roce/bth_parser.cpp` | BTH 解析器 |
| 新建 | `src/roce/dispatch.cpp` | 事务分发器 |
| 新建 | `src/roce/memory.cpp` | 模拟内存模型 |
| 新建 | `src/roce/completion.cpp` | 完成生成器 |
| 新建 | `src/roce/ack_gen.cpp` | ACK/NAK 生成器 |
| 新建 | `include/nano/roce/nic.h` | RoCE NIC 顶层组装 |
| 新建 | `src/roce/nic.cpp` | RoCE NIC 组装实现 |
| 新建 | `src/main_roce_pingpong.cpp` | 双节点 ping-pong 测试 |

### 验证场景

```
Node A                          Node B
  │                               │
  ├─ RDMA WRITE (64B, addr=0x1000) ─→ 接受、写入内存
  │                               ├─ 生成 ACK
  ←────── ACK (BTH+AETH) ─────────┤
  │                               │
  │  (检查 CQE 内容)               │  (检查内存 0x1000)
```

### 通过标准

1. Node B 内存 `0x1000` 读到正确的 64B 数据
2. Node A 收到 ACK，CQE 状态为成功
3. 打印端到端周期数

---

## M05 — RoCE RDMA READ

**目标**：在 M04 基础上增加 RDMA READ 请求/响应路径。

### 新增

- `Dispatch` 增加 READ 分支
- `Memory Read` 元件
- `Read Response` 路径（响应包走 TX 侧发回）
- 发起端处理 READ RESPONSE 完成

### 验证

```
Node A                          Node B
  │                               │
  ├─ RDMA READ (addr=0x2000, len=64) ─→ 读内存
  │                               ├─ 生成 Read Response
  ←──── Read Response + data ─────┤
  │                               │
  │  (检查 CQE + 数据 buffer)      │
```

---

## M06 — RoCE 完整 RC

**目标**：支持所有 RC opcode + Go-Back-N 重传 + DCQCN 拥塞控制。

### 新增

| 功能 | 文件 | 说明 |
|------|------|------|
| SEND/RECV | `src/roce/send_recv.cpp` | 双端消息 |
| Atomic CAS/FAA | `src/roce/atomic_alu.cpp` | 原子 ALU |
| GBN 重传 | `src/roce/retx.cpp` | 超时重传 |
| DCQCN | `src/roce/dcqcn.cpp` | ECN-based CC |

### 验证

- 各 opcode 端到端正确性测试
- 注入丢包，确认 GBN 重传恢复
- 打印窗口变化（DCQCN）

---

## M07 — UB Load/Store TX 最小路径

**目标**：开始 UB 实现。先做 §8.3 TP Bypass 路径——这是 UB 最简路径，也是 Pillar 2 的核心。

### 元件链

```
Load/Store Engine → BTAH Builder → NTH Builder → Ethernet Encap → Wire
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/ub/ls_engine.h` | Load/Store 引擎 |
| 新建 | `src/ub/ls_engine.cpp` | 实现 |
| 新建 | `include/nano/ub/btah_builder.h` | BTAH 构建器 |
| 新建 | `src/ub/btah_builder.cpp` | 实现 |
| 新建 | `include/nano/ub/nth_builder.h` | NTH 构建器 |
| 新建 | `src/ub/nth_builder.cpp` | 实现 |
| 新建 | `include/nano/ub/eth_encap.h` | UB 以太网封装 (Etype 0x88B5) |
| 新建 | `src/ub/eth_encap.cpp` | 实现 |
| 新建 | `src/main_ub_ls_tx.cpp` | TX 测试 |

### 验证

```cpp
ls_engine.addr_in.write({addr=0x1000, len=8, type=READ});
auto pkt = wire_out.read();
assert(pkt.nlp == 0x01);       // TP_BYPASS
assert(pkt.ethertype == 0x88B5);
assert(pkt.ta_opcode == 0x06); // Read
assert(pkt.mem_addr == 0x1000);
```

---

## M08 — UB Load/Store ping-pong

**目标**：双节点 Load/Store 往返，验证 Pillar 2 的延迟优势。

### 新增

``` 新增
RX: Ethernet Decap → NTH Parser → (TP_BYPASS) → BTAH Parser → Memory → Completion
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/ub/rx.h` | UB RX 元件 |
| 新建 | `src/ub/eth_decap.cpp` | 解封装 |
| 新建 | `src/ub/nth_parser.cpp` | NTH 解析/路由 |
| 新建 | `src/ub/btah_parser.cpp` | BTAH 解析 |
| 新建 | `include/nano/ub/nic.h` | UB NIC 顶层 |
| 新建 | `src/ub/nic.cpp` | 组装 |
| 新建 | `src/main_ub_ls_pingpong.cpp` | 双节点测试 |

### 验证

```
Node A                          Node B
  │                               │
  ├─ Load (addr=0x1000, 8B) ──────→ 读内存
  ←──── Read Response + data ─────┤
  │                               │
  │  端到端延迟 ≈ 16 周期 (≈80ns @200MHz)
```

---

## M09 — UB URMA TX 完整路径

**目标**：实现 UB 完整传输+事务 TX 路径（所有服务模式的最小版本）。

### 元件链

```
WR → Doorbell → Jetty Scheduler → Order Tracker(INI) → BTAH Builder → TPG
  → TP Channel TX → Congestion Window → Retransmit Buffer → RTPH Builder
  → NTH Builder → Ethernet Encap
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `src/ub/doorbell.cpp` | Doorbell |
| 新建 | `src/ub/jetty_sched.cpp` | Jetty 调度器 |
| 新建 | `src/ub/order_tracker_ini.cpp` | 发起端排序跟踪 |
| 新建 | `src/ub/tpg_group.cpp` | TPG 组 |
| 新建 | `src/ub/tp_channel_tx.cpp` | TP 通道 TX |
| 新建 | `src/ub/congestion_window.cpp` | 拥塞窗口 |
| 新建 | `src/ub/retx_buf.cpp` | 重传缓冲区 |
| 新建 | `src/ub/rtph_builder.cpp` | RTPH 构建器 |
| 新建 | `src/main_ub_urma_tx.cpp` | TX 测试 |

### 验证

- WR → wire 输出，检查 BTAH/RTPH/NTH 所有字段正确
- UNO 模式确认绕过 PSN 分配
- TP Bypass 确认门铃/Jetty 等被跳过

---

## M10 — UB URMA 端到端

**目标**：URMA Read/Write/Send 双节点互通。

### 新增 RX 元件

```
RX: Ethernet Decap → NTH Parser → RTPH Parser → TP Channel RX → PSN Reorder
  → BTAH Parser → Order Tracker(TGT) → MR Table → Transaction Dispatch
  → HBM Read/Write → Completion Gen → Completion Reorder → TAACK Gen
```

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `src/ub/rtph_parser.cpp` | RTPH 解析 |
| 新建 | `src/ub/tp_channel_rx.cpp` | TP 通道 RX |
| 新建 | `src/ub/psn_reorder.cpp` | PSN 重排序 |
| 新建 | `src/ub/order_tracker_tgt.cpp` | 目标端排序跟踪 |
| 新建 | `src/ub/mr_table.cpp` | 内存区域表 |
| 新建 | `src/ub/trans_dispatch.cpp` | 事务分发 |
| 新建 | `src/ub/hbm_memory.cpp` | HBM 内存模型 |
| 新建 | `src/ub/completion_gen.cpp` | 完成生成器 |
| 新建 | `src/ub/completion_reorder.cpp` | 完成重排序 |
| 新建 | `src/ub/taack_gen.cpp` | TAACK 生成器 |
| 新建 | `src/main_ub_urma_pingpong.cpp` | 双节点测试 |

### 验证

- RDMA Write：数据正确写入对端
- RDMA Read：数据正确读回
- Send/Recv：消息投递到 JFR
- 原子操作：CAS/Swap/FAA 结果正确

---

## M11 — UB 完整事务 + 分级排序

**目标**：实现四种服务模式（ROI/ROT/ROL/UNO）、三种执行标签（NO/RO/SO）、Fence、两种完成顺序。

### 新增/修改

| 功能 | 涉及元件 | 验证 |
|------|---------|------|
| ROI | Order Tracker Initiator | SO 等待未完成 RO |
| ROT | Order Tracker Target | SO 等待缺失 TASSN |
| ROL | TP Channel RX | TPACK 融合 TAACK |
| UNO | 全局 | 绕过所有排序状态 |
| Fence | Jetty Scheduler | Fence 位阻塞后续 WR |
| 完成顺序 | Completion Reorder | In-order vs out-of-order |

### 验证实验

```cpp
// 混合 NO/RO/SO 标签在同一 Jetty
jetty.submit(wr_no);   // 立即执行
jetty.submit(wr_ro);   // 在 NO 之后有序
jetty.submit(wr_so);   // 等待 RO 完成
// 验证只有 SO 付出额外门控延迟
```

---

## M12 — 对比框架 + 验证

**目标**：统一的 workload 驱动 + 指标采集 + 对照 OpenURMA 数据验证。

### 文件

| 新建/修改 | 文件 | 用途 |
|-----------|------|------|
| 新建 | `include/nano/harness.h` | 对比框架声明 |
| 新建 | `src/harness.cpp` | 框架实现 |
| 新建 | `src/bench_pingpong.cpp` | Ping-pong 延迟 |
| 新建 | `src/bench_throughput.cpp` | 吞吐量 |
| 新建 | `src/bench_state_sweep.cpp` | 状态伸缩 |
| 新建 | `src/bench_loss.cpp` | 丢包恢复 |
| 新建 | `src/bench_ordering.cpp` | 排序开销 (UB only) |
| 新建 | `src/main_comparison.cpp` | 一键运行所有实验 |

### 指标采集

```cpp
struct BenchResult {
    string label;
    double latency_ns;
    double throughput_gbps;
    size_t state_bytes;
    uint64_t cycles;
};
```

### 验证目标

| 指标 | OpenURMA | Nano-UB 目标 | 状态 |
|------|----------|-------------|------|
| Load/store 延迟 | 500 ns | ~500 ns ±10% | M08 |
| RoCE READ 延迟 | 2236 ns | ~2236 ns ±10% | M05 |
| UB/RoCE 延迟比 | 4.47× | ~4.47× ±10% | M12 |
| 状态缩减 (N=M=1024) | 4855× | ~4855× | M12 |

---

## 依赖图总览

```
M00 ─→ M01 ─→ M02 ─→ M03 ─→ M04 ─→ M05 ─→ M06
                      │
                      └→ M07 ─→ M08 ─→ M09 ─→ M10 ─→ M11
                                              │
M06 ──────────────────────────────────────────┼──→ M12
M11 ──────────────────────────────────────────┘
```

每个箭头表示"依赖前一步的元件和验证正确性"。

---

## 构建命令速查

```bash
# 构建全部
cmake -B build && cmake --build build

# 构建并运行特定里程碑
cmake --build build --target nano_empty         && ./build/nano_empty
cmake --build build --target test_flit           && ./build/test_flit
cmake --build build --target main_linktest       && ./build/main_linktest
cmake --build build --target main_roce_tx        && ./build/main_roce_tx
cmake --build build --target main_roce_pingpong  && ./build/main_roce_pingpong
cmake --build build --target main_ub_ls_tx       && ./build/main_ub_ls_tx
cmake --build build --target main_ub_ls_pingpong && ./build/main_ub_ls_pingpong
cmake --build build --target main_ub_urma_tx     && ./build/main_ub_urma_tx
cmake --build build --target main_ub_urma_pp     && ./build/main_ub_urma_pp
cmake --build build --target main_comparison     && ./build/main_comparison

# 运行所有测试
cmake --build build && ctest --test-dir build
```
