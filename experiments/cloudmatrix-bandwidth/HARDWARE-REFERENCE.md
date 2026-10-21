# CloudMatrix384 UB bandwidth reference

## Versioned primary sources

- [Paper v1, June 15, 2025](https://arxiv.org/pdf/2506.12708v1): §3.3.1 and Figure 3, p.11; network-interface description continues onto p.12. §3.3.2 and Figure 4, p.12.
- [Paper v2, June 18, 2025](https://arxiv.org/pdf/2506.12708v2): Table 1, p.9; §3.3.1 and Figure 3, p.11; §3.3.2 and Figure 4, p.12.
- [Paper v3, June 19, 2025](https://arxiv.org/pdf/2506.12708v3): latest version removes the original bandwidth/latency table and numerical hardware/interface specifications. Its Table 1 instead concerns model loading, p.36. It retains the dual-die architecture and changes “Ascend 910C” to “Ascend 910.” The removal does not by itself establish that the earlier numbers were corrected.
- [Submission history](https://arxiv.org/abs/2506.12708).

## Hardware capacity and directionality

V1/v2 specify seven 224-Gbps transceivers per die. Decimal-unit arithmetic gives 28 GB/s per physical transceiver and 196 GB/s aggregate one-way capacity per die. Figure 3 labels each die 196 GB/s one-way.

There are two different meanings of **392 GB/s**:

- Per die, summing both directions: 196 GB/s send + 196 GB/s receive.
- Per dual-die NPU/package, one direction: 2 × 196 GB/s.

Neither is 392 GB/s one-way per die. The separate on-package cross-die fabric is listed as 270 GB/s per direction; do not conflate it with external UB bandwidth.

## Reported measurement and scope limits

V2 Table 1 explicitly labels NPU metrics **per-die and unidirectional**. NPU–NPU WRITE is 135 GB/s inter-node and 137 GB/s intra-node. READ is 164 and 167 GB/s, respectively. The inter-node WRITE value corresponds to 135/196 ≈ 68.9% of nominal one-way per-die capacity, but that ratio is not a universal protocol-efficiency claim.

The table and accompanying discussion do not establish peer count, concurrency, bandwidth-test message size, or benchmark implementation. Thus **135 GB/s is not verified as a single-peer result or as simultaneous all-to-all throughput**. Use it as a reported per-die path calibration point, with test scope unknown.

WRITE latency is **2.1 µs inter-node** and 1.3 µs intra-node, for the latency column's 512-byte transfer. That transfer size does not establish bandwidth-test size. A **20 ns propagation setting is a separate modeling assumption**, not a substitute for measured 2.1 µs end-to-end WRITE latency.

## Modeling interpretation

A logical aggregate bandwidth model represents an endpoint's effective aggregate communication budget. Assigning an endpoint 196 GB/s nominal or 135 GB/s calibrated bandwidth does **not reproduce the physical seven-link, multi-switch UB topology**, routing, contention, or protocol behavior. Do not assign the aggregate value independently to each of seven physical links.

The existing **100 TF/s and 2692 reference assumptions remain unchanged** for this bandwidth-only comparison. They are reference-model assumptions, not hardware specifications validated by this note. No independent meaning or unit for 2692 is inferred here.
