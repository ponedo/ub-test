#!/usr/bin/env bash
set -euo pipefail
module_dir="$(cd "$(dirname "$0")" && pwd)"
repo_dir="$(cd "$module_dir/../.." && pwd)"
cd "$repo_dir"
export EVIDENCE="${CAPACITY_RAW:-/workspace/prefill-capacity-raw}/regressions"
export NS3_ROOT="${NS3_ROOT:-/workspace/ns-3-ub}"
export BUILD_JOBS=4
bash experiments/multi-npu-relay/run.sh
