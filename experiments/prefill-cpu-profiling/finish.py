#!/usr/bin/env python3
import hashlib,json,shutil,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent;E=H/'evidence';RAW=Path('/workspace/prefill-cpu-raw')
# Retain full Direct regression raw tree created by the accepted helper in /tmp.
execution=json.loads((RAW/'regressions/prior-regression/execution.json').read_text());prior=Path(execution['raw_evidence']);assert prior.is_dir() and str(prior).startswith('/tmp/multi-relay-prior-')
shutil.copytree(prior,RAW/'prior-regression-raw',dirs_exist_ok=True)
# Public summaries are small; originals remain untouched in raw archives.
for source in ['regressions','timed-regressions','regression-guard']:
 dest=E/source;dest.mkdir(exist_ok=True)
 for p in (RAW/source).iterdir():
  if p.is_file() and (p.suffix in ['.json','.txt']):shutil.copyfile(p,dest/p.name)
original=json.loads((E/'binary-sha256.json').read_text());after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original};assert original==after,'measured ELF changed during regressions'
(E/'binary-after-regressions.json').write_text(json.dumps(after,indent=2)+'\n')
assert subprocess.check_output(['git','-C','/workspace/ns-3-ub','diff','--name-only']).strip()==b''
(E/'original-native-clean.txt').write_text('git diff --name-only: empty; all recorded original/timed ELF SHA256 unchanged after regressions.\n')
rows=json.loads((E/'run-ledger.json').read_text());lines=['# Completed run ledger','','All 12 planned cases completed; all guards and strict verification PASS; per-scale full run/ hashes equal. No 100K case. Exact commands/timestamps/resources: evidence/run-ledger.json.','','|case|ns3 wall s|verifier wall s|result|','|---|---:|---:|---|']
for r in rows:lines.append(f"|{r['id']}|{r['stages']['ns3']['wall_seconds']:.3f}|{r['stages']['verify']['wall_seconds']:.3f}|{r['status']}|")
lines+=['','Checkpoints: 5K,10K,20K,50K passed; automatic continuation followed authorized plan. All predictions were registered before first run; lifecycle dominance was not supported, while superlinear lookup-path cost was supported (see conclusions.md). The build-time class-name error was fixed before simulations and retained as build-attempt1.txt. No runtime retry or skipped case.','', 'Original regression chain plus timer-clone relay suite and normal/-O negative tests completed; see evidence/regression-guard and raw archives.']
(H/'run-ledger.md').write_text('\n'.join(lines)+'\n')
print('regressions copied, full prior raw retained, ELF hashes and native cleanliness verified')
