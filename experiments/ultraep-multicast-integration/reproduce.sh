#!/usr/bin/env bash
set -euo pipefail
# Start with the accepted native retransmission tree from project commit 93033c1.
# See README for its fixed-base reconstruction. Private input paths are never published.
NATIVE=$(realpath "$1"); PRIVATE=$(realpath -m "$2")
ROUTING=$(realpath "$3"); MANIFEST=$(realpath "$4"); COUNTS=$(realpath "$5")
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$PRIVATE" ]] || { echo 'Fresh private output required' >&2; exit 2; }
python3 - "$HERE" "$NATIVE" <<'PY'
import hashlib,json,sys
from pathlib import Path
h,n=map(Path,sys.argv[1:])
for p,d in json.loads((h/'accepted-native-source-sha256.json').read_text()).items():assert hashlib.sha256((n/p).read_bytes()).hexdigest()==d,p
PY
for PATCH in peek-original-head allocator-revalidation; do
 git -C "$NATIVE" apply --check "$HERE/patches/$PATCH.patch"
 git -C "$NATIVE" apply "$HERE/patches/$PATCH.patch"
done
mkdir -p "$PRIVATE"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
for name,cmd in [('configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('full-native-build',['cmake','--build',n/'cmake-cache','-j4'])]:assert run(cmd,o/name,3600,case=o)['status']=='PASS'
PY
python3 "$HERE/build.py" --native "$NATIVE" --out "$PRIVATE/build-admission"
python3 "$HERE/stage-a.py" --build "$PRIVATE/build-admission" --native "$NATIVE" --out "$PRIVATE/stage-a"
python3 "$HERE/../ub-multicast-v2/build.py" --native "$NATIVE" --out "$PRIVATE/v2-fixtures"
python3 "$HERE/../ub-multicast-retransmission/build.py" --native "$NATIVE" --out "$PRIVATE/retx-fixtures"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
b=o/'legacy-build';b.mkdir();cmd=['c++','-std=c++20','-O3','-g',h.parent/'pair-jetty/pair-layer.cc','-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',b/'pair-layer'];assert run(cmd,b/'host',3600,case=o)['status']=='PASS'
PY
python3 "$HERE/regress.py" --stage-a "$PRIVATE/stage-a" --native "$NATIVE" --legacy-build "$PRIVATE/legacy-build" --v2-build "$PRIVATE/v2-fixtures" --retx-build "$PRIVATE/retx-fixtures" --out "$PRIVATE/regression"
python3 "$HERE/two-stage-regress.py" --build "$PRIVATE/build-admission" --legacy-build "$PRIVATE/legacy-build" --stage-a "$PRIVATE/stage-a" --out "$PRIVATE/two-stage-regression"
python3 "$HERE/stage-b.py" --build "$PRIVATE/build-admission" --native "$NATIVE" --stage-a "$PRIVATE/stage-a" --out "$PRIVATE/stage-b" --routing "$ROUTING" --manifest "$MANIFEST" --counts "$COUNTS"
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/compact-results"
