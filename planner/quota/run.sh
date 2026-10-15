#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
mkdir -p "$HERE/evidence"
"$PYTHON" "$HERE/reference/extract.py" > "$HERE/evidence/reference-build.txt"
"$PYTHON" "$HERE/tests/run_tests.py" > "$HERE/evidence/tests-normal.txt"
"$PYTHON" -O "$HERE/tests/run_tests.py" > "$HERE/evidence/tests-optimized.txt"
"$PYTHON" "$HERE/reference/extract_replication.py" > "$HERE/evidence/replication-build.txt"
"$PYTHON" "$HERE/tests/test_replication_reference.py" > "$HERE/evidence/replication-tests-normal.txt"
"$PYTHON" -O "$HERE/tests/test_replication_reference.py" > "$HERE/evidence/replication-tests-optimized.txt"
"$PYTHON" "$HERE/tests/test_compatible.py" > "$HERE/evidence/compatible-tests-normal.txt"
"$PYTHON" -O "$HERE/tests/test_compatible.py" > "$HERE/evidence/compatible-tests-optimized.txt"
cat "$HERE/evidence/tests-normal.txt" "$HERE/evidence/replication-tests-normal.txt" "$HERE/evidence/compatible-tests-normal.txt"
