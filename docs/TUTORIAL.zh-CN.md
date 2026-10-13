# Nano-UB 自学指南：从 RoCE 到 UB

这份文档把 Nano-UB 当作一套**可运行的 UB 架构学习实验本**。它不试图
替代 UB 规范，也不把代码当成完整协议实现；它的目标是帮你建立一张清楚的
心智地图：

```text
RoCE 为什么以 QP 为中心？
UB 为什么拆成 Jetty、TP Channel、BTAH、RTPH/NTH？
Load/Store 旁路为什么能降低小操作延迟？
排序和可靠性到底在哪一层发生？
```

学习时请始终记住：

```text
Nano-UB = 教学级 SystemC 模型 + 架构实验
不是 bit-accurate UB/RoCE 实现
不是硬件综合结果
不是协议合规测试器
```

---

## 0. 先建立全局图

Nano-UB 里有三条主要路径：

```text
RoCE RC
  传统 RDMA 对照组，以 QP 为连接状态中心。

UB Load/Store
  小操作旁路路径，使用 TP_BYPASS，绕过完整传输层。

UB URMA
  完整异步路径，拆开本地应用状态、远端传输状态、事务语义和排序语义。
```

最重要的对比是：

```text
RoCE:
  QP = local endpoint + remote endpoint + reliable transport state
  状态趋势：O(local * remote)

UB:
  Jetty      = local endpoint / application state
  TP Channel = remote host transport state
  状态趋势：O(local + remote)
```

跑通项目：

```bash
cmake -B build
cmake --build build
bash scripts/test.sh
```

后面的章节会给出对应源码和测试入口；建议先顺着文字理解主线，
再按需要运行 `scripts/test.sh`、`scripts/compare.sh` 或 `scripts/microbench.sh`
查看证据。

---

## 1. Flit：不是协议格式，而是教学 IR

入口：

```text
include/nano/flit.h
tests/m01_flit.cpp
```

`flit` 作为概念，在网络、NoC、片上互连里很常见，通常表示 flow-control
digit，也就是内部流控/传输的小单位。

但 Nano-UB 里的 `struct Flit` 不是 UB 标准里的真实 flit，也不是 RoCE
真实 packet。它更像编译器里的 IR：

```text
真实协议概念
  READ / WRITE / SEND / ATOMIC
  PSN / TASSN / ODR / RTP / UTP / TP_BYPASS
  地址 / 长度 / 响应 / ACK

        ↓ 抽象成

Nano-UB Flit

        ↓ 被流水线模块读写
```

所以你看 `Flit` 不要问：

```text
这个字段在真实 UB 包里是第几 bit？
```

而要问：

```text
这个字段属于网络、传输、事务、排序中的哪一层？
哪个模块产生它？
哪个模块消费它？
如果没有它，哪种机制无法表达？
```

`Flit` 大致揉合了三层语义：

```text
网络/路由：
  src_addr, dst_addr, nlp

传输：
  psn, tpmsn, tp_opcode, syndrome

事务/排序：
  ta_opcode, tassn, odr, service_mode, fence, mem_addr, mem_len
```

实验：

```bash
./build/m01_flit
```

一句话记住：

```text
Flit 是 Nano-UB 的内部教学中间表示；
它让我们观察“协议语义如何在 NIC pipeline 中流动”。
```

---

## 2. EtherLink：两个 NIC 之间的最小实验环境

入口：

```text
include/nano/eth_link.h
src/eth_link.cpp
tests/m02_link.cpp
```

`EtherLink` 是教学用网线：

```text
Node A wire_tx ── delay/jitter/loss ──> Node B wire_rx
Node A wire_rx <── delay/jitter/loss ── Node B wire_tx
```

它只建模三件事：

| 参数 | 作用 |
|------|------|
| delay | 单向链路延迟 |
| jitter | 延迟抖动 |
| loss_rate | 丢包概率 |

它不建模真实以太网 MAC、CRC、PHY、速率限制、MTU、拥塞控制。

它的教学价值是把问题分层：

```text
Flit       = 传什么
EtherLink  = 两个 NIC 怎么相互送
Pipeline   = 协议逻辑如何改写/解释 Flit
```

实验：

```bash
./build/m02_link
```

---

## 3. RoCE TX：从 Host WR 到网络包

入口：

```text
include/nano/roce/tx.h
tests/m03_roce_tx.cpp
```

RoCE TX 路径：

```text
Host WR
  -> Doorbell
  -> QpTx
  -> BthBuilder
  -> RoceEncap
  -> wire_tx
```

### 3.1 QP、PSN、BTH 的关系

先记这句话：

```text
QP  = 这是谁和谁之间的连接状态
PSN = 这条连接上的包序号
BTH = 把 opcode、目标 QP、PSN 等写进包头
```

`QP` 是 RoCE RC 的连接上下文。真实 QP 里会有 send/recv queue 指针、
ACK/NAK、retry、RNR、路径、权限、CQ 关联等状态。Nano-UB 的教学模型里，
QP 状态主要简化成：

```text
TX: next_psn
RX: expected_psn
```

`PSN` 是每个 QP 独立的包序号空间，用来做可靠、有序接收和重传。

`BTH` 是 RoCE 的基础传输头，携带：

```text
opcode
destination QP
PSN
ACK request
其他传输控制信息
```

RoCE TX 可以概括为：

```text
Host WR 进入 QP 上下文；
QP 分配 PSN；
BTH 把 QP / PSN / opcode 写入包头；
Encap 后发到 wire_tx。
```

实验：

```bash
./build/m03_roce_tx
```

观察目标：一个 WRITE WR 如何经过 QP/PSN/BTH 变成 RoCE wire flit。

---

## 4. RoCE RX：以 QP 为中心的接收状态机

入口：

```text
include/nano/roce/rx.h
tests/m04_roce_pingpong.cpp
tests/m05_roce_read.cpp
tests/m06_roce_full.cpp
```

RoCE RX 路径：

```text
wire_rx
  -> RoceDecap
  -> QpRx
  -> BthParser
  -> Dispatch
  -> MemoryModel / RecvQueue / AtomicALU
  -> Completion / Response / ACK
```

核心是 `QpRx`：

```text
这个包属于哪条 QP 连接？
它的 PSN 是否等于 expected_psn？
如果是，接收并推进 expected_psn。
如果不是，真实协议会触发 NAK/重传等；教学模型里简化为丢弃。
```

`BthParser` 根据 BTH opcode 区分：

```text
WRITE
READ request
READ response
SEND
ACK
ATOMIC
```

`Dispatch` 再把操作交给：

```text
WRITE  -> MemoryModel
READ   -> MemoryModel 并生成 READ response
SEND   -> RecvQueue
ATOMIC -> AtomicALU
```

实验：

```bash
./build/m04_roce_pingpong
./build/m05_roce_read
./build/m06_roce_full
```

你要带着一个问题看 RoCE：

```text
为什么连接身份、可靠性、PSN 顺序和操作分发都围绕 QP 展开？
```

这个问题就是进入 UB 的门。

---

## 5. UB TX：两条入口，两种目标

入口：

```text
include/nano/ub/tx.h
tests/m07_ub_ls_tx.cpp
tests/m09_ub_urma_tx.cpp
```

UB TX 分两条路径。

### 5.1 Load/Store TX：TP_BYPASS 最短路径

```text
CPU Load/Store
  -> LsEngine
  -> BtahBuilder
  -> NthBuilder
  -> UbEncap
  -> wire_tx
```

这条路径的关键词是：

```text
TP_BYPASS
```

它绕过：

```text
Doorbell
JettyScheduler
OrderTrackerIni
TPG
TPChannelTx
RetransmitBuffer
RTPH/UTPH
```

它回答的是：

```text
小的同步 Load/Store 操作能不能不走完整 WR/CQE/PCIe DMA 路径？
```

实验：

```bash
./build/m07_ub_ls_tx
```

### 5.2 URMA TX：完整异步路径

```text
Host WR
  -> UbDoorbell
  -> JettyScheduler
  -> OrderTrackerIni
  -> BtahBuilder
  -> TpgGroup
  -> TpChannelTx
  -> CongestionWindow
  -> RetransmitBuffer
  -> RtphBuilder
  -> NthBuilder
  -> UbEncap
  -> wire_tx
```

这条路径回答的是：

```text
如果需要完整 RDMA 类语义，UB 如何组织本地状态、传输状态、事务语义和排序？
```

关键模块：

| 模块 | 架构意义 |
|------|----------|
| `JettyScheduler` | 本地应用端点，处理 WR 调度和 Fence |
| `OrderTrackerIni` | 发起端排序，处理 NO/RO/SO |
| `BTAH Builder` | 事务头，表达 READ/WRITE/SEND/ATOMIC/TASSN/ODR |
| `TpgGroup` | 为远端选择 TP Channel |
| `TpChannelTx` | 每远端传输状态，分配 PSN/TPMSN |
| `RetransmitBuffer` | 可靠传输保存副本 |
| `RtphBuilder` | 选择 RTP 或 UTP |
| `NthBuilder` | 标记 RTP/UTP/TP_BYPASS 等下一层协议 |

实验：

```bash
./build/m09_ub_urma_tx
```

一句话：

```text
RoCE 用 QP 包办本地端点 + 远端端点 + 传输可靠性；
UB 用 Jetty 表示本地端点，用 TP Channel 表示远端传输状态。
```

---

## 6. UB RX：先分流，再进入传输/事务/排序层

入口：

```text
include/nano/ub/rx.h
tests/m08_ub_ls_pingpong.cpp
tests/m10_ub_urma_e2e.cpp
```

UB RX 入口：

```text
wire_rx
  -> UbDecap
  -> NthParser
```

`NthParser` 是第一个关键分流点：

```text
NLP = TP_BYPASS
  -> 直接进入 BTAH / 事务层

NLP = RTP / UTP
  -> 先进入传输层
```

### 6.1 Load/Store RX

```text
UbDecap
  -> NthParser
  -> BtahParser
  -> UbMemory
  -> READ response if needed
```

这条路径是 Load/Store 低延迟路径的目标端一半。

### 6.2 URMA RX

```text
UbDecap
  -> NthParser
  -> RtphParser
  -> TpChannelRx
  -> PsnReorder
  -> BtahParser
  -> OrderTrackerTgt
  -> TransDispatch
  -> Memory / Atomic / Send
  -> CompletionGen
  -> CompletionReorder
  -> TaackGen
```

关键分层：

```text
NTH:
  网络分流，判断 TP_BYPASS / RTP / UTP

RTPH / TPChannel:
  传输可靠性，PSN、ACK/NAK、重传、重排

BTAH:
  事务语义，READ / WRITE / SEND / ATOMIC

OrderTracker:
  排序语义，ROI / ROT / SO 等

Dispatch:
  真正执行内存、SEND、Atomic
```

实验：

```bash
./build/m08_ub_ls_pingpong
./build/m10_ub_urma_e2e
```

---

## 7. UB READ/WRITE 的可靠性

UB 的可靠性要分两层：

```text
传输层可靠性：
  包有没有可靠送达？

事务层可靠性：
  READ / WRITE 这个操作有没有完成并可匹配？
```

普通 UB URMA READ/WRITE 走 RTP：

```text
TpChannelTx
  -> 分配 PSN / TPMSN
  -> RetransmitBuffer 保存副本
  -> RtphBuilder 标成 RTP_DATA

TpChannelRx
  -> 检查 expected PSN
  -> PsnReorder 恢复顺序
```

事务层再通过：

```text
BTAH
TASSN
RC / Jetty 身份
TAACK
READ_RESP
ATOMIC_RESP
```

来表达具体操作完成。

要区分两类确认：

```text
TPACK / TPNAK:
  传输层确认，说明包到没到。

TAACK / READ_RESP / ATOMIC_RESP:
  事务层确认，说明操作完成没完成。
```

Load/Store TP_BYPASS 在 Nano-UB 中是低延迟教学路径，当前假设链路可靠，
没有完整建模旁路路径的错误恢复、超时、异常上报。

---

## 8. RoCE BF、RoCE DMA 和 UB Load/Store

Nano-UB 的 `bench_full_latency` 有四个 host-visible 口径：

```text
ub_loadstore
ub_urma
roce_bf
roce_dma
```

RoCE DMA：

```text
PCIe MMIO doorbell
+ DMA read WQE
+ DMA write CQE
+ CQE polling
```

RoCE BF，即 BlueFlame 类路径，表示更快的 doorbell/inline 提交：

```text
PCIe MMIO doorbell
+ DMA write CQE
+ CQE polling
```

它省掉了：

```text
DMA read WQE
```

但它仍然没有消除 PCIe/CQE/polling 成本。UB Load/Store 则建模为：

```text
片上总线 30 ns * 2
```

运行：

```bash
./build/bench_full_latency --payload-bytes 64
```

当前 200 MHz 假设下：

```text
UB LoadStore: 440 ns
RoCE BF:      820 ns
RoCE DMA:     1320 ns
```

---

## 9. 分级排序：按需付费

入口：

```text
tests/m11_ub_ordering.cpp
bench/bench_micro.cpp
bench/bench_ordering_cost.cpp
```

UB 的排序不是固定协议属性，而是按需选择：

| 机制 | 教学模型中的位置 |
|------|------------------|
| Fence | `JettyScheduler` |
| ROI | `OrderTrackerIni` |
| ROT | `OrderTrackerTgt` |
| UNO | `TpChannelTx` / `RtphBuilder` |

运行：

```bash
./build/m11_ub_ordering
./build/bench_ordering_cost
bash scripts/microbench.sh
```

关注这些 CSV：

```text
eval/results/sc_tx_latency.csv
eval/results/sc_fence_cost.csv
eval/results/sc_so_blocking.csv
eval/results/sc_hol_blocking.csv
```

---

## 10. 状态规模：哪些是模型，哪些不是

运行：

```bash
./build/bench_state_size > state_size.csv
tail state_size.csv
```

非常重要：`state_size.csv` 是**纯数学/分析模型**，不是 SystemC 实测内存占用，
也不是真实硬件 SRAM/BRAM 结果。它使用固定对象大小假设来展示趋势：

```text
UB   = global + local * JettyBytes + remote * TpChannelBytes + MR
RoCE = global + local * remote * QpBytes + MR
```

它只能说明：

```text
UB   趋势为 O(local + remote)
RoCE 趋势为 O(local * remote)
```

不能证明真实 UB NIC 或真实 RoCE NIC 的具体 byte 数。

OpenURMA 的 state scaling 也是 analytical model，但它是“源码字段级分析模型”：
它按 `.clnp` 元素里的 Jetty、TP Channel、MR、QP 字段逐项加总。Nano-UB
当前版本是教学假设级分析模型。

---

## 11. 推荐学习顺序

如果你是第一次读，建议按这个顺序：

```text
1. Flit 是 IR，不是真实协议格式
2. EtherLink 是双节点实验环境
3. RoCE TX：Doorbell -> QP -> PSN -> BTH
4. RoCE RX：QpRx 作为可靠连接状态机
5. UB TX：LoadStore 旁路 vs URMA 完整路径
6. UB RX：NTH 分流，TPChannel 传输，BTAH 事务，OrderTracker 排序
7. READ/WRITE 可靠性：TPACK 和 TAACK 分层
8. microbench / latency / state_size 看三大主张
```

对应命令：

```bash
./build/m01_flit
./build/m02_link
./build/m03_roce_tx
./build/m05_roce_read
./build/m07_ub_ls_tx
./build/m08_ub_ls_pingpong
./build/m09_ub_urma_tx
./build/m10_ub_urma_e2e
./build/m11_ub_ordering
bash scripts/microbench.sh
./build/bench_full_latency --payload-bytes 64
./build/bench_state_size > state_size.csv
```

---

## 12. 当前模型边界

| 已建模 | 简化/缺失 |
|--------|-----------|
| RoCE 和 UB 的主要流水线 | bit-accurate 真实线缆格式 |
| QP/PSN/BTH 教学模型 | 完整 RoCE RC 状态机 |
| UB Load/Store TP_BYPASS | 完整旁路错误恢复和异常处理 |
| Jetty / TP Channel 分离 | 完整资源表、权限、安全、MR 检查 |
| Fence / ROI / ROT / UNO 基本行为 | 完整 ROL、完成排序、TAACK/TPACK 融合 |
| Go-Back-N 分析模型 | 完整重传、拥塞控制和 loss recovery 状态机 |

因此，Nano-UB 最适合用来学习：

```text
协议架构为什么这样拆
状态为什么这样伸缩
低延迟路径省在哪里
排序和可靠性分别在哪一层
```

而不是用来判断真实协议的所有边界行为。
