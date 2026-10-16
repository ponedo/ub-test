#!/usr/bin/env python3
"""Retain bulky decode/calibration/regression evidence outside the source tree."""
import json,shutil
from pathlib import Path
from execute import H,RAW
for p in sorted((H/'evidence/analysis').glob('*/perf-script.txt')) + sorted((H/'evidence/analysis').glob('*/stacks-count.folded')):
 target=RAW/'analysis-raw'/p.parent.name/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.move(p,target)
for p in sorted((H/'evidence').glob('calibration2.data')):
 target=RAW/'calibration'/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.move(p,target)
# Preserve the zero-sample official CLI failure as well, if this local probe exists.
probe=Path('/tmp/official-perf-empty.data')
if probe.exists():
 target=RAW/'calibration'/probe.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(probe,target)
# Older regression drivers use isolated /tmp trees. Retain their complete artifacts.
for record in list((RAW/'regressions').rglob('execution.json')):
 try:data=json.loads(record.read_text())
 except (OSError,ValueError):continue
 old=data.get('raw_evidence')
 if old and str(old).startswith('/tmp/') and Path(old).is_dir():
  dest=RAW/'regressions/retained-prior'/Path(old).name
  if not dest.exists():shutil.copytree(old,dest)
print('Bulky evidence retained for attachments; source report stays small')

# Also preserve failed-driver trees (which never reached execution.json).
for rootfile in [H/'evidence/regression-resource.json'] + list((RAW/'regressions').rglob('resource.json')):
 if not rootfile.exists():continue
 for old in json.loads(rootfile.read_text()).get('retained_temporary_roots',[]):
  source=Path(old)
  if source.is_dir() and source.parent==Path('/tmp'):
   dest=RAW/'regressions/retained-prior'/source.name
   if not dest.exists():shutil.copytree(source,dest)
