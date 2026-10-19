#!/usr/bin/env bash
set -euo pipefail
# Existing accepted executables and private audited inputs are required.
NATIVE=$(realpath "$1"); BIN=$(realpath "$2"); GRAPH=$(realpath "$3")
REFERENCE=$(realpath "$4"); MANIFEST=$(realpath "$5"); COUNTS=$(realpath "$6")
PRIVATE=$7
[[ ! -e "$PRIVATE" ]] || { echo 'Use a fresh private output directory' >&2; exit 2; }
mkdir -p "$PRIVATE"; PRIVATE=$(realpath "$PRIVATE")
HERE=$(cd "$(dirname "$0")" && pwd)
COMMON=(--private "$PRIVATE" --reference "$REFERENCE" --binary "$BIN" --graph-tool "$GRAPH" --manifest "$MANIFEST" --counts "$COUNTS")
python3 "$HERE/run.py" --phase prepare-multicast "${COMMON[@]}"
python3 "$HERE/capacity.py" --private "$PRIVATE" --native "$NATIVE"
python3 "$HERE/run.py" --phase run "${COMMON[@]}"
mkdir -p "$PRIVATE/aggregates"
python3 "$HERE/verify_campaign.py" --private "$PRIVATE" --out "$PRIVATE/aggregates/campaign-verification.json"
python3 "$HERE/verify_baselines.py" --private "$PRIVATE" --historical "$REFERENCE" --out "$PRIVATE/aggregates/historical-parity.json"
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/aggregates"
MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/qwen-multicast-mpl}" python3 "$HERE/analyze.py" --results "$PRIVATE/aggregates"
echo 'Completed. Raw inputs remain private; review aggregates before publishing.'
