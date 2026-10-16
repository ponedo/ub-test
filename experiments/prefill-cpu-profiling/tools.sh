#!/usr/bin/env bash
# Install only under workspace; no sysctl, capabilities, or security changes.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
python3 - "$HERE/evidence/perf-packages.json" <<'PY'
import hashlib,json,pathlib,subprocess,sys,urllib.request
root=pathlib.Path('/workspace/prefill-cpu-tools');root.mkdir(exist_ok=True)
for name,m in json.load(open(sys.argv[1])).items():
 p=root/(name+'.deb');urllib.request.urlretrieve('https://deb.debian.org/debian/'+m['Filename'],p)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==m['SHA256']
 subprocess.run(['dpkg-deb','-x',str(p),str(root/'root')],check=True)
PY
if [ ! -d /workspace/prefill-cpu-tools/FlameGraph/.git ]; then
 git clone https://github.com/brendangregg/FlameGraph.git /workspace/prefill-cpu-tools/FlameGraph
fi
git -C /workspace/prefill-cpu-tools/FlameGraph checkout --detach 41fee1f99f9276008b7cd112fca19dc3ea84ac32
