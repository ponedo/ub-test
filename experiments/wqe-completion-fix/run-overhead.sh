#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
: "${INDEX_BIN:?}" "${INDEX_LIB:?}" "${FIX_BIN:?}" "${FIX_LIB:?}" "${INPUTS_RAW:?}" "${BUILD_TOOLS:?}" "${GRAPH_TOOL:?}" "${OUT:?}"
# Reuse the accepted byte-for-byte verifier and resource guard. Harness arm A here is
# native B (index-only); harness arm B here is native C (index + completion fix).
for scale in 5000 10000; do
 for trial in 1 2 3; do
  python3 "$HERE/run-harness.py" --execute --arm A --assignments "$scale" --phase timing --attempt "$scale-index-$trial" --raw "$OUT" --inputs-raw "$INPUTS_RAW" --binary "$INDEX_BIN" --lib "$INDEX_LIB" --tools "$BUILD_TOOLS" --graph-tool "$GRAPH_TOOL"
  python3 "$HERE/run-harness.py" --execute --arm B --assignments "$scale" --phase timing --attempt "$scale-fix-$trial" --reference "$OUT/$scale-index-$trial" --raw "$OUT" --inputs-raw "$INPUTS_RAW" --binary "$FIX_BIN" --lib "$FIX_LIB" --tools "$BUILD_TOOLS" --graph-tool "$GRAPH_TOOL"
 done
done
