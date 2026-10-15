#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
NS3_ROOT=${NS3_ROOT:-/workspace/ns-3-ub}
EVIDENCE=${EVIDENCE:-"$HERE/evidence"}
PYTHON=${PYTHON:-python3.12}
mkdir -p "$EVIDENCE"
EVIDENCE=$(cd "$EVIDENCE" && pwd)
EVIDENCE="$EVIDENCE" bash "$HERE/build.sh"
"$PYTHON" "$HERE/suite.py" --ns3 "$NS3_ROOT" --out "$EVIDENCE" > "$EVIDENCE/suite-console.txt" 2>&1
"$PYTHON" "$HERE/tests.py" --ns3 "$NS3_ROOT" --out "$EVIDENCE" > "$EVIDENCE/tests-console.txt" 2>&1
"$PYTHON" -O "$HERE/tests.py" --ns3 "$NS3_ROOT" --out "$EVIDENCE" > "$EVIDENCE/tests-optimized-console.txt" 2>&1
"$PYTHON" "$HERE/regressions.py" --ns3 "$NS3_ROOT" --out "$EVIDENCE" > "$EVIDENCE/regressions-console.txt" 2>&1
printf 'PASS: direct-weight-forward matrix and ordinary/optimized checks.\n'
