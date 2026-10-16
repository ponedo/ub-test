#!/usr/bin/env python3
"""Execute unchanged old test logic against the explicitly approved native revision.

Only isolated bootstrap preflight pin/path checks are adapted, never test oracles.
The snapshot, bootstrap diff, commands and full logs remain as evidence.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
H=Path(__file__).resolve().parent; REPO=H.parents[1]; WORK=REPO.parent
sys.path.insert(0,str(H.parent/'prefill-cpu-profiling'))
from guard import run
p=argparse.ArgumentParser(); p.add_argument('--native',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
a.native=a.native.resolve(); a.out=a.out.resolve()
if a.out.exists(): raise RuntimeError('Refusing existing regression evidence')
a.out.mkdir(parents=True); snapshot=a.out/'source'
subprocess.run(['git','clone','--shared','--quiet',str(REPO),str(snapshot)],check=True)
head=subprocess.check_output(['git','-C',str(a.native),'rev-parse','HEAD'],text=True).strip()
subprocess.run(['git','-C',str(a.native),'diff','--quiet'],check=True)
subprocess.run(['git','-C',str(a.native),'diff','--cached','--quiet'],check=True)
base='d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b'
paths=['experiments/multi-npu-relay/build.sh','experiments/direct-weight-forward/build.sh','poc/chunk-relay/run.sh']
for name in paths:
 f=snapshot/name; content=f.read_text(); assert base in content; content=content.replace(base,head)
 if name=='poc/chunk-relay/run.sh':
  assert '[[ ! -d "$NS3_ROOT/.git" ]]' in content
  content=content.replace('[[ ! -d "$NS3_ROOT/.git" ]]','! git -C "$NS3_ROOT" rev-parse --git-dir >/dev/null 2>&1')
 f.write_text(content)
(a.out/'bootstrap-only.patch').write_bytes(subprocess.check_output(['git','diff'],cwd=snapshot))
(a.out/'native-provenance.json').write_text(json.dumps(dict(base=base,tested=head,bootstrap_files=paths),indent=2)+'\n')
env={'PATH':str(WORK/'prefill-cpu-tools/bin')+':'+os.path.dirname(sys.executable)+':/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','HOME':str(a.out/'home'),'PYTHONPATH':str(WORK/'prefill-cpu-tools'),'NS3_ROOT':str(a.native),'BUILD_TOOLS':str(WORK/'prefill-cpu-tools'),'EVIDENCE':str(a.out/'accepted'),'BUILD_JOBS':'4','RELAY_GRAPH_TOOL':str(a.out/'aux/graph-tool'),'LD_LIBRARY_PATH':str(a.native/'build/lib')}
r=run(['bash',snapshot/'experiments/multi-npu-relay/run.sh'],a.out/'host',1800,cwd=snapshot,case=a.out,env=env)
raise SystemExit(r['status']!='PASS')
