"""Run accepted Direct plus all older milestones without changing tracked evidence."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--ns3',default='/workspace/ns-3-ub');a=p.parse_args()
root=Path(__file__).resolve().parent;out=Path(a.out).resolve();dest=out/'prior-regression';dest.mkdir(parents=True,exist_ok=True)
prior=Path(tempfile.mkdtemp(prefix='multi-relay-prior-',dir='/tmp'))
# Current Direct source is unchanged except the backwards-compatible strategy header.
# Its run.sh includes isolated accepted Planner, NoBalancing, PoC and legacy parity.
cmd=['bash',str(root.parent/'direct-weight-forward/run.sh')]
with (dest/'console.txt').open('w') as f:subprocess.run(cmd,env=dict(os.environ,EVIDENCE=str(prior),NS3_ROOT=a.ns3),stdout=f,stderr=subprocess.STDOUT,check=True)
for name in ['build.txt','suite-console.txt','tests-console.txt','tests-optimized-console.txt','tests.json','regressions-console.txt','comparison.json','run-ledger.json','legacy-parity.json']:
 shutil.copyfile(prior/name,dest/name)
shutil.copytree(prior/'prior-regression',dest/'older',dirs_exist_ok=True)
(dest/'artifact-sha256.json').write_text(json.dumps({str(f.relative_to(prior)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(prior.rglob('*')) if f.is_file()},indent=2)+'\n')
(dest/'execution.json').write_text(json.dumps(dict(command=cmd,returncode=0,raw_evidence=str(prior),base='ea78e1ba7ce7fce7caa747b96d02c3d324765383'),indent=2)+'\n')
print('PASS: accepted Direct 26 runs and all prior Planner/NoBalancing/ChunkRelay regressions')
