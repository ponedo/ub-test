#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${SYSTEMC_PREFIX:?source .deps/openurma/env.sh first}"
: "${OPENCLICKNP_ROOT:?}"
: "${OPENURMA_NATIVE_ROOT:?}"
: "${OPENURMA_PATCHED_ROOT:?}"
out=${OPENURMA_RESULTS:-experiments/openurma/results}
mkdir -p "$out/build"
export CPATH="$SYSTEMC_PREFIX/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$SYSTEMC_PREFIX/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export LD_LIBRARY_PATH="$SYSTEMC_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
for variant in native patched; do
  if [[ $variant == native ]]; then repo=$OPENURMA_NATIVE_ROOT; extra=(-DOPENURMA_NATIVE); else repo=$OPENURMA_PATCHED_ROOT; extra=(); fi
  bash "$repo/scripts/build_swemu.sh" > "$out/build/$variant.txt" 2>&1
  python3 - "$repo" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1])/'build/openurma_gen/systemc';s=(p/'topology.cpp').read_text()
assert 'int sc_main' in s
s=s[:s.index('int sc_main')].replace('#include "openclicknp/sc_runtime.hpp"','#include "openclicknp/sc_runtime.hpp"\nusing namespace openclicknp;')
(p/'topology_no_main.cpp').write_text(s)
PY
  g++ -std=c++17 -O2 -DSC_INCLUDE_DYNAMIC_PROCESSES "${extra[@]}" \
    -I "$OPENCLICKNP_ROOT/runtime/include" -I "$repo/runtime/openurma/include" \
    -I "$repo/build/openurma_gen/systemc" experiments/openurma/component.cpp \
    -L "$SYSTEMC_PREFIX/lib" -Wl,-rpath,"$SYSTEMC_PREFIX/lib" -lsystemc -lpthread -o "$repo/build/component"
done
