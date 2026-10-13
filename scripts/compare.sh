#!/bin/bash
cd "$(dirname "$0")/.."

# PCIe/总线延迟参数（来自 OpenURMA twonode 模型）
PCIE_MMIO=150
PCIE_DMA_RD=500
PCIE_DMA_WR=250
PCIE_CQE_POLL=70
MEMBUS=30

echo "======================================"
echo "  Nano-UB: UB vs RoCE 延迟对比"
echo "======================================"
echo ""

echo "--- Host-visible 延迟模型（64B，含 PCIe/片上总线）---"
if [ -x ./build/bench_full_latency ]; then
    ./build/bench_full_latency --payload-bytes 64
else
    echo "  bench_full_latency 未构建"
fi
echo ""
echo "--- PCIe 开销明细 ---"
echo "  PCIe MMIO 门铃:      ${PCIE_MMIO} ns"
echo "  PCIe DMA 读 WQE:     ${PCIE_DMA_RD} ns"
echo "  PCIe DMA 写 CQE:     ${PCIE_DMA_WR} ns"
echo "  CQE 轮询 (主机 DRAM): ${PCIE_CQE_POLL} ns"
echo "  片上总线 (UB 独占):   ${MEMBUS} ns/次"
echo ""
echo "--- Micro-benchmark ---"
echo "  运行: bash scripts/microbench.sh"
echo "  输出: eval/results/sc_*.csv"
echo ""
echo "======================================"
