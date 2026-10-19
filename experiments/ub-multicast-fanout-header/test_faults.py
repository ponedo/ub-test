#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for header in ['full','compact-oracle','ideal-oracle']:
 for fault,reason in [('weight-byte','payload byte mismatch'),('early-wqe','sender completed before target data ready'),('duplicate-completion','audit premature/duplicate sender completion'),('premature-ready','ready before target completion coverage'),('missing-wqe','unfinished native transfer')]:
  name=header+'-'+fault;d=a.out/name
  r=run([a.binary,'--out='+str(d),'--fanout=3','--bytes=12288','--strategy=multicast','--headerModel='+header,'--fault='+fault],a.out/'hosts'/name,3600,case=a.out);text=(a.out/'hosts'/name/'console.txt').read_text();ok=r['returncode']!=0 and r['guard'] is None and reason in text
  rows.append(dict(case=name,status='PASS' if ok else 'FAIL',expected_failure=reason,returncode=r['returncode'],guard=r['guard']));(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert ok,(name,text)
for fault,reason in [('early-relay','relay before target chunk ready'),('relay-buffer-byte','payload byte mismatch')]:
 name='chunk-'+fault;d=a.out/name;r=run([a.binary,'--out='+str(d),'--fanout=4','--bytes=12288','--strategy=chunk-streaming','--fault='+fault],a.out/'hosts'/name,3600,case=a.out);text=(a.out/'hosts'/name/'console.txt').read_text();ok=r['returncode']!=0 and not r['guard'] and reason in text;rows.append(dict(case=name,status='PASS' if ok else 'FAIL',expected_failure=reason,returncode=r['returncode'],guard=r['guard']));(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert ok,(name,text)
print('FAULTS PASS',len(rows))
