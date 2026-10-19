#!/usr/bin/env bash
set -euo pipefail
# Existing reconstructed native tree from the previous network PoC; fresh output directory.
NATIVE=$(cd "$1" && pwd)
OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$OUT" ]] || { echo 'Choose a fresh private output directory' >&2; exit 2; }
export CLICOLOR=0
# On an unmodified PoC tree, apply patches/lightweight-adapter.patch first.
# All compilation and tests are sequential. Existing dependency toolchain must be available.
mkdir -p "$OUT"
python3 - "$HERE" "$NATIVE" "$OUT" <<'PY'
import sys
from pathlib import Path
h,n,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
r=run(['cmake','--build',n/'cmake-cache','--target','unified-bus','-j2'],o/'native-build',3600,case=o);assert r['status']=='PASS'
for name in ['singleton','multitarget']:
 cmd=['c++','-std=c++20','-O3','-g',h/(name+'.cc'),'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',o/name]
 r=run(cmd,o/(name+'-build'),3600,case=o);assert r['status']=='PASS'
PY
python3 "$HERE/run-singleton.py" --shared --binary "$OUT/singleton" --private "$OUT/singleton-evidence"
python3 "$HERE/run-multi.py" --binary "$OUT/multitarget" --private "$OUT/multi-evidence" --singleton-gate "$OUT/singleton-evidence/results.json"
python3 "$HERE/test-verifier.py" "$OUT/multi-evidence/three-target" --out "$OUT/verifier-mutations"
echo "PASS; private evidence: $OUT"
