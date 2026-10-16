#!/usr/bin/env bash
set -euo pipefail
module_dir="$(cd "$(dirname "$0")" && pwd)"
repo_dir="$(cd "$module_dir/../.." && pwd)"
export CAPACITY_RAW="${CAPACITY_RAW:-/workspace/prefill-capacity-reproduce-$(date -u +%Y%m%dT%H%M%S)}"
export NS3_ROOT="${NS3_ROOT:-/workspace/ns-3-ub}"
export PATH="/workspace/build-tools/bin:$PATH"
export PYTHONPATH="/workspace/build-tools${PYTHONPATH:+:$PYTHONPATH}"
# Preserve any previously generated evidence and reject an occupied raw run directory.
test ! -e "$CAPACITY_RAW"
mkdir -p "$CAPACITY_RAW"
cd "$repo_dir"
if [ -d "$module_dir/evidence" ]; then mv "$module_dir/evidence" "$CAPACITY_RAW/previous-evidence"; fi
python3.12 "$module_dir/initialize.py" --raw "$CAPACITY_RAW"
# Build the accepted pre-change application without editing tracked native files.
cp experiments/direct-weight-forward/weight-distribution.h experiments/no-balancing-layer/nb-tracker.h "$NS3_ROOT/scratch/"
git show 555f2a591d7537b35fb507078dd686a50fb3400e:experiments/multi-npu-relay/multi-npu-relay.cc > "$NS3_ROOT/scratch/multi-npu-relay.cc"
(cd "$NS3_ROOT" && python3.12 ./ns3 build -j 4 multi-npu-relay) > "$CAPACITY_RAW/build-original-console.txt" 2>&1
cp "$NS3_ROOT/build/scratch/ns3.44-multi-npu-relay" "$CAPACITY_RAW/original-executor"
EVIDENCE="$CAPACITY_RAW/build-instrumented" bash experiments/multi-npu-relay/build.sh > "$CAPACITY_RAW/build-instrumented-console.txt" 2>&1
python3.12 "$module_dir/parity.py" --before "$CAPACITY_RAW/original-executor" > "$CAPACITY_RAW/parity-console.txt" 2>&1
python3.12 "$module_dir/safety_checks.py"
python3.12 "$module_dir/reproduce_cases.py" | tee "$CAPACITY_RAW/cases-console.txt"
python3.12 "$module_dir/guard.py" --out "$CAPACITY_RAW/regression-host" --wall 1800 --case "$CAPACITY_RAW/regressions" -- bash "$module_dir/regressions.sh"
python3.12 "$module_dir/collect.py"
python3.12 "$module_dir/collect_regressions.py"
/workspace/prefill-profile-venv/bin/python "$module_dir/report.py"
python3.12 "$module_dir/check.py"
git diff 555f2a591d7537b35fb507078dd686a50fb3400e -- experiments/multi-npu-relay/multi-npu-relay.cc > "$module_dir/evidence/executor-change.patch"
python3.12 "$module_dir/manifest.py"
