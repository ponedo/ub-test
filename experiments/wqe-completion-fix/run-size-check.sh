#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
: "${INDEX_ROOT:?}" "${FIX_ROOT:?}" "${OUT:?}"
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
for arm in B C; do
 if [ "$arm" = B ]; then root=$(cd "$INDEX_ROOT" && pwd); else root=$(cd "$FIX_ROOT" && pwd); fi
 c++ -std=c++20 -O2 "$HERE/wqe-size.cc" -I"$root/build/include" -L"$root/build/lib" -Wl,-rpath,"$root/build/lib" -lns3.44-core -o "$OUT/sizeof-$arm"
 "$OUT/sizeof-$arm" > "$OUT/sizeof-$arm.txt"
done
