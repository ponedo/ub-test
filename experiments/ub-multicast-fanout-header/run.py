#!/usr/bin/env python3
"""Execute only the preregistered matrix, sequentially with unchanged host guards."""
import argparse,hashlib,json,sys
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['small','main','ideal'],required=True);a=p.parse_args();root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
 ledger_path=root/(a.phase+'-ledger.json')
 if ledger_path.exists():raise RuntimeError('Fresh phase required; preserve prior ledger, no implicit resume')
 def gate(phase):
  rows=json.loads((root/(phase+'-ledger.json')).read_text());required=[r for r in matrix if r['block']==phase]
  assert [r['case_id'] for r in rows]==[r['case_id'] for r in required]
  for r in rows:
   assert r['status']=='PASS' and r['binary_sha256']==sha(a.binary)
   assert r['simulator_host']['status']=='PASS' and r['postflight_host']['status']=='PASS'
   assert sha(root/r['case_id']/'postflight.json')==r['postflight_sha256']
 matrix=json.loads((X/'matrix.yaml').read_text())['cases']
 if a.phase!='small':gate('small')
 if a.phase=='ideal':gate('main')
 rows=[]
 def save():ledger_path.write_text(json.dumps(rows,indent=2)+'\n')
 try:
  for spec in [r for r in matrix if r['block']==a.phase]:
   row=dict(spec,status='RUNNING',binary_sha256=sha(a.binary));rows.append(row);save();dest=root/spec['case_id'];assert not dest.exists(),'fresh output required';dest.mkdir()
   strategy={'direct':'direct','chunk':'chunk-streaming'}.get(spec['mode'],'multicast');header=spec['mode'] if strategy=='multicast' else 'full'
   cmd=[a.binary,'--out='+str(dest),'--fanout='+str(spec['fanout']),'--bytes='+str(spec['bytes']),'--strategy='+strategy,'--headerModel='+header,'--logLevel=summary']
   row['simulator_host']=run(cmd,root/'hosts'/spec['case_id']/'simulator',3600,case=root);save()
   if row['simulator_host']['status']!='PASS':raise RuntimeError('protected/nonzero simulator stop')
   row['postflight_host']=run([sys.executable,X/'verify.py',dest,'--out',dest/'postflight.json'],root/'hosts'/spec['case_id']/'postflight',3600,case=root);save()
   if row['postflight_host']['status']!='PASS':raise RuntimeError('independent postflight stop')
   check=json.loads((dest/'postflight.json').read_text());assert check['status']=='PASS'
   row.update(status='PASS',postflight_sha256=sha(dest/'postflight.json'));save();print('CASE VERIFIED',spec['case_id'],flush=True)
 except BaseException as exc:
  if rows:rows[-1].update(status='STOPPED',failure=str(exc))
  save();raise
 save()
if __name__=='__main__':main()
