#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
: "${NS3_ROOT:?unchanged fixed native checkout}" "${OUT:?fresh build output directory}"
test "$(git -C "$NS3_ROOT" rev-parse HEAD^{tree})" = c27d1faef570e6da9900a71aa0a37180a58dfba8
# Tree pin permits reproducing the exact reviewed patches with different commit metadata.
git -C "$NS3_ROOT" diff --exit-code
git -C "$NS3_ROOT" diff --cached --exit-code
test "$(git -C "$NS3_ROOT/scratch/ns-3-ub-tools" rev-parse HEAD)" = 29009175f1778f76a22d929063c3a0821cb91e56
mkdir -p "$OUT"
for app in pair-probe pair-layer; do
 c++ -std=c++20 -O3 -g "$HERE/$app.cc" -I"$NS3_ROOT/build/include" -L"$NS3_ROOT/build/lib" -Wl,--disable-new-dtags -Wl,-rpath,"$NS3_ROOT/build/lib" -lns3.44-unified-bus -lns3.44-network -lns3.44-core -o "$OUT/$app" > "$OUT/build-$app.log" 2>&1
done
sha256sum "$OUT/pair-probe" "$OUT/pair-layer" "$NS3_ROOT"/build/lib/libns3.*.so > "$OUT/elf-sha256.txt"
