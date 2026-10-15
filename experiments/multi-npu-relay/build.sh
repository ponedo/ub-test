#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
NS3_ROOT=${NS3_ROOT:-/workspace/ns-3-ub}
BUILD_TOOLS=${BUILD_TOOLS:-/workspace/build-tools}
export PATH="$BUILD_TOOLS/bin:$PATH" PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
EVIDENCE=${EVIDENCE:-"$HERE/evidence"}
RELAY_GRAPH_TOOL=${RELAY_GRAPH_TOOL:-/tmp/ub-relay-build/graph-tool}
mkdir -p "$EVIDENCE" "$(dirname "$RELAY_GRAPH_TOOL")"
test "$(git -C "$NS3_ROOT" rev-parse HEAD)" = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
test "$(git -C "$NS3_ROOT/scratch/ns-3-ub-tools" rev-parse HEAD)" = 29009175f1778f76a22d929063c3a0821cb91e56
c++ -std=c++20 -Wall -Wextra -O2 "$HERE/graph-tool.cc" -o "$RELAY_GRAPH_TOOL" > "$EVIDENCE/graph-build.txt" 2>&1
c++ -std=c++20 -O2 "$HERE/reference/oracle.cc" -o "$(dirname "$RELAY_GRAPH_TOOL")/reference-oracle" > "$EVIDENCE/oracle-build.txt" 2>&1
c++ -std=c++20 -O2 "$HERE/tracker-tests.cc" -o "$(dirname "$RELAY_GRAPH_TOOL")/tracker-tests" > "$EVIDENCE/tracker-build.txt" 2>&1
"$(dirname "$RELAY_GRAPH_TOOL")/tracker-tests" > "$EVIDENCE/tracker-tests.txt"
cp "$HERE/multi-npu-relay.cc" "$NS3_ROOT/scratch/"
cp "$HERE/../direct-weight-forward/weight-distribution.h" "$NS3_ROOT/scratch/"
cp "$HERE/../no-balancing-layer/nb-tracker.h" "$NS3_ROOT/scratch/"
cd "$NS3_ROOT"
python3.12 ./ns3 build -j "${BUILD_JOBS:-4}" multi-npu-relay > "$EVIDENCE/build.txt" 2>&1
for kind in UbPort UbLink UbSwitch; do
 python3.12 ./ns3 run --no-build "multi-npu-relay --PrintAttributes=ns3::$kind" > "$EVIDENCE/$kind-attributes.txt" 2>&1
done
python3.12 ./ns3 run --no-build 'multi-npu-relay --PrintGlobals' > "$EVIDENCE/ub-globals.txt" 2>&1
