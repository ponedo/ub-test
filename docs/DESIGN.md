# Nano-UB: A Pure SystemC Open Implementation of UB and RoCEv2

**Design Document**
2026-06-24

> This document describes the architecture, wire format, and evaluation
> methodology for a clean-room SystemC implementation of Huawei's Unified
> Bus (UB) transport and transaction layers, alongside a matched RoCEv2 RC
> baseline. The goal is a side-by-side comparison that reproduces the
> architectural claims of UB — connectionless state scaling, native
> load/store latency, and graded ordering — without depending on any
> hardware description language compiler or FPGA toolchain.

---

## 1. Framing

### 1.1 The motivation

Huawei's Unified Bus (UB) Specification 2.0.1 defines a connectionless,
transaction-decoupled RDMA-class transport that attacks two structural
costs of traditional RDMA: the O(N·M) connection-state explosion of
per-pair Queue Pairs, and the four-PCIe-traversal latency tax on small
operations. UB ships in Huawei's closed Ascend 950 silicon, and an open
FPGA implementation exists (OpenURMA, built on OpenClickNP), but there is
no toolchain-independent, pure-simulation implementation that a researcher
can study, modify, and extend without committing to a specific FPGA
compiler.

Nano-UB fills this gap: a **pure SystemC** implementation of both UB and
RoCEv2 RC, designed from the start for side-by-side comparison on
identical workloads and evaluation infrastructure.

### 1.2 What this project is (and is not)

| Is | Is not |
|----|--------|
| A cycle-level SystemC simulator of UB's transport/transaction layers | A synthesisable RTL design |
| A matched RoCEv2 RC baseline on the same simulation infrastructure | A production NIC driver stack |
| A toolchain-independent reference that needs only SystemC + C++17 | A drop-in replacement for OpenURMA's FPGA bitstream |
| A framework for measuring the UB-vs-RoCE architectural trade | A full UB link-layer or security implementation |

### 1.3 Three architectural pillars

The project exists to defend the same three architectural claims that
motivate UB and OpenURMA:

1. **Transport/transaction split.** NIC state grows as O(local endpoints) +
   O(remote hosts) rather than O(local × remote). This is the mechanism
   that bounds NIC working-set size.

2. **Native load/store latency.** With bounded state fitting on-chip, the
   controller sits on the CPU's on-chip bus instead of behind PCIe,
   collapsing four PCIe traversals into one on-chip-bus crossing for
   small synchronous operations.

3. **Graded ordering.** Ordering guarantees are opt-in per operation, not
   a fixed property of the transport. Four service modes × three execution
   tags × application Fence × two completion-order modes let applications
   pay gating cost only when they ask for it.

These three form a dependency chain: (1) enables (2) by bounding state,
and (3) rides on the per-application counters that (1) provisions.

---

## 2. Architecture

### 2.1 The element-graph model

The NIC is modelled as a directed graph of **processing elements**
connected by FIFO channels. Each element is a single-purpose processing
block: it reads flits from its input FIFOs, performs a specific protocol
function, and writes flits to its output FIFOs. There is no shared state
between elements beyond what passes through the FIFOs — the dataflow
exposes the protocol's inherent parallelism.

Two topologies are defined:

- **UB topology**: approximately 40 elements implementing the full
  transport/transaction split, four service modes, three execution tags,
  load/store bypass path, and Go-Back-N retransmit.
- **RoCE topology**: approximately 20 elements implementing the standard
  RC Queue-Pair model with per-QP PSN state, BTH/RETH/AETH/AtomicETH
  headers, and GBN retransmit.

Both topologies share the same wire-link model, the same host-interface
abstraction, and the same evaluation harness — only the protocol changes.

### 2.2 UB topology

#### TX path (host work-request → wire packet)

```
Host work-request
    │
    ▼
Doorbell ─── validates incoming WR, strips flit framing
    │
    ▼
Jetty Scheduler ─── round-robin WR dispatch, Fence gating (§7.3.2.2)
    │
    ▼
Order Tracker (Initiator) ─── ROI-mode SO gating (§7.3.3.2)
    │
    ▼
BTAH Builder ─── stamps transaction header (opcode, ODR, INI_RC_ID)
    │
    ▼
TPG Group ─── selects a TP Channel from the pool (§6.4.3)
    │
    ▼
TP Channel TX ─── allocates PSN/TPMSN, maintains per-host transport state
    │
    ▼
Congestion Window ─── LDCP window (advisory in MVP, §6.6)
    │
    ▼
Retransmit Buffer ─── holds in-flight copy for GoBackN retransmit
    │
    ▼
RTPH Builder ─── stamps transport header (PSN, TPOpcode, RSPST)
    │
    ▼
NTH Builder ─── stamps network header (24-bit CNA, NLP)
    │
    ▼
Ethernet Encap ─── wraps in Ethernet frame (Ethertype 0x88B5)
    │
    ▼
Wire output
```

For UNO-mode (unreliable) traffic, the TP Channel sets metadata flags so
the pipeline uses UTPH instead of RTPH, bypassing PSN allocation and the
retransmit buffer.

For §8.3 load/store (TP Bypass) traffic, the host-facing ingress is
replaced by a Load/Store Engine that sends flits directly to BTAH Builder
with NLP = TP_BYPASS, skipping the entire transport layer.

#### RX path (wire packet → host completion)

```
Wire input
    │
    ▼
Ethernet Decap ─── strips Ethernet header
    │
    ▼
NTH Parser ─── routes by NLP: RTP (port 1) vs UTP (port 2) vs TP_BYPASS
    │
    ▼
RTPH Parser ─── splits data packets vs ACK packets; Congestion Echo
    │            emits CNP on FECN
    ▼
TP Channel RX ─── per-host receiver: PSN window validation, ROL fusion
    │
    ▼
PSN Reorder ─── out-of-order reassembly buffer
    │
    ▼
BTAH Parser ─── splits requests (port 1) from responses (port 2)
    │
    ▼
Order Tracker (Target) ─── ROT-mode SO gating, TASSN scoreboard (§7.3.3.3)
    │
    ▼
MR Table ─── memory-region lookup and token-ID verification (§8.2.4)
    │
    ▼
Transaction Dispatch ─── branches by opcode:
    ├── Read    → HBM Read
    ├── Write   → HBM Write
    ├── Atomic  → Atomic ALU (CAS/Swap/FAA/FSUB/FAND/FOR/FXOR)
    └── Send    → Jetty Group → Jetty Recv (deliver to JFR)
    │
    ▼
Completion Generator ─── flips request to ATAH response
    │
    ▼
Completion Reorder ─── in-order vs out-of-order completion buffer (§7.3.2.3)
    │
    ▼
TAACK Generator ─── builds transaction ACK (ROI/ROT); ROL fuses
    │               into TPACK; UNO is dropped
    ▼
(Routed back through TX merge as a response packet)
```

Responses arriving on the initiator side (TPACK/TPNAK/TPSACK) are routed
into the Completion Stream, which surfaces host-visible CQEs.

### 2.3 RoCE topology

#### TX path

```
Host work-request
    │
    ▼
Doorbell ─── validates and forwards WR
    │
    ▼
QP TX ─── per-QP PSN allocation, src/dest QPN stamping (§9.7.4)
    │         Each (local QP) has its own PSN sequence space — this is
    │         the canonical RC behaviour and the source of O(N·M) scaling.
    ▼
BTH Builder ─── stamps standard BTH fields (tver, padcnt, opcode, pkey)
    │
    ▼
Retransmit Buffer ─── holds in-flight WQEs for GBN retransmit
    │
    ▼
Ethernet Encap ─── wraps in UDP/IPv4 + Ethernet (Ethertype 0x8915, UDP 4791)
    │
    ▼
Wire output
```

#### RX path

```
Wire input
    │
    ▼
Ethernet Decap ─── strips UDP/IPv4 + Ethernet headers
    │
    ▼
QP RX ─── per-QP PSN validation, ordering, ACK generation (§9.7.5)
    │
    ▼
BTH Parser ─── extracts opcode, routes to dispatch
    │
    ▼
Dispatch ─── branches by opcode:
    ├── RDMA READ      → Memory Read
    ├── RDMA WRITE     → Memory Write
    ├── ATOMIC_CAS/FAA → Atomic ALU
    ├── SEND           → Recv queue
    └── ACK/NAK        → QP TX ACK processing
    │
    ▼
Completion Generator ─── builds CQE
    │
    ▼
ACK/NAK Generator ─── builds BTH+AETH response
    │
    ▼
(Routed back through TX merge)
```

### 2.4 The three architectural pillars in the graph

**Pillar 1 (state split)** is visible as separate tables that scale on
different axes:

| Table | Scales with | UB | RoCE |
|-------|-------------|----|------|
| Jetty/endpoint table | Local applications | 1 per app | — |
| TP Channel / QP table | Remote hosts | 1 per host | 1 per peer pair |
| MR table | Registered segments | 1 per segment | 1 per segment |

Because UB decouples the Jetty table (per-application) from the TP Channel
table (per-host), total NIC state is O(local endpoints + remote hosts).
RoCE fuses both identities into a single QP object, so state is
O(local × remote).

**Pillar 2 (load/store latency)** is realised by the Load/Store Engine
ingress that replaces the doorbell/Jetty/OrderTracker/TPChannel chain with
a direct on-chip-bus-to-BTAH path. The UB TX path completes in ~8 cycles
for this path versus ~25 cycles for the full URMA-async path.

**Pillar 3 (graded ordering)** is spread across the gating elements:
Jetty Scheduler (Fence), Order Tracker Initiator (ROI), Order Tracker
Target (ROT), TP Channel RX (ROL fusion), and Completion Reorder
(completion order). Each corresponds to one axis of the §7.3 surface.

### 2.5 Host interface abstraction

Both topologies expose a uniform host interface:

```
wr_in      →  host submits work-request flits
cqe_out    ←  NIC emits completion-event flits
wire_tx    →  flits emitted to the network link
wire_rx    ←  flits arriving from the network link
```

The UB topology additionally exposes a load/store port for §8.3 operations
that bypass the WR/CQE machinery entirely — the CPU's memory request goes
directly to the Load/Store Engine and a response returns as a memory-read
result.

### 2.6 Wire link model

The two NIC instances are connected by an EtherLink model that introduces
configurable delay, jitter, and optional packet loss:

```
NIC A          EtherLink           NIC B
wire_tx ────┬───────────┬──── wire_rx
            │  delay τ  │
wire_rx ←───┴───────────┴──── wire_tx
```

The link model is independent of the protocol — the same link connects
UB NICs, RoCE NICs, or mixed-protocol pairs.

---

## 3. Wire Format

### 3.1 UB wire format

UB packets are encapsulated in standard Ethernet frames. The wire layout
per packet is:

```
+------------+------------+------------+------------+
| Ethernet   | NTH        | TPH        | TAH        |
| 14 B       | 12 B       | 16 B       | 16 B       |
+------------+------------+------------+------------+
| Ext TAHs   | Payload (variable)                   |
+------------+--------------------------------------+
```

**Ethernet header** (14 B): dst_mac (6) | src_mac (6) | ethertype (2).
Ethertype = 0x88B5 (local experimental).

**NTH — Network Transport Header** (§5.2.2, 12 B): carries 24-bit CNA
network-layer addressing. Key fields:

```
Byte 0:       RT[1:0] | reserved[5:0]
Bytes 1-3:    SCNA[23:0]       — source CNA
Bytes 4-6:    DCNA[23:0]       — destination CNA
Bytes 7-8:    CCI[15:0]        — congestion control identifier
Byte 9:       LBF[7:0]         — load-balancing field
Byte 10:      SL[3:0] | NLP[2:0] | mgmt[1]
Byte 11:      reserved
```

NLP values:
- 0x010 = RTPH follows (reliable transport)
- 0x011 = UTPH follows (unreliable transport, OpenURMA convention)
- 0x001 = TP Bypass (§8.3 load/store, no transport header)

**RTPH — Reliable TP Header** (§6.2.1, 16 B):

```
Byte 0:       TPOpcode[7:0]
Byte 1:       TPVer[1:0] | Padding[1:0] | NLP[3:0]
Bytes 2-4:    SrcTPN[23:0]
Bytes 5-7:    DstTPN[23:0]
Byte 8:       A[1] | F[1] | reserved[5:0]
Bytes 9-11:   PSN[23:0]           — packet sequence number
Byte 12:      RSPST[2:0] | RSPINFO[4:0]
Bytes 13-15:  TPMSN[23:0]         — transport message sequence number
```

TPOpcode values: 0x00 = UTP, 0x01 = RTP data, 0x02 = TPACK/TPNAK,
0x03 = TPACK-CC, 0x05 = TPSACK, 0x06 = TPSACK-CC, 0x08 = CNP.
Bit 7 marks the last packet of a transaction.

**UTPH — Unreliable TP Header** (§6.2.1, 16 B): Minimal header with
TPOpcode[0]=0, no PSN or retransmit fields.

**BTAH — Base Transaction Header** (§7.2.1, 16 B):

```
Byte 0:       TAOpcode[7:0]
Byte 1:       TAver[1:0] | EE_bits[1:0] | TV_EN | Poison | Target_Hint | UD_Flag
Bytes 2-3:    INI_TASSN[15:0]     — transaction sequence number
Byte 4:       No_TAACK | ODR[2:0] | MT_EN | FCE | Retry | Alloc
Byte 5:       E_bit | INI_RC_Type[1:0] | reserved
Bytes 8-10:   INI_RC_ID[19:0]     — initiator resource identifier
```

TAOpcode values cover 18 transaction types: Send (0x00), Write (0x03),
Read (0x06), all eight atomic opcodes (0x07-0x0F), TAACK (0x11),
Read Response (0x12), Atomic Response (0x13), and management opcodes.

ODR[1:0] encodes the execution-order tag (00 = NO, 01 = RO, 10 = SO).
ODR[2] selects in-order completion notification.

**MAETAH — Memory Address Extension TAH** (§7.2.3, 16 B): carries
64-bit address, 20-bit token ID, and 32-bit length for Read/Write/Atomic
operations.

**ATAH — ACK Transaction Header** (§7.2.2, 16 B): response header
mirroring BTAH fields with RSPST/RSPINFO status codes.

### 3.2 RoCE wire format

RoCEv2 packets are encapsulated in UDP/IPv4 over Ethernet (IBTA §9.3).

```
+------------+----------+----------+------------+------------+
| Ethernet   | IPv4     | UDP      | BTH        | RETH/AETH/ |
| 14 B       | 20 B     | 8 B      | 12 B       | AtomicETH  |
+------------+----------+----------+------------+------------+
| Payload (variable)                                       |
+----------------------------------------------------------+
```

Ethertype = 0x8915, UDP destination port = 4791.

**BTH — Base Transport Header** (12 B):

```
Bytes 0-1:    Opcode[7:0] | TVer[3:0] | PadCnt[1:0] | SE | M | reserved
Bytes 2-3:    PKey[15:0]
Bytes 4-7:    DestQP[23:0] | A | reserved
Bytes 8-11:   PSN[23:0] | reserved
```

RC opcodes include: SEND_ONLY (0x04), RDMA_WRITE_ONLY (0x0A),
RDMA_READ_REQUEST (0x0C), RDMA_READ_RESPONSE_ONLY (0x10),
ACKNOWLEDGE (0x11), COMPARE_SWAP (0x13), FETCH_ADD (0x14).

**RETH — RDMA Extended Transport Header** (16 B): virtual address (8 B),
rkey (4 B), DMA length (4 B). Present on RDMA WRITE and READ requests.

**AETH — ACK Extended Transport Header** (4 B): syndrome byte indicating
ACK (0x00), RNR-NAK (0x20), or various NAK reasons (0x60-0x63),
followed by 3 reserved bytes.

**AtomicETH** (28 B): virtual address (8 B), rkey (4 B), swap/add
operand (8 B), compare operand (8 B).

### 3.3 Internal flit format

Inside the simulator, each packet is represented as a fixed-size metadata
record carrying the parsed header fields in a compact bit-packed layout.
The conversion between wire bytes and internal metadata is the
responsibility of the Ethernet Encap/Decap elements at the topology
boundary.

The metadata record is 64 bytes, organised as four 64-bit lanes:

| Lane | UB content | RoCE content |
|------|-----------|-------------|
| 0 | NTH summary (DCNA, SCNA, NLP, valid) | BTH summary (opcode, pkey, dest_qp) |
| 1 | RTPH fields (TPOpcode, PSN, TPMSN) | PSN, syndrome, flags |
| 2 | Flags (service mode, response, A/F) | Src QP, rkey |
| 3 | BTAH fields (TAOpcode, TASSN, ODR, RC_ID) | Cookies, internal routing |

A second "extension" record follows for operations carrying address,
length, token, or atomic operand data.

---

## 4. Evaluation Methodology

### 4.1 The comparison: UB vs RoCE

Every experiment is run twice — once on the UB topology and once on the
RoCE topology — with identical workload parameters. The only variable is
the protocol. This mirrors the OpenURMA evaluation strategy.

### 4.2 Measured dimensions

**Pillar 1 — State scaling:**

NIC-resident state is measured as the sum of per-connection context
across both tables:

```
State(N, M) = Σ(element_state) × cardinality(element, N, M)
```

| Element | UB cardinality | RoCE cardinality |
|---------|---------------|------------------|
| TP Channel / QP | M (remote hosts) | N × M (local × remote) |
| Jetty / endpoint | N (local apps) | N × M (fused into QP) |
| MR segment | per registration | per registration |

For N = M = 1024 full-mesh, the ratio should approach ~O(N·M)/O(N+M)
≈ 4855×.

**Pillar 2 — End-to-end latency:**

Each operation's path is decomposed into segments:

| Segment | UB load/store | UB URMA | RoCE |
|---------|--------------|---------|------|
| Host post | 0 (ISA ld/st) | membus traversal | PCIe MMIO + DMA |
| NIC TX | ~8 cycles | ~25 cycles | ~9 cycles |
| Wire | configurable delay | configurable delay | configurable delay |
| NIC RX + remote memory | ~8 cycles | ~25 cycles | ~9 cycles + PCIe |
| Completion | 0 (direct return) | membus + CQE poll | PCIe DMA CQE + host poll |

The headline measurement: a 64-byte remote fetch at a 200 MHz NIC clock,
comparing UB load/store latency against RoCE RDMA READ latency.

**Pillar 3 — Graded ordering:**

Four experiments probe each ordering axis:
1. ROI: SO gates behind outstanding RO on the same Initiator
2. ROT: Target defers SO until missing TASSN arrives
3. ROL: TPACK fuses TAACK, saving a wire flit
4. UNO: Unreliable mode bypasses all ordering state

Cross-experiment: NO/RO/SO tags mixed on the same Jetty, verifying that
only SO-tagged operations pay gating latency.

### 4.3 Workloads

| Workload | What it measures | Stacks exercised |
|----------|-----------------|-----------------|
| Ping-pong latency | Minimum operation latency | Both |
| Bulk read/write | Throughput vs payload size | Both |
| Send/recv | Two-sided messaging overhead | Both |
| Mixed ordering | NO/RO/SO interleaving cost | UB only |
| State sweep | Latency vs active connections | Both |
| Loss recovery | Goodput under injected packet loss | Both |
| Many-to-one fanout | Target dispatch overhead (Jetty Group vs CPU) | Both |

### 4.4 Validation against OpenURMA

Where OpenURMA has published numbers (500 ns load/store, 2236 ns RoCE
READ, 4.47× ratio, 4855× state reduction), Nano-UB results should fall
within ±10% under identical configuration. Discrepancies are investigated
and documented — they may reveal genuine modelling differences or bugs.

### 4.5 Determinism

All randomised experiments (Poisson arrival processes, link jitter, loss
injection) seed their RNG, so repeated runs produce identical results.

---

## 5. Scope

### 5.1 In scope

- UB transport layer: RTP with PSN/GoBackN, UTP for UNO mode, simplified
  CETPH echo
- UB transaction layer: BTAH/ATAH, all 18 opcodes, all four service modes
  (ROI/ROT/ROL/UNO), all three execution-order tags (NO/RO/SO),
  application Fence, both completion-order modes
- UB §8.3 Load/Store with TP Bypass
- UB §7.4.2.3 atomic suite: CAS, Swap, Store, Load, FAA, FSUB, FAND,
  FOR, FXOR
- RoCEv2 RC: SEND, RDMA WRITE, RDMA READ, COMPARE_SWAP, FETCH_ADD,
  ACK/NAK with GBN retransmit
- RoCEv2 DCQCN congestion control (ECN-based)
- Side-by-side comparison harness with identical workloads

### 5.2 Out of scope

- UB physical/link layer (packets run over a modelled EtherLink, not real
  transceivers)
- Selective retransmit engine (GoBackN only)
- TPG multi-path load balancing beyond single-channel
- Security partitions, virtualization, device management
- C-AQM congestion control on real hardware (simulated switch only)
- RoCEv2 XRC, UD, or DCT transport modes
- Real PCIe or Ethernet hardware interfaces

---

## 6. Project Structure

```
nano-ub/
├── DESIGN.md                ← this document
├── CMakeLists.txt           ← top-level build
├── README.md
├── include/
│   └── nano/                ← protocol headers and type definitions
├── src/
│   ├── ub/                  ← UB pipeline elements
│   ├── roce/                ← RoCE pipeline elements
│   ├── nic_ub.cpp           ← UB NIC assembly
│   ├── nic_roce.cpp         ← RoCE NIC assembly
│   └── main_twonode.cpp     ← two-node simulator entry point
├── tests/                   ← correctness and comparison tests
├── scripts/                 ← build and run wrappers
└── results/                 ← experiment outputs (git-ignored)
```

---

## 7. References

- *UB-Base-Specification 2.0.1* — Huawei Technologies, 2025.
- *UB-Software-Reference-Design-for-OS 2.0* — Huawei Technologies, 2025.
- *InfiniBand Architecture Specification Volume 1, Release 1.5* — IBTA, 2024.
- *OpenURMA* — Bojie Li, 2026. https://github.com/bojieli/OpenURMA
- OpenURMA `docs/architecture.md` — element-graph design and pillar mapping.
- OpenURMA `docs/wire_format.md` — bit-level header layouts.
- OpenURMA `RESEARCH_PLAN.md` — research framing and evaluation plan.
- OpenURMA `eval/comparison.md` — published UB-vs-RoCE comparison data.
