#!/usr/bin/env bash
set -euo pipefail
NATIVE=$(realpath "$1"); PRIVATE=$(realpath -m "$2"); ROUTING=$(realpath "$3"); MANIFEST=$(realpath "$4"); COUNTS=$(realpath "$5")
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$PRIVATE" ]] || { echo 'Fresh private output required' >&2; exit 2; }
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import hashlib,json,sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h));from guard import run
for p,v in json.loads((h.parent/'ultraep-multicast-integration/candidate-native-source-sha256.json').read_text()).items():assert hashlib.sha256((n/p).read_bytes()).hexdigest()==v,p
o.mkdir()
for name,cmd in [('native-configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('native-full-build',['cmake','--build',n/'cmake-cache','-j2'])]:assert run(cmd,o/name,4800,case=o)['status']=='PASS'
PY
python3 "$HERE/build.py" --native "$NATIVE" --out "$PRIVATE/build"
python3 "$HERE/stage-a.py" --build "$PRIVATE/build" --native "$NATIVE" --out "$PRIVATE/stage-a"
python3 "$HERE/prepare-real.py" --build "$PRIVATE/build" --native "$NATIVE" --stage-a "$PRIVATE/stage-a" --out "$PRIVATE/real" --routing "$ROUTING" --manifest "$MANIFEST" --counts "$COUNTS"
python3 "$HERE/run-real.py" "$PRIVATE/real" --build "$PRIVATE/build"
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/results"
MPLCONFIGDIR="$PRIVATE/mpl-cache" python3 "$HERE/plot.py" "$PRIVATE/results"
cp "$HERE/MODEL.md" "$HERE/README.md" "$PRIVATE/"
python3 "$HERE/report.py" "$PRIVATE/results" --out "$PRIVATE/REPORT.md"
