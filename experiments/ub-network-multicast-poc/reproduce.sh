#!/usr/bin/env bash
set -euo pipefail
export CLICOLOR=0
# Usage: reproduce.sh <clean ns-3-ub d6aa checkout> <new private run directory>
# Requires cmake,ninja,C++20,Python3+psutil. No weights/GPU/private routing data.
HERE=$(cd "$(dirname "$0")" && pwd)
NATIVE=$(cd "$1" && pwd)
PRIVATE=$2
[[ ! -e "$PRIVATE" ]] || { echo 'Use a new private output directory' >&2; exit 2; }
[[ $(git -C "$NATIVE" rev-parse HEAD) == d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b ]] || { echo 'Wrong native base' >&2; exit 2; }
git -C "$NATIVE" diff --quiet
git -C "$NATIVE" diff --cached --quiet
git -C "$NATIVE" apply --check "$HERE/patches/accepted-unicast-baseline.patch"
git -C "$NATIVE" apply "$HERE/patches/accepted-unicast-baseline.patch"
git -C "$NATIVE" apply --check "$HERE/patches/network-replication.patch"
git -C "$NATIVE" apply "$HERE/patches/network-replication.patch"
cp "$HERE/network-poc.cc" "$NATIVE/scratch/network-poc.cc"
# Register all source files BEFORE configuring, keep configuration environment stable.
cmake -S "$NATIVE" -B "$NATIVE/cmake-cache" -G Ninja -DCMAKE_BUILD_TYPE=release \
  -DNS3_ENABLED_MODULES=unified-bus -DNS3_ASSERT=ON -DNS3_LOG=OFF \
  -DNS3_TESTS=ON -DNS3_EXAMPLES=OFF -DNS3_MPI=OFF -DNS3_MTP=OFF \
  -DNS3_NATIVE_OPTIMIZATIONS=OFF -DNS3_WARNINGS_AS_ERRORS=OFF
cmake --build "$NATIVE/cmake-cache" --target scratch_network-poc scratch_ub-quick-example test-runner -j2
mkdir -p "$PRIVATE"
python3 "$HERE/run.py" --binary "$NATIVE/build/scratch/ns3.44-network-poc" \
  --private "$PRIVATE/runs" --public "$PRIVATE/collected"
python3 "$HERE/test-verifier.py" "$PRIVATE/runs/multipart-multicast" --out "$PRIVATE/verifier-mutations.json"
python3 "$HERE/collect.py" "$PRIVATE/collected" "$PRIVATE/summary"
python3 "$HERE/run-native-tests.py" --native "$NATIVE" --out "$PRIVATE/native-tests"
echo "Summary: $PRIVATE/summary"
