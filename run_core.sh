#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
CXX="${CXX:-g++}"
"$CXX" -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude tests/test_core.cpp -o build/test_core
"$CXX" -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude bench/scheduler_microbench.cpp -o build/scheduler_microbench
build/test_core
build/scheduler_microbench results.csv
