#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/../.."
root=$PWD
if [[ -z ${SYSTEMC_PREFIX:-} ]]; then
  ./scripts/bootstrap_systemc.sh
  source .deps/env.sh
fi
export SYSTEMC_PREFIX
export CMAKE_BIN=${CMAKE_BIN:-cmake}
export OPENCLICKNP_ROOT=${OPENCLICKNP_ROOT:-$root/.deps/openurma/openclicknp}
export OPENURMA_NATIVE_ROOT=${OPENURMA_NATIVE_ROOT:-$root/.deps/openurma/native}
export OPENURMA_PATCHED_ROOT=${OPENURMA_PATCHED_ROOT:-$root/.deps/openurma/patched}
python3 - <<'PY'
import json,os,subprocess
from pathlib import Path
m=json.loads(Path('third_party/openurma/UPSTREAM.json').read_text())
for env,url,commit in [('OPENCLICKNP_ROOT',m['openclicknp_url'],m['openclicknp_commit']),('OPENURMA_NATIVE_ROOT',m['openurma_url'],m['openurma_commit']),('OPENURMA_PATCHED_ROOT',m['openurma_url'],m['openurma_commit'])]:
 p=Path(os.environ[env]);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  subprocess.run(['git','clone','--no-checkout',url,str(p)],check=True)
  subprocess.run(['git','-C',str(p),'checkout','--detach',commit],check=True)
 assert subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD']).decode().strip()==commit,(env,'unexpected commit')
p=Path(os.environ['OPENURMA_PATCHED_ROOT']);target='elements/protocols/ub/UB_Jetty_Sched.clnp'
overlay=Path('openurma',target).read_bytes()
if (p/target).read_bytes()!=overlay:
 native=subprocess.check_output(['git','-C',str(p),'show','HEAD:'+target])
 assert (p/target).read_bytes()==native,'unexpected edits in patched source'
 subprocess.run(['git','-C',str(p),'apply',str(Path('patches/openurma/0001-jetty-rr-drr.patch').resolve())],check=True)
assert (p/target).read_bytes()==overlay
assert subprocess.check_output(['git','-C',str(p),'diff','--name-only']).decode().splitlines()==[target],'unexpected edits in patched tree'
assert not subprocess.check_output(['git','-C',os.environ['OPENCLICKNP_ROOT'],'status','--porcelain']).strip(),'compiler tree must be pristine'
assert not subprocess.check_output(['git','-C',os.environ['OPENURMA_NATIVE_ROOT'],'status','--porcelain']).strip(),'native tree must be pristine'
PY
"$CMAKE_BIN" -S "$OPENCLICKNP_ROOT" -B "$OPENCLICKNP_ROOT/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$SYSTEMC_PREFIX"
"$CMAKE_BIN" --build "$OPENCLICKNP_ROOT/build" --target openclicknp-cc -j "${JOBS:-4}"
mkdir -p .deps/openurma
printf 'export SYSTEMC_PREFIX=%q\nexport CMAKE_BIN=%q\nexport OPENCLICKNP_ROOT=%q\nexport OPENURMA_NATIVE_ROOT=%q\nexport OPENURMA_PATCHED_ROOT=%q\n' \
  "$SYSTEMC_PREFIX" "$CMAKE_BIN" "$OPENCLICKNP_ROOT" "$OPENURMA_NATIVE_ROOT" "$OPENURMA_PATCHED_ROOT" > .deps/openurma/env.sh
printf '%s\n' 'Ready: source .deps/openurma/env.sh && ./scripts/openurma/run.sh'
