#!/usr/bin/env bash
# Install only in this checkout; no sudo and no changes to global tools.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .deps
deps=$(cd .deps && pwd)
cmake_bin=$(command -v cmake || true)
if [[ -z "$cmake_bin" ]]; then
    python3 -m pip install --target "$deps/python" cmake==4.4.4
    cmake_bin="$deps/python/cmake/data/bin/cmake"
fi
commit=5fc1469339775b54b1fcc2020ac744a58be5b50e
if [[ ! -d "$deps/systemc-src" ]]; then
    git clone --depth 1 --branch 2.3.4 https://github.com/accellera-official/systemc.git "$deps/systemc-src"
fi
[[ "$(git -C "$deps/systemc-src" rev-parse HEAD)" == "$commit" ]] || { echo 'SystemC source commit mismatch' >&2; exit 1; }
"$cmake_bin" -S "$deps/systemc-src" -B "$deps/systemc-build" \
    -DCMAKE_INSTALL_PREFIX="$deps/systemc" -DCMAKE_CXX_STANDARD=17 \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
"$cmake_bin" --build "$deps/systemc-build" -j "${JOBS:-4}"
"$cmake_bin" --install "$deps/systemc-build"
printf 'export SYSTEMC_PREFIX=%q\nexport CMAKE_BIN=%q\nexport CTEST_BIN=%q\n' \
    "$deps/systemc" "$cmake_bin" "$(dirname "$cmake_bin")/ctest" > "$deps/env.sh"
echo "Ready: source .deps/env.sh && ./scripts/run_e2e.sh"
