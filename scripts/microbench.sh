#!/bin/bash
# Nano-UB SystemC-style microbenchmark suite.
# Emits OpenURMA-like CSV files under eval/results/.
set -e

cd "$(dirname "$0")/.."
BUILD="build"
RES="eval/results"
BIN="$BUILD/bench_micro"
mkdir -p "$RES"

if [ ! -x "$BIN" ]; then
    cmake -B "$BUILD" >/dev/null
    cmake --build "$BUILD" --target bench_micro >/dev/null
fi

run_one() {
    "$BIN" "$@" | grep '^CSV,'
}

{
    echo "svc,exec,tx_cycles,tx_ns_200MHz"
    for s in ROI ROT ROL UNO; do
        for e in NO RO SO; do
            run_one tx_latency "$s" "$e" | awk -F, '{print $3","$4","$5","$6}'
        done
    done
} > "$RES/sc_tx_latency.csv"
echo "wrote $RES/sc_tx_latency.csv"

{
    echo "svc,n_wrs,wire_flits,span_cycles,wr_per_us"
    for s in ROI ROT ROL UNO; do
        run_one throughput "$s" | awk -F, '{print $3","$4","$5","$6","$7}'
    done
} > "$RES/sc_throughput.csv"
echo "wrote $RES/sc_throughput.csv"

{
    echo "stage,first_t_ns,delta_cycles_from_prev"
    run_one per_element | awk -F, '{print $3","$4","$5}'
} > "$RES/sc_per_element.csv"
echo "wrote $RES/sc_per_element.csv"

{
    echo "n_pending_reads,fenced_emerge_cycles"
    for n in 0 1 2 3 4; do
        run_one fence_cost "$n" | awk -F, '{print $3","$4}'
    done
} > "$RES/sc_fence_cost.csv"
echo "wrote $RES/sc_fence_cost.csv"

{
    echo "n_outstanding_ro,so_emerge_cycles"
    for n in 0 1 2 3 4; do
        run_one so_blocking "$n" | awk -F, '{print $3","$4}'
    done
} > "$RES/sc_so_blocking.csv"
echo "wrote $RES/sc_so_blocking.csv"

{
    echo "length_bytes,wire_flits_per_wr,wr_per_us"
    for L in 8 64 256 1024 4096; do
        run_one payload "$L" | awk -F, '{print $3","$4","$5}'
    done
} > "$RES/sc_payload.csv"
echo "wrote $RES/sc_payload.csv"

{
    echo "wr_index,emerge_cycles_after_post"
    run_one hol_blocking | awk -F, '{print $3","$4}'
} > "$RES/sc_hol_blocking.csv"
echo "wrote $RES/sc_hol_blocking.csv"

echo ""
echo "=== summary ==="
for f in sc_tx_latency sc_throughput sc_per_element sc_fence_cost sc_so_blocking sc_payload sc_hol_blocking; do
    echo "--- $f ---"
    cat "$RES/$f.csv"
done
