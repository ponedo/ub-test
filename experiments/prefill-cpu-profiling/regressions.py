#!/usr/bin/env python3
"""Run accepted regressions after measurement; no concurrency with matrix."""
import os,sys,json,subprocess,shutil,time
from pathlib import Path
from execute import H,REPO,WORK,RAW,env
from guard import run
# PoC deliberately requires a clean tracked native tree. Reverse only our exact
# diagnostic patch after formal ELF freezing; never discard unrelated edits.
native=WORK/'prefill-cpu-native';patch=H/'evidence/native-timing.patch'
if subprocess.run(['git','diff','--quiet'],cwd=native).returncode:
 subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=native,check=True)
 subprocess.run(['git','apply','--reverse',str(patch)],cwd=native,check=True)
 subprocess.run(['git','diff','--quiet'],cwd=native,check=True)
out=RAW/'regressions';out.mkdir(parents=True,exist_ok=True)
if (out/'accepted').exists():
 previous=out/('previous-'+str(time.time_ns()));previous.mkdir()
 for item in list(out.iterdir()):
  if item!=previous and not item.name.startswith('previous-'):shutil.move(str(item),previous/item.name)
 if (H/'evidence/regression-resource.json').exists():shutil.copy2(H/'evidence/regression-resource.json',previous/'resource.json')
en=env();en.update(NS3_ROOT=str(WORK/'prefill-cpu-native'),BUILD_TOOLS=str(WORK/'prefill-cpu-tools'),EVIDENCE=str(out/'accepted'),BUILD_JOBS='4',LD_LIBRARY_PATH=str(WORK/'prefill-cpu-native/build/lib'))
before_tmp=set(Path('/tmp').glob('multi-relay-prior-*'))|set(Path('/tmp').glob('direct-forward-regression-*'))
r=run(['bash',REPO/'experiments/multi-npu-relay/run.sh'],out/'host',1800,cwd=REPO,case=out,env=en)
after_tmp=set(Path('/tmp').glob('multi-relay-prior-*'))|set(Path('/tmp').glob('direct-forward-regression-*'))
r['retained_temporary_roots']=[str(p) for p in sorted(after_tmp-before_tmp)]
(H/'evidence/regression-resource.json').write_text(json.dumps(r,indent=2)+'\n')
raise SystemExit(r['status']!='PASS')
