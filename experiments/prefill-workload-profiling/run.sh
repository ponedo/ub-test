#!/usr/bin/env bash
set -euo pipefail
module_dir="$(cd "$(dirname "$0")" && pwd)"
profile_cache="${PROFILE_CACHE:-/workspace/prefill-profile-cache/run}"
profile_venv="${PROFILE_VENV:-/workspace/prefill-profile-venv}"
profile_out="${PROFILE_OUT:-$module_dir/evidence}"
mkdir -p "$profile_out"
if [ ! -x "$profile_venv/bin/python" ]; then python3 -m venv "$profile_venv"; fi
"$profile_venv/bin/python" -m pip install -r "$module_dir/requirements.lock.txt" > "$profile_out/install.log" 2>&1
"$profile_venv/bin/python" "$module_dir/prepare.py" --cache "$profile_cache" --out "$profile_out" 2>&1 | tee "$profile_out/prepare.log"
"$profile_venv/bin/python" "$module_dir/profile.py" --cache "$profile_cache" --out "$profile_out" 2>&1 | tee "$profile_out/profile.log"
"$profile_venv/bin/python" "$module_dir/research.py" --cache "$profile_cache" --out "$profile_out" 2>&1 | tee "$profile_out/research.log"
"$profile_venv/bin/python" "$module_dir/statistics.py" --out "$profile_out" 2>&1 | tee "$profile_out/statistics.log"
"$profile_venv/bin/python" "$module_dir/audit.py" --out "$profile_out" 2>&1 | tee "$profile_out/audit.log"
"$profile_venv/bin/python" "$module_dir/report.py" --out "$profile_out"
"$profile_venv/bin/python" "$module_dir/check.py" --cache "$profile_cache" --out "$profile_out" 2>&1 | tee "$profile_out/check.log"
"$profile_venv/bin/python" "$module_dir/manifest.py" --out "$profile_out"
