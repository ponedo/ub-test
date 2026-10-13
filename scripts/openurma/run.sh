#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/../.."
out=${OPENURMA_RESULTS:-experiments/openurma/results}
mkdir -p "$out/upstream"
./scripts/openurma/build.sh
export CPATH="$SYSTEMC_PREFIX/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$SYSTEMC_PREFIX/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export LD_LIBRARY_PATH="$SYSTEMC_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Preserve exit status directly; no PASS/FAIL grep pipeline masks a failure.
for variant in native patched; do
  if [[ $variant == native ]]; then repo=$OPENURMA_NATIVE_ROOT; else repo=$OPENURMA_PATCHED_ROOT; fi
  for test in test_fence test_multi_ini_parallel test_tx_wire test_multi_flit_write test_roi_ordering test_rot_ordering; do
    (cd "$repo" && bash scripts/run_test.sh "tests/swemu/$test.cpp") > "$out/upstream/${variant}_$test.txt" 2>&1
  done
done
(cd "$OPENURMA_NATIVE_ROOT" && bash scripts/build_systemc.sh tests/systemc/test_sc_latency.cpp) > "$out/upstream/sc_latency.txt" 2>&1
python3 -m experiments.openurma.run --native "$OPENURMA_NATIVE_ROOT/build/component" --patched "$OPENURMA_PATCHED_ROOT/build/component" --output "$out" | tee "$out/validation.txt"
python3 -m experiments.openurma.provenance "$out"
