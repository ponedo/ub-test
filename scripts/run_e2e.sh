#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build=${BUILD_DIR:-build-e2e}
out=${RESULT_DIR:-eval/e2e}
cmake_bin=${CMAKE_BIN:-cmake}
ctest_bin=${CTEST_BIN:-ctest}
"$cmake_bin" -S . -B "$build" -DCMAKE_BUILD_TYPE=Debug ${SYSTEMC_PREFIX:+-DCMAKE_PREFIX_PATH="$SYSTEMC_PREFIX"}
"$cmake_bin" --build "$build" -j "${JOBS:-4}"
mkdir -p "$out"
"$ctest_bin" --test-dir "$build" --output-on-failure | tee "$out/ctest.log"
for load in mixed equal fence ordering rot; do
    for policy in fifo rr drr; do
        "$build/scheduler_e2e" "$policy" "$load" "$out/${policy}_${load}" > "$out/${policy}_${load}.log" 2>&1
    done
done
"$build/scheduler_e2e" drr mixed "$out/drr_mixed_50gbps" 50 > "$out/drr_mixed_50gbps.log" 2>&1
python3 scripts/analyze_e2e.py "$out" | tee "$out/summary.txt"
# Independent rerun must produce byte-identical WR and raw event records.
repeat=$(mktemp -d)
trap 'rm -rf "$repeat"' EXIT
for policy in fifo rr drr; do
    "$build/scheduler_e2e" "$policy" mixed "$repeat/$policy" > "$repeat/$policy.log" 2>&1
    cmp "$out/${policy}_mixed.events.csv" "$repeat/$policy.events.csv"
    cmp "$out/${policy}_mixed.wr.csv" "$repeat/$policy.wr.csv"
done
echo 'PASS: 15 baseline/guard tests, 16 E2E runs, 3 deterministic reruns' | tee "$out/validation.txt"
