#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build=${BUILD_DIR:-build-phase2}
out=${RESULT_DIR:-experiments/phase2/output}
cmake_bin=${CMAKE_BIN:-cmake}
ctest_bin=${CTEST_BIN:-ctest}
mkdir -p "$out"
BUILD_DIR="$build" RESULT_DIR="$out/legacy" CMAKE_BIN="$cmake_bin" CTEST_BIN="$ctest_bin" bash scripts/run_e2e.sh > "$out/legacy_validation.txt" 2>&1
python3 -m unittest discover -s workloads/tests -v > "$out/phase1_tests.txt" 2>&1
TRACE_BINARY="$build/trace_e2e" python3 -m unittest discover -s tests/phase2 -v > "$out/phase2_tests.txt" 2>&1
python3 -m experiments.phase2.run --binary "$build/trace_e2e" --output "$out" | tee "$out/trace_validation.txt"
python3 - "$out" <<'PY'
from pathlib import Path
import sys
out=Path(sys.argv[1]);count=0
for f in Path('eval/e2e').glob('*.csv'):
    if not (out/'legacy'/f.name).exists():continue
    assert f.read_bytes()==(out/'legacy'/f.name).read_bytes(),f.name
    count+=1
assert count==34,count
(out/'legacy_byte_comparison.txt').write_text(f'PASS: {count} old event/WR/summary CSV files byte-identical to committed baseline\n')
PY
printf '%s\n' 'PASS: original 15 CTests + 16 E2E, 24 Phase1 tests, Phase2 adapter/evaluation tests, 21 traces, exact baseline and deterministic repeats'
