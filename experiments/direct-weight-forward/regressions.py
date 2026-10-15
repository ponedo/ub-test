#!/usr/bin/env python3
"""Run all accepted baselines without rewriting their tracked evidence."""
import argparse,hashlib,io,json,os,shutil,subprocess,sys,tarfile,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);a=p.parse_args()
HERE=Path(__file__).resolve().parent;repo=HERE.parents[1];out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
prior=Path(tempfile.mkdtemp(prefix='direct-forward-regression-',dir='/tmp'));snapshot=prior/'accepted';snapshot.mkdir()
blob=subprocess.check_output(['git','archive','a9ba52f6fdd2b7b5ef26913032aad2d11ab852ac'],cwd=repo)
with tarfile.open(fileobj=io.BytesIO(blob)) as archive:archive.extractall(snapshot,filter='data')
with (out/'prior-planner-console.txt').open('w') as f:subprocess.run(['bash','planner/quota/run.sh'],cwd=snapshot,stdout=f,stderr=subprocess.STDOUT,check=True)
(out/'prior-planner-root.txt').write_text(str(snapshot)+'\n')
network=prior/'network';env=dict(os.environ,EVIDENCE=str(network),NS3_ROOT=a.ns3)
with (out/'prior-network-console.txt').open('w') as f:subprocess.run(['bash',str(repo/'experiments/no-balancing-layer/run.sh')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
dest=out/'prior-regression';dest.mkdir(exist_ok=True)
for name in ['tests.txt','tests-optimized.txt','run-ledger.json','tool-versions.txt','poc-regression-console.txt','suite-console.txt']:shutil.copyfile(network/name,dest/name)
(dest/'raw-artifacts-sha256.json').write_text(json.dumps({str(f.relative_to(network)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(network.rglob('*')) if f.is_file()},indent=2)+'\n')
for name in ['tests-normal.txt','tests-optimized.txt','replication-tests-normal.txt','replication-tests-optimized.txt','compatible-tests-normal.txt','compatible-tests-optimized.txt','numeric-bounds.json']:shutil.copyfile(snapshot/'planner/quota/evidence'/name,dest/('planner-'+name))
(dest/'environment.json').write_text(json.dumps(dict(base='a9ba52f6fdd2b7b5ef26913032aad2d11ab852ac',ns3=subprocess.check_output(['git','-C',a.ns3,'rev-parse','HEAD'],text=True).strip(),tools=subprocess.check_output(['git','-C',a.ns3+'/scratch/ns-3-ub-tools','rev-parse','HEAD'],text=True).strip(),python=sys.version,raw_network_root=str(network)),indent=2)+'\n')
with (out/'legacy-parity-console.txt').open('w') as f:subprocess.run([sys.executable,str(HERE/'legacy_parity.py'),'--ns3',a.ns3,'--out',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
print('PASS: isolated Planner, complete NoBalancing/PoC regressions, cross-executor legacy parity.')
