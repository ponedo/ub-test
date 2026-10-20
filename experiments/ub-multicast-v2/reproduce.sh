#!/usr/bin/env bash
set -euo pipefail
# Input: disposable accepted native tree (original fixed base + three historical patches).
# Build tools cmake/ninja/c++ and Python+psutil must be available on PATH.
NATIVE=$(realpath "$1")
PRIVATE=$(realpath -m "$2")
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$PRIVATE" ]] || { echo 'Fresh private output directory required' >&2; exit 2; }
python3 - "$HERE" "$NATIVE" <<'PY'
import json,hashlib,sys
from pathlib import Path
h,n=map(Path,sys.argv[1:])
for p,digest in json.loads((h.parent/'ub-multicast-fanout-header/native-source-sha256.json').read_text()).items():
 if hashlib.sha256((n/p).read_bytes()).hexdigest()!=digest:raise SystemExit('Wrong accepted source: '+p)
PY
git -C "$NATIVE" apply --check "$HERE/patches/native-write-v2.patch"
git -C "$NATIVE" apply "$HERE/patches/native-write-v2.patch"
mkdir -p "$PRIVATE"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
commands=[('configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('build',['cmake','--build',n/'cmake-cache','--target','unified-bus','-j2'])]
for name,cmd in commands:
 if run(cmd,o/name,3600,case=o)['status']!='PASS':raise SystemExit(2)
PY
python3 "$HERE/build.py" --native "$NATIVE" --out "$PRIVATE/fixtures"
python3 "$HERE/run.py" --build "$PRIVATE/fixtures" --out "$PRIVATE/matrix"
python3 "$HERE/regress.py" --native "$NATIVE" --out "$PRIVATE/regressions"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys,json
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
r=run(['cmake','--build',n/'cmake-cache','--target','test-runner','scratch_ub-quick-example','-j2'],o/'native-tests-build',3600,case=o)
if r['status']!='PASS':raise SystemExit(2)
r=run([sys.executable,h.parent/'ub-network-multicast-poc/run-native-tests.py','--native',n,'--out',o/'native-tests'],o/'native-tests-host',3600,case=o)
# Preserve original known missing-parser failure as a failure, not a passed suite.
import subprocess
subprocess.run([sys.executable,h/'check-native.py',n,o],check=True)
PY
python3 "$HERE/test-native-gate.py"
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/compact-results"
echo "Finished; inspect explicit native suite failures and compact results: $PRIVATE/compact-results"
