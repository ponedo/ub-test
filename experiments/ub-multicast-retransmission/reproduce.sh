#!/usr/bin/env bash
set -euo pipefail
NATIVE=$(realpath "$1")
PRIVATE=$(realpath -m "$2")
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$PRIVATE" ]] || { echo 'Fresh output required' >&2; exit 2; }
# Begin with fixed accepted pre-v2 native tree, same reconstruction as v2 README.
python3 - "$HERE" "$NATIVE" <<'PY'
import sys,json,hashlib
from pathlib import Path
h,n=map(Path,sys.argv[1:])
for p,d in json.loads((h.parent/'ub-multicast-fanout-header/native-source-sha256.json').read_text()).items():
 assert hashlib.sha256((n/p).read_bytes()).hexdigest()==d,p
PY
git -C "$NATIVE" apply --check "$HERE/../ub-multicast-v2/patches/native-write-v2.patch"
git -C "$NATIVE" apply "$HERE/../ub-multicast-v2/patches/native-write-v2.patch"
git -C "$NATIVE" apply --check "$HERE/patches/transport-fault-seam.patch"
git -C "$NATIVE" apply "$HERE/patches/transport-fault-seam.patch"
mkdir -p "$PRIVATE"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
for name,cmd in [('configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('native-build',['cmake','--build',n/'cmake-cache','--target','unified-bus','-j2'])]:
 assert run(cmd,o/name,3600,case=o)['status']=='PASS'
PY
python3 "$HERE/build.py" --native "$NATIVE" --out "$PRIVATE/fixtures"
python3 "$HERE/run.py" --build "$PRIVATE/fixtures" --out "$PRIVATE/matrix"
python3 "$HERE/../ub-multicast-v2/build.py" --native "$NATIVE" --out "$PRIVATE/v2-fixtures"
python3 "$HERE/../ub-multicast-v2/run.py" --build "$PRIVATE/v2-fixtures" --out "$PRIVATE/v2-regression"
python3 "$HERE/../ub-multicast-v2/regress.py" --native "$NATIVE" --out "$PRIVATE/old-regression"
python3 - "$HERE" "$PRIVATE" <<'PYCODE'
import sys,json
from pathlib import Path
h,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
assert run([sys.executable,h/'test-verifier.py',o/'matrix/data-once'],o/'final-verification/mutations',3600,case=o)['status']=='PASS'
(o/'verifier-mutations.json').write_text((o/'final-verification/mutations/console.txt').read_text())
r=run([sys.executable,'-O',h/'verify.py',o/'matrix/data-once','data-once'],o/'final-verification/optimized-rejection',3600,case=o)
assert r['returncode']!=0 and not r['guard'] and 'Assertions must remain enabled' in (o/'final-verification/optimized-rejection/console.txt').read_text()
a=json.loads((h.parent/'ub-multicast-v2/results/microbench.json').read_text());b=json.loads((o/'v2-regression/results.json').read_text())
fields=['case','mode','bytes','source_data_bytes','switch_data_bytes','source_packets','branches','group_complete_ps','receiver_ready_ps','sender_complete_ps','blocked_queries','peak_egress_bytes']
assert len(a)==len(b)==14
for x,y in zip(a,b):
 for k in fields:assert x[k]==y[k],(x['case'],k)
(o/'v2-parity.json').write_text(json.dumps(dict(cases=14,fields=fields,status='EXACT_MATCH'),indent=2)+'\n')
PYCODE
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/compact-results"
echo 'Review expected native exhaustion and bounded incomplete cases, not only process PASS.' 
