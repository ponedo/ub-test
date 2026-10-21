#!/usr/bin/env bash
# This file records commands; execution/build authority belongs to the parent.
# Supply verified absolute paths. Preparation does not build or run simulations.
set -euo pipefail
: "${BUILD:?}" "${NATIVE:?}" "${ROUTING:?}" "${MANIFEST:?}" "${COUNTS:?}" "${SOURCE_IDENTITY:?}"
HERE=$(cd "$(dirname "$0")" && pwd)
PRIVATE=/workspace/scratch/c6ba02920254/bandwidth-private
python "$HERE/prepare.py" --build "$BUILD" --native "$NATIVE" --stage-a "$PRIVATE/stage-a" --source-identity "$SOURCE_IDENTITY" --routing "$ROUTING" --manifest "$MANIFEST" --counts "$COUNTS" --out "$PRIVATE/real-3136"
python "$HERE/run-real.py" "$PRIVATE/real-3136" --build "$BUILD"
