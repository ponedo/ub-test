#!/bin/bash
# Nano-UB: 一键回归测试
# 运行所有正确性测试 + benchmark，汇总结果
set -e

cd "$(dirname "$0")/.."
BUILD="build"

# 颜色
PASS="\033[32mPASS\033[0m"
FAIL="\033[31mFAIL\033[0m"
SKIP="\033[33mSKIP\033[0m"

echo "======================================"
echo "  Nano-UB 回归测试"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "======================================"
echo ""

# 编译
echo "--- 编译 ---"
if cmake -B "$BUILD" 2>/dev/null && cmake --build "$BUILD" 2>/dev/null; then
    echo -e "  编译: $PASS"
else
    echo -e "  编译: $FAIL"
    exit 1
fi
echo ""

# 正确性测试
echo "--- 正确性测试 ---"
TESTS=(
    m01_flit
    m02_link
    m03_roce_tx
    m04_roce_pingpong
    m05_roce_read
    m06_roce_full
    m07_ub_ls_tx
    m08_ub_ls_pingpong
    m09_ub_urma_tx
    m10_ub_urma_e2e
    m11_ub_ordering
)
PENDING=0
for t in "${TESTS[@]}"; do
    if [ ! -f "$BUILD/$t" ]; then
        echo -e "  $SKIP $t (未构建)"
        continue
    fi
    timeout 60 "$BUILD/$t" &>/dev/null && echo -e "  $PASS $t" || echo -e "  $FAIL $t"
done
echo ""

# Benchmark
echo "--- 性能基准 ---"
if [ -f "$BUILD/bench_full_latency" ]; then
    "$BUILD/bench_full_latency" --payload-bytes 64 >/dev/null && \
        echo -e "  $PASS bench_full_latency" || echo -e "  $FAIL bench_full_latency"
fi
if [ -f "$BUILD/bench_state_size" ]; then
    "$BUILD/bench_state_size" >/dev/null && \
        echo -e "  $PASS bench_state_size" || echo -e "  $FAIL bench_state_size"
fi
if [ -f "$BUILD/bench_ordering_cost" ]; then
    "$BUILD/bench_ordering_cost" >/dev/null && \
        echo -e "  $PASS bench_ordering_cost" || echo -e "  $FAIL bench_ordering_cost"
fi
if [ -f "$BUILD/bench_loss_recovery" ]; then
    "$BUILD/bench_loss_recovery" >/dev/null && \
        echo -e "  $PASS bench_loss_recovery" || echo -e "  $FAIL bench_loss_recovery"
fi
if [ -f "$BUILD/bench_micro" ]; then
    "$BUILD/bench_micro" summary >/dev/null && \
        echo -e "  $PASS bench_micro" || echo -e "  $FAIL bench_micro"
fi
if [ -f "docs/TUTORIAL.zh-CN.md" ]; then
    echo -e "  $PASS tutorial assets"
else
    echo -e "  $FAIL tutorial assets"
fi
echo ""

echo "======================================"
echo "  完成"
echo "======================================"
