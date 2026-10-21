#!/usr/bin/env bash
# Requires a prepared accepted native tree; never reruns the old full real matrix.
set -euo pipefail
[[ -z "${PYTHONOPTIMIZE:-}" ]] || { echo "Unset PYTHONOPTIMIZE; assertions are mandatory" >&2; exit 2; }
if [[ $# != 5 ]]; then
  echo 'Usage: reproduce.sh ACCEPTED_NATIVE FRESH_PRIVATE ROUTING MANIFEST COUNTS' >&2
  exit 2
fi
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
NATIVE=$(realpath "$1"); PRIVATE=$(realpath -m "$2")
ROUTING=$(realpath "$3"); MANIFEST=$(realpath "$4"); COUNTS=$(realpath "$5")
[[ ! -e "$PRIVATE" ]] || { echo 'Fresh private output required' >&2; exit 2; }
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
python3 - "$HERE" "$ROOT" "$NATIVE" "$PRIVATE" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
h,root,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h));from guard import run
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((h.parent/'ultraep-multicast-integration/candidate-native-source-sha256.json').read_text())
assert len(manifest)==109
assert all(sha(n/p)==v for p,v in manifest.items()), 'Native tree does not match accepted patches'
commit='3c2275eafea79426a441c819c8b65268492ff08e'
diff_command=['git','-C',str(root),'diff','--name-only',commit,'--','.',':(exclude)experiments/cloudmatrix-bandwidth']
project_diff=subprocess.check_output(diff_command)
assert not project_diff, 'Changes outside new experiment directory'
accepted=subprocess.check_output(['git','-C',str(root),'ls-tree','-r','--name-only',commit],text=True).splitlines()
# All historical project files, not just the executor, must still match.
for name in accepted:
    path=root/name
    assert path.is_file(), 'Missing accepted project file: '+name
    expected=subprocess.check_output(['git','-C',str(root),'show',commit+':'+name])
    assert path.read_bytes()==expected, 'Accepted project file changed: '+name
sources={str((root/name).resolve()):sha(root/name) for name in accepted
         if (root/name).is_file() and ((root/name).suffix in ['.py','.cc','.h','.hpp'] or name.endswith('fixed-config.json') or name.endswith('candidate-native-source-sha256.json'))}
for path in (n/'src').rglob('*'):
    if path.is_file() and path.suffix in ['.py','.cc','.h','.hpp','.cmake','.txt']:
        sources[str(path.resolve())]=sha(path)
o.mkdir(parents=True)
(o/'source-identity.json').write_text(json.dumps(sources,indent=2)+'\n')
(o/'source-provenance.json').write_text(json.dumps(dict(status='PASS',accepted_commit=commit,project_tracked_diff_empty=not bool(project_diff),project_diff_command=diff_command,project_diff_sha256=hashlib.sha256(project_diff).hexdigest(),accepted_project_files_byte_checked=len(accepted),native_candidate_hashes_verified=len(manifest),private_source_identity_sha256=sha(o/'source-identity.json'),private_source_identity_entries=len(sources),note='Regenerated reproduction identity; absolute paths and hashes are not claimed identical to original-run binaries.'),indent=2)+'\n')
for name,cmd in [('native-configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('native-full-build',['cmake','--build',n/'cmake-cache','-j2'])]:
    result=run(cmd,o/name,4800,case=o)
    assert result['status']=='PASS' and result['guard'] is None
PY
python3 "$HERE/../qwen-roofline-compute/build.py" --native "$NATIVE" --out "$PRIVATE/build"
python3 - "$HERE" "$NATIVE" "$PRIVATE" <<'PY'
import sys
from pathlib import Path
h,n,o=map(Path,sys.argv[1:]);sys.path.insert(0,str(h));from guard import run
cmd=['c++','-std=c++20','-O2','-g',h/'rate-probe.cc','-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',o/'build/rate-probe']
assert run(cmd,o/'build/rate-probe-build',1800,case=o)['status']=='PASS'
PY
python3 "$HERE/../qwen-roofline-compute/test-model.py" "$PRIVATE/build/model-probe" "$PRIVATE/model-unit"
python3 "$HERE/stage-a.py" --build "$PRIVATE/build" --native "$NATIVE" --out "$PRIVATE/stage-a" --source-identity "$PRIVATE/source-identity.json" --reference "$HERE/../qwen-roofline-compute/results/stage-a"
python3 "$HERE/prepare.py" --build "$PRIVATE/build" --native "$NATIVE" --stage-a "$PRIVATE/stage-a" --out "$PRIVATE/real-3136" --source-identity "$PRIVATE/source-identity.json" --routing "$ROUTING" --manifest "$MANIFEST" --counts "$COUNTS"
python3 "$HERE/run-real.py" "$PRIVATE/real-3136" --build "$PRIVATE/build"
python3 "$HERE/collect.py" --private "$PRIVATE" --out "$PRIVATE/results" --source-provenance "$PRIVATE/source-provenance.json"
MPLCONFIGDIR="$PRIVATE/mpl-cache" python3 "$HERE/plot.py" "$PRIVATE/results"
cp "$HERE/README.md" "$HERE/HARDWARE-REFERENCE.md" "$HERE/source-audit.md" "$HERE/HIGH-BANDWIDTH-ANALYSIS.md" "$PRIVATE/"
python3 "$HERE/report.py" "$PRIVATE/results" --out "$PRIVATE/REPORT.md"
echo "Validated bounded evidence: $PRIVATE/results; report: $PRIVATE/REPORT.md"
