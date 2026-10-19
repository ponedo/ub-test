#!/usr/bin/env bash
set -euo pipefail
NATIVE=$(cd "$1" && pwd)
PRIVATE=$2
GRAPH=$(realpath "$3")
BASELINE_LAYER=$(realpath "$4")
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$PRIVATE" ]] || { echo 'Choose a fresh private output directory' >&2; exit 2; }
mkdir -p "$PRIVATE"
PRIVATE=$(cd "$PRIVATE" && pwd)
python3 "$HERE/build.py" --native "$NATIVE" --out "$PRIVATE/build"
python3 "$HERE/test_headers.py" --native "$NATIVE" --out "$PRIVATE/header-tests"
python3 "$HERE/build_legacy.py" --native "$NATIVE" --out "$PRIVATE/legacy"
python3 "$HERE/guard_stage.py" --out "$PRIVATE/final-verifier-tests" -- python3 "$HERE/test_verify.py"
python3 "$HERE/run.py" --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase small
python3 "$HERE/check_legacy.py" --old "$PRIVATE/legacy/fanout" --new "$PRIVATE/build/fanout" --out "$PRIVATE/legacy-parity"
python3 "$HERE/test_faults.py" --binary "$PRIVATE/build/fanout" --out "$PRIVATE/faults"
python3 "$HERE/test_pressure.py" --native "$NATIVE" --out "$PRIVATE/pressure"
python3 "$HERE/run.py" --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase main
python3 "$HERE/run.py" --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase ideal
python3 "$HERE/../ub-concurrent-multicast/run-regressions.py" --native "$NATIVE" --out "$PRIVATE/regressions" --layer "$PRIVATE/build/pair-layer" --graph-tool "$GRAPH" --baseline-layer "$BASELINE_LAYER"
python3 "$HERE/collect.py" "$PRIVATE/campaign" --out "$PRIVATE/aggregate"
python3 "$HERE/analyze.py" "$PRIVATE/aggregate"
python3 "$HERE/package_evidence.py" "$PRIVATE" --out "$PRIVATE/aggregate"
echo 'Finished. Review aggregates and explicit known native-suite limitation before publication.'
