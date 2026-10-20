#!/usr/bin/env python3
"""Merge only verified final-version results after both driver processes exit."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--drivers-exited',action='store_true',required=True);a=p.parse_args();r=a.root.resolve();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
x=json.loads((r/'ledger.json').read_text());m=json.loads((r/'multicast-parallel-result.json').read_text());admission=json.loads((r/'parallel-admission.json').read_text());held=Path(admission['held_binary']);original=held.with_name('layer');copy=Path(admission['identical_execution_binary'])
assert x['status']=='STOPPED' and str(original) in x['failure'] and 'No such file' in x['failure'],'Unexpected sequential stop; do not merge'
assert [z['status'] for z in x['runs']]==['PASS','PASS','PASS','PREPARED'] and m['status']=='PASS'
assert [z['strategy'] for z in x['runs']]==['no-balancing','direct','chunk-streaming','multicast-v2']
assert m['strategy']=='multicast-v2' and admission['status']=='ADMITTED'
assert m['binary_identity']==x['binary_identity']
assert m['simulator_host']['command'][0]==str(copy)
assert not original.exists() and sha(held)==sha(copy)==admission['binary_sha256']==x['binary_identity'][str(original)]
for path,digest in x['binary_identity'].items():assert sha(held if Path(path)==original else path)==digest
allrows=x['runs'][:3]+[m]
for row in allrows:
 d=r/row['strategy']
 for key,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert sha(d/name)==row[key]
 for stage in ['simulator','postflight','independent']:
  actual=json.loads((d/(stage+'-host')/'resource.json').read_text());assert actual==row[stage+'_host'] and actual['status']=='PASS' and actual['guard'] is None
 assert json.loads((d/'online-summary.json').read_text())==row['summary'] and json.loads((d/'validation.json').read_text())['status']=='PASS'
assert len({z['summary']['combine_fnv1a64'] for z in allrows})==1
backup=r/'ledger-before-parallel-merge.json';assert not backup.exists();backup.write_text((r/'ledger.json').read_text())
held.rename(original)
for row in allrows:row['execution_mode']='partly_concurrent_with_other_treatment' if row['strategy'] in ['chunk-streaming','multicast-v2'] else 'serial'
x.update(status='PASS',runs=allrows,parallel_execution=admission,parallel_handoff_note='Expected missing-executable identity gate prevented duplicate v2 launch; both drivers exited and all receipts verified before restoring identical executable.');x.pop('failure',None)
(r/'ledger.json').write_text(json.dumps(x,indent=2)+'\n');print('PASS all four frozen cases; parallel receipts merged without rerunning completed cases')
