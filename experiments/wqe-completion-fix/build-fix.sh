#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
: "${NS3_ROOT:?set NS3_ROOT to a dedicated native checkout}"
: "${BUILD_TOOLS:?set BUILD_TOOLS to the cmake/ninja/psutil installation}"
BASE=eda2fd75bfd1a37b28917b3ebbe721bade5f91ae
TOOLS_BASE=29009175f1778f76a22d929063c3a0821cb91e56
OUT=${OUT:-"$HERE/evidence/build"}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
NS3_ROOT=$(cd "$NS3_ROOT" && pwd)
BUILD_TOOLS=$(cd "$BUILD_TOOLS" && pwd)
git -C "$NS3_ROOT" merge-base --is-ancestor "$BASE" HEAD
test "$(git -C "$NS3_ROOT/scratch/ns-3-ub-tools" rev-parse HEAD)" = "$TOOLS_BASE"
# Permit only the exact reviewed completion patch; preserve all unrelated changes.
if git -C "$NS3_ROOT" diff "$BASE" --quiet; then
 git -C "$NS3_ROOT" apply --check "$HERE/combined-native.patch"
 git -C "$NS3_ROOT" apply "$HERE/combined-native.patch"
fi
git -C "$NS3_ROOT" diff "$BASE" --binary > "$OUT/actual-native.patch"
cmp "$HERE/combined-native.patch" "$OUT/actual-native.patch"
export PATH="$BUILD_TOOLS/bin:$PATH" PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
cp "$REPO/experiments/multi-npu-relay/multi-npu-relay.cc" "$NS3_ROOT/scratch/"
cp "$REPO/experiments/direct-weight-forward/weight-distribution.h" "$REPO/experiments/no-balancing-layer/nb-tracker.h" "$NS3_ROOT/scratch/"
cd "$NS3_ROOT"
python3 ./ns3 configure --enable-modules=unified-bus --disable-examples --enable-tests --disable-mpi --disable-mtp --disable-werror -d release -G Ninja -- -DCMAKE_EXPORT_COMPILE_COMMANDS=ON '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG -g' > "$OUT/configure.log" 2>&1
python3 ./ns3 build -j "${BUILD_JOBS:-4}" multi-npu-relay > "$OUT/build.log" 2>&1
# The large native test translation unit is compiled alone to bound peak memory.
ninja -C cmake-cache -j1 unified-bus-test > "$OUT/build-tests.log" 2>&1
c++ -std=c++20 -O3 -g utils/test-runner.cc -Ibuild/include -Lbuild/lib -Wl,--no-as-needed -lns3.44-unified-bus-test -lns3.44-core -Wl,-rpath,"$NS3_ROOT/build/lib" -o "$OUT/native-test-runner"
"$OUT/native-test-runner" --list > "$OUT/test-list.txt"
