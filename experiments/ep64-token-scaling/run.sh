#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
: "${NS3_ROOT:?fixed native checkout}" "${RAW:?fresh output root}"
mkdir -p "$RAW"
python3 - "$RAW" <<'PY'
import shutil,sys
assert shutil.disk_usage(sys.argv[1]).free>=8*1024**3,'disk_free_guard before build'
PY
export OUT="$RAW/build"
NS3_ROOT="$NS3_ROOT" bash "$HERE/../pair-jetty/build.sh"
c++ -std=c++20 -Wall -Wextra -O2 "$HERE/../multi-npu-relay/graph-tool.cc" -o "$OUT/graph-tool" > "$OUT/build-graph.log" 2>&1
set +e
python3 "$HERE/run.py" --raw "$RAW" --binary "$OUT/pair-layer" --lib "$NS3_ROOT/build/lib" --graph-tool "$OUT/graph-tool" "$@"
result=$?
set -e
if [[ -f "$RAW/runs.json" ]]; then python3 "$HERE/collect.py" --raw "$RAW" --out "$RAW/analysis"; fi
exit "$result"
