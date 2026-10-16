#!/usr/bin/env bash
# Rebuild documented release settings in a dedicated native clone.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
WORK=$(dirname "$REPO")
NATIVE=${NS3_ROOT:-"$WORK/prefill-cpu-native"}
TOOLS=${BUILD_TOOLS:-"$WORK/prefill-cpu-tools"}
RAW=${PROFILE_RAW:-"$WORK/prefill-cpu-raw"}
if [ "$NATIVE" != "$WORK/prefill-cpu-native" ] || [ "$TOOLS" != "$WORK/prefill-cpu-tools" ] || [ "$RAW" != "$WORK/prefill-cpu-raw" ]; then
 echo 'This reproducible layout derives paths from the repository. Unsupported path overrides refused.' >&2; exit 2
fi
export PATH="$TOOLS/bin:$PATH" PYTHONPATH="$TOOLS${PYTHONPATH:+:$PYTHONPATH}"
test "$(git -C "$NATIVE" rev-parse HEAD)" = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
test "$(git -C "$NATIVE/scratch/ns-3-ub-tools" rev-parse HEAD)" = 29009175f1778f76a22d929063c3a0821cb91e56
mkdir -p "$RAW/aux" "$HERE/evidence"
cp "$REPO/experiments/multi-npu-relay/multi-npu-relay.cc" "$NATIVE/scratch/"
cp "$REPO/experiments/direct-weight-forward/weight-distribution.h" "$REPO/experiments/no-balancing-layer/nb-tracker.h" "$NATIVE/scratch/"
(cd "$NATIVE"; python3 ./ns3 configure --enable-modules=unified-bus --disable-examples --disable-tests --disable-mpi --disable-mtp --disable-werror -d release -G Ninja -- -DCMAKE_EXPORT_COMPILE_COMMANDS=ON '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG -g'; python3 ./ns3 build -j4 multi-npu-relay)
if [ -e "$RAW/baseline-binaries" ]; then echo 'Refusing to overwrite baseline' >&2; exit 1; fi
mkdir "$RAW/baseline-binaries"; cp -a "$NATIVE/build/lib" "$RAW/baseline-binaries/"; cp "$NATIVE/build/scratch/ns3.44-multi-npu-relay" "$RAW/baseline-binaries/"
python3 "$HERE/capture_build.py" --variant baseline
for pair in 'graph-tool.cc graph-tool' 'reference/oracle.cc reference-oracle'; do read -r source binary <<< "$pair"; c++ -std=c++20 -O2 "$REPO/experiments/multi-npu-relay/$source" -o "$RAW/aux/$binary"; done
cc -O2 -g "$HERE/record.c" -o "$HERE/record"
python3 "$HERE/instrument.py" --native "$NATIVE" --output "$HERE/evidence/native-timing.patch" --app "$REPO/experiments/multi-npu-relay/multi-npu-relay.cc" --app-output "$HERE/evidence/app-timing.patch"
git -C "$NATIVE" apply "$HERE/evidence/native-timing.patch"
sed 's@experiments/multi-npu-relay/multi-npu-relay.cc@scratch/multi-npu-relay.cc@g' "$HERE/evidence/app-timing.patch" | git -C "$NATIVE" apply -
(cd "$NATIVE"; python3 ./ns3 build -j4 multi-npu-relay)

python3 "$HERE/capture_build.py" --variant timed
