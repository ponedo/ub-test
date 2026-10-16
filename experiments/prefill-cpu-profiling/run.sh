#!/usr/bin/env bash
# Fresh raw case paths are required; published summaries in this checkout are replaced.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$HERE/../.."
raw=/workspace/prefill-cpu-raw
if [ -d "$raw/common-5000" ]; then printf 'Use a fresh workspace: existing raw cases are preserved.\n' >&2; exit 1; fi
mkdir -p "$raw"
bash "$HERE/tools.sh" > "$raw/tools-install.txt" 2>&1
bash "$HERE/build.sh" > "$raw/build-timed.txt" 2>&1
python3 "$HERE/capture.py" > "$raw/capture.txt" 2>&1
python3 "$HERE/execute.py" --init
for assignments in 5000 10000 20000 50000; do
 python3 "$HERE/execute.py" --assignments "$assignments" > "$raw/$assignments-driver.txt" 2>&1
 python3 "$HERE/analyze.py" "$assignments" > "$raw/$assignments-analysis.txt" 2>&1
done
python3 "$HERE/check.py" > "$raw/evidence-check.txt" 2>&1
python3 experiments/prefill-capacity/guard.py --out "$raw/regression-guard" --wall 1800 --case "$raw" -- bash "$HERE/regressions.sh"
python3 "$HERE/finish.py"
python3 "$HERE/symbols.py"
python3 "$HERE/conclusions.py"
/workspace/prefill-profile-venv/bin/python "$HERE/report.py"
python3 "$HERE/publish.py"
python3 "$HERE/package.py"
