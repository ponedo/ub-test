#!/usr/bin/env bash
# Existing accepted native Release DSOs are reused; only the diagnostic app is built.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
WORK=$(cd "$HERE/../../.." && pwd)
RAW=${PROFILE_RAW:-"$WORK/qwen-chunk-profile-raw"}
NATIVE=${NS3_ROOT:-"$WORK/wqe-completion-native"}
test "$(git -C "$NATIVE" rev-parse HEAD^{tree})" = c27d1faef570e6da9900a71aa0a37180a58dfba8
git -C "$NATIVE" diff --exit-code
git -C "$NATIVE" diff --cached --exit-code
python3 - "$RAW" <<'PY'
import shutil,sys
assert shutil.disk_usage(sys.argv[1]).free>=8*1024**3, '8GiB free-disk guard'
PY
mkdir -p "$RAW/aux" "$RAW/instrumented"
python3 "$HERE/generate-instrumented.py" --out "$RAW/instrumented" > "$RAW/aux/instrument-generation.json"
c++ -std=c++20 -O3 -g "$RAW/instrumented/pair-layer.cc" -I"$NATIVE/build/include" -L"$NATIVE/build/lib" -Wl,--disable-new-dtags -Wl,-rpath,"$NATIVE/build/lib" -lns3.44-unified-bus -lns3.44-network -lns3.44-core -o "$RAW/instrumented/pair-layer" > "$RAW/aux/build-instrumented.log" 2>&1
cc -O2 -g "$HERE/record.c" -o "$RAW/aux/record"
cc -O3 -g "$HERE/calibration-hotloop.c" -o "$RAW/aux/calibration-hotloop"
sha256sum "$RAW/instrumented/pair-layer" "$RAW/aux/record" "$RAW/aux/calibration-hotloop" > "$RAW/aux/profiler-binaries.sha256"
