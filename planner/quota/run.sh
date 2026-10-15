#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
mkdir -p "$HERE/evidence"
"$PYTHON" "$HERE/reference/extract.py" > "$HERE/evidence/reference-build.txt"
"$PYTHON" "$HERE/tests/run_tests.py" > "$HERE/evidence/tests-normal.txt"
"$PYTHON" -O "$HERE/tests/run_tests.py" > "$HERE/evidence/tests-optimized.txt"
cat "$HERE/evidence/tests-normal.txt"
