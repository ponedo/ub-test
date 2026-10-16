#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
native=/workspace/prefill-cpu-native
export PATH=/workspace/build-tools/bin:$PATH PYTHONPATH=/workspace/build-tools
if [ ! -d "$native/.git" ]; then git clone --shared /workspace/ns-3-ub "$native"; fi
test "$(git -C "$native" rev-parse HEAD)" = d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b
cp "$HERE/../direct-weight-forward/weight-distribution.h" "$HERE/../no-balancing-layer/nb-tracker.h" "$native/scratch/"
python3 "$HERE/instrument.py"
cp "$HERE/scopes.h" "$native/scopes.h"
c++ -O3 -g -shared -fPIC "$HERE/scopes.cc" -o "$native/libcpuscopes.so"
cd "$native"
python3.12 ./ns3 configure --enable-modules=unified-bus --disable-examples --disable-tests --disable-mpi --disable-mtp --disable-werror -d release -G Ninja -- -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG -g -include $native/scopes.h" -DCMAKE_EXE_LINKER_FLAGS="-Wl,--no-as-needed $native/libcpuscopes.so" -DCMAKE_SHARED_LINKER_FLAGS="-Wl,--no-as-needed $native/libcpuscopes.so"
python3.12 ./ns3 build -j4 multi-npu-relay
