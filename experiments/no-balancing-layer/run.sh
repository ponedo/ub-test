#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
NS3_ROOT=${NS3_ROOT:-/workspace/ns-3-ub}
BUILD_TOOLS=${BUILD_TOOLS:-/workspace/build-tools}
PYTHON=${PYTHON:-python3.12}
EVIDENCE=${EVIDENCE:-"$HERE/evidence"}
mkdir -p "$EVIDENCE"
EVIDENCE=$(cd "$EVIDENCE" && pwd)
# Reuse the immutable PoC bootstrap and ALL its regressions; never overwrite its evidence.
NS3_ROOT="$NS3_ROOT" BUILD_TOOLS="$BUILD_TOOLS" PYTHON="$PYTHON" OUT="$EVIDENCE/poc-regression" bash "$HERE/../../poc/chunk-relay/run.sh" > "$EVIDENCE/poc-regression-console.txt" 2>&1
export PATH="$BUILD_TOOLS/bin:$PATH" PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
cp "$HERE/no-balancing-layer.cc" "$NS3_ROOT/scratch/"
cp "$HERE/nb-tracker.h" "$NS3_ROOT/scratch/"
cd "$NS3_ROOT"
"$PYTHON" ./ns3 build -j "${BUILD_JOBS:-4}" no-balancing-layer > "$EVIDENCE/build.txt" 2>&1
{ "$PYTHON" --version; g++ --version; cmake --version; ninja --version; git rev-parse HEAD; git -C scratch/ns-3-ub-tools rev-parse HEAD; } > "$EVIDENCE/tool-versions.txt"
"$PYTHON" "$HERE/suite.py" --ns3 "$NS3_ROOT" --out "$EVIDENCE" > "$EVIDENCE/suite-console.txt" 2>&1
"$PYTHON" "$HERE/tests/test_layer.py" --evidence "$EVIDENCE" --ns3 "$NS3_ROOT" > "$EVIDENCE/tests.txt" 2>&1
"$PYTHON" -O "$HERE/tests/test_layer.py" --evidence "$EVIDENCE" --ns3 "$NS3_ROOT" > "$EVIDENCE/tests-optimized.txt" 2>&1
printf 'PASS: NoBalancing suite, all PoC regressions, ordinary and optimized tests.\n'
