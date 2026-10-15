#!/usr/bin/env bash
set -euo pipefail
POC_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
NS3_ROOT=${NS3_ROOT:-/workspace/ns-3-ub}
BUILD_TOOLS=${BUILD_TOOLS:-/workspace/build-tools}
PYTHON=${PYTHON:-python3.12}
OUT=${OUT:-"$POC_DIR/evidence"}
mkdir -p "$OUT"
if [[ ! -d "$NS3_ROOT/.git" ]]; then
  git clone --no-checkout https://gitcode.com/open-usim/ns-3-ub.git "$NS3_ROOT"
  git -C "$NS3_ROOT" checkout --detach d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
fi
test "$(git -C "$NS3_ROOT" rev-parse HEAD)" = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
git -C "$NS3_ROOT" submodule update --init --recursive
test "$(git -C "$NS3_ROOT/scratch/ns-3-ub-tools" rev-parse HEAD)" = 29009175f1778f76a22d929063c3a0821cb91e56
if [[ ! -x "$BUILD_TOOLS/bin/cmake" || ! -x "$BUILD_TOOLS/bin/ninja" ]]; then
  "$PYTHON" -m pip install --target "$BUILD_TOOLS" cmake==4.4.4 ninja==1.13.2
fi
export PATH="$BUILD_TOOLS/bin:$PATH"
export PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
cp "$POC_DIR/chunk-relay.cc" "$NS3_ROOT/scratch/chunk-relay.cc"
cp "$POC_DIR/tracker.h" "$NS3_ROOT/scratch/tracker.h"
cd "$NS3_ROOT"
"$PYTHON" ./ns3 configure --enable-modules=unified-bus --disable-examples --disable-tests --disable-mpi --disable-mtp --disable-werror -d release -G Ninja > "$OUT/configure.txt" 2>&1
"$PYTHON" ./ns3 build -j "${BUILD_JOBS:-4}" ub-quick-example chunk-relay > "$OUT/build.txt" 2>&1
"$PYTHON" ./ns3 run --no-build 'scratch/ub-quick-example --case-path=scratch/2nodes_single-tp' > "$OUT/smoke-console.txt" 2>&1
mkdir -p "$OUT/smoke-raw"
cp scratch/2nodes_single-tp/runlog/TaskTrace_*.csv scratch/2nodes_single-tp/runlog/PacketTrace_*.csv scratch/2nodes_single-tp/runlog/AllPacketTrace_ACK_*.csv "$OUT/smoke-raw/"
"$PYTHON" "$POC_DIR/diagnose-smoke.py" scratch/2nodes_single-tp "$OUT/smoke-diagnosis.json" > "$OUT/smoke-adapter.txt"
"$PYTHON" ./ns3 run --no-build "chunk-relay --output=$OUT/events.csv" > "$OUT/relay-console.txt" 2>&1
"$PYTHON" "$POC_DIR/verify.py" "$OUT/events.csv" > "$OUT/verification.json"
"$PYTHON" ./ns3 run --no-build "chunk-relay --chunk0Bytes=65537 --chunk1Bytes=262147 --segmentBytes=4096 --computeNs=2000 --output=$OUT/variant-events.csv" > "$OUT/variant-console.txt" 2>&1
"$PYTHON" "$POC_DIR/verify.py" "$OUT/variant-events.csv" --sizes 65537 262147 --segment 4096 --compute-ns 2000 > "$OUT/variant-verification.json"
g++ -std=c++17 -Wall -Wextra -Werror "$POC_DIR/tests/tracker-test.cc" -o "$OUT/tracker-test"
"$OUT/tracker-test" > "$OUT/tracker-tests.txt"
"$PYTHON" "$POC_DIR/tests/test-verifier.py" "$OUT/events.csv" > "$OUT/verifier-tests.txt" 2>&1
rm "$OUT/tracker-test"
printf 'PASS: evidence in %s\n' "$OUT"
