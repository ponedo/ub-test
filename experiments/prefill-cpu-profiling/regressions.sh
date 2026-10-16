#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=$(cd -- "$HERE/../.." && pwd)
cd "$REPO"
CAPACITY_RAW=/workspace/prefill-cpu-raw NS3_ROOT=/workspace/ns-3-ub bash experiments/prefill-capacity/regressions.sh
# The diagnostic app must not be overwritten by the suite build helper.
mkdir -p /workspace/prefill-cpu-raw/timed-regressions
python3.12 experiments/multi-npu-relay/suite.py --ns3 /workspace/prefill-cpu-native --out /workspace/prefill-cpu-raw/timed-regressions > /workspace/prefill-cpu-raw/timed-regressions/suite-console.txt 2>&1
python3.12 experiments/multi-npu-relay/tests.py --ns3 /workspace/prefill-cpu-native --out /workspace/prefill-cpu-raw/timed-regressions > /workspace/prefill-cpu-raw/timed-regressions/tests-console.txt 2>&1
python3.12 -O experiments/multi-npu-relay/tests.py --ns3 /workspace/prefill-cpu-native --out /workspace/prefill-cpu-raw/timed-regressions > /workspace/prefill-cpu-raw/timed-regressions/tests-optimized-console.txt 2>&1
