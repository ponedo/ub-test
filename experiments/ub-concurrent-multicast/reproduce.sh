#!/usr/bin/env bash
set -euo pipefail
NATIVE=$(cd "$1" && pwd)
OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ! -e "$OUT" ]] || { echo 'Choose a fresh private output directory' >&2; exit 2; }
# Native protocol code is the accepted lightweight-adapter baseline, unchanged here.
mkdir -p "$OUT"
python3 - "$HERE" "$NATIVE" "$OUT" <<'PY'
import sys,json,hashlib
from pathlib import Path
h,n,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);e=h.parent;sys.path.insert(0,str(e/'wqe-completion-fix'));from guard import run
for relative,digest in json.loads((h/'native-source-sha256.json').read_text()).items():assert hashlib.sha256((n/relative).read_bytes()).hexdigest()==digest,relative
r=run(['cmake','--build',n/'cmake-cache','--target','unified-bus','-j2'],o/'native-build',3600,case=o);assert r['status']=='PASS'
for name,src in [('concurrent',h/'concurrent.cc'),('pair-layer',e/'pair-jetty/pair-layer.cc'),('graph-tool',e/'multi-npu-relay/graph-tool.cc')]:
 cmd=['c++','-std=c++20','-O3','-g',src]
 if name!='graph-tool':cmd+=['-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core']
 r=run(cmd+['-o',o/name],o/(name+'-build'),3600,case=o);assert r['status']=='PASS'
PY
python3 "$HERE/run-concurrent.py" --binary "$OUT/concurrent" --out "$OUT/concurrent-results"
python3 "$HERE/run-layer.py" --binary "$OUT/pair-layer" --graph-tool "$OUT/graph-tool" --out "$OUT/layer" --case all
python3 "$HERE/run-layer.py" --binary "$OUT/pair-layer" --graph-tool "$OUT/graph-tool" --out "$OUT/debug" --case topk2_4 --log-level debug
python3 "$HERE/test-layer-faults.py" --binary "$OUT/pair-layer" --graph-tool "$OUT/graph-tool" --input "$OUT/layer/topk2_4/multicast" --out "$OUT/faults"
python3 "$HERE/verify-debug.py" --summary "$OUT/layer/topk2_4" --debug "$OUT/debug/topk2_4" --out "$OUT/debug-parity.json"
echo 'PASS; review private results, including explicit limitations, before interpreting performance.'
