#!/usr/bin/env bash
# Compile the application-only probe against the accepted unchanged native build.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WORKSPACE=$(cd "$HERE/../../.." && pwd)
NATIVE=${NATIVE:-"$WORKSPACE/wqe-completion-native"}
OUT=${OUT:-"$WORKSPACE/pair-jetty-raw/gate-a-extra"}
mkdir -p "$OUT"
EXPECTED=2fde39d02920e639f5b200d0c5262a517326deb8
ACTUAL=$(git -C "$NATIVE" rev-parse HEAD)
[[ $(git -C "$NATIVE" rev-parse HEAD^{tree}) == c27d1faef570e6da9900a71aa0a37180a58dfba8 ]] || { echo "Unexpected native source tree at $ACTUAL" >&2; exit 2; }
git -C "$NATIVE" diff --exit-code >/dev/null
git -C "$NATIVE" diff --cached --exit-code >/dev/null
[[ $(git -C "$NATIVE/scratch/ns-3-ub-tools" rev-parse HEAD) == 29009175f1778f76a22d929063c3a0821cb91e56 ]]
printf '%s\n' "$ACTUAL" > "$OUT/native-commit.txt"
c++ -std=c++20 -O3 -g -I"$NATIVE/build/include" "$HERE/pair-lifecycle-probe.cc" \
  -L"$NATIVE/build/lib" -Wl,-rpath,"$NATIVE/build/lib" \
  -lns3.44-unified-bus -lns3.44-network -lns3.44-core -o "$OUT/pair-lifecycle-probe" \
  >"$OUT/build.log" 2>&1
printf 'case,exit_code\n' > "$OUT/exit-status.csv"
run() {
  local name=$1; shift
  set +e
  python3 - "$OUT/$name" "$OUT/pair-lifecycle-probe" "$@" <<'PYRUN'
import json, resource, shutil, subprocess, sys, time
prefix, binary, *args = sys.argv[1:]
start = time.monotonic()
if shutil.disk_usage(prefix.rsplit('/', 1)[0]).free < 2*1024**3:
    raise SystemExit('Less than 2 GiB free disk; refusing run')
def limits():
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
try:
    with open(prefix + '.log', 'w') as log:
        result = subprocess.run([binary, '--output=' + prefix, *args], stdout=log, stderr=subprocess.STDOUT, timeout=90, preexec_fn=limits)
    code = result.returncode
except subprocess.TimeoutExpired:
    code = 124
r = resource.getrusage(resource.RUSAGE_CHILDREN)
with open(prefix + '-resources.json', 'w') as out:
    json.dump(dict(wall_seconds=time.monotonic()-start, user_seconds=r.ru_utime, system_seconds=r.ru_stime,
                   max_rss_kib=r.ru_maxrss, exit_code=code), out, indent=2)
sys.exit(code if code >= 0 else 128-code)
PYRUN
  local status=$?
  set -e
  printf '%s,%s\n' "$name" "$status" >> "$OUT/exit-status.csv"
  cat "$OUT/$name.log"
  if ((status)); then echo "Gate A failure: $name; stop for review" >&2; exit "$status"; fi
}
for n in 2 3 4; do run "directional-$n" --mode=directional --nodes="$n"; done
run cancel --mode=cancel
run fail --mode=fail
run wrap-66000 --mode=wrap --count=22000
sha256sum "$HERE/pair-lifecycle-probe.cc" "$HERE/pair-jetty-manager.h" "$HERE/run-pair-lifecycle.sh" "$OUT/pair-lifecycle-probe" "$NATIVE/build/lib/libns3.44-unified-bus.so" > "$OUT/source-binary-sha256.txt"
