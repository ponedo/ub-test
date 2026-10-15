#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
NS3_ROOT=${NS3_ROOT:-/workspace/ns-3-ub}
BUILD_TOOLS=${BUILD_TOOLS:-/workspace/build-tools}
export PATH="$BUILD_TOOLS/bin:$PATH" PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
BUILD_EVIDENCE=${EVIDENCE:-"$HERE/evidence"}
mkdir -p "$BUILD_EVIDENCE"
test "$(git -C "$NS3_ROOT" rev-parse HEAD)" = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
test "$(git -C "$NS3_ROOT/scratch/ns-3-ub-tools" rev-parse HEAD)" = 29009175f1778f76a22d929063c3a0821cb91e56
cp "$HERE/direct-weight-forward.cc" "$NS3_ROOT/scratch/"
cp "$HERE/weight-distribution.h" "$NS3_ROOT/scratch/"
cp "$HERE/../no-balancing-layer/nb-tracker.h" "$NS3_ROOT/scratch/"
cd "$NS3_ROOT"
python3.12 ./ns3 build -j "${BUILD_JOBS:-4}" direct-weight-forward > "$BUILD_EVIDENCE/build.txt" 2>&1
for kind in UbPort UbLink UbSwitch; do
  python3.12 ./ns3 run --no-build "direct-weight-forward --PrintAttributes=ns3::$kind" > "$BUILD_EVIDENCE/$kind-attributes.txt" 2>&1
done
python3.12 ./ns3 run --no-build 'direct-weight-forward --PrintGlobals' > "$BUILD_EVIDENCE/ub-globals.txt" 2>&1
