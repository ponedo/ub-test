#!/usr/bin/env python3
"""Small actual codec and intentional-abort checks; exact failure evidence required."""
import argparse,json,sys
from pathlib import Path
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
cmd=['c++','-std=c++20','-O3','-g',X/'header-tests.cc','-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',out/'header-tests']
r=run(cmd,out/'build',3600,case=out);assert r['status']=='PASS'
failures={
 'wrong-group':'oracle wire identity','wrong-sequence':'oracle wire identity','wrong-length':'oracle wire size/membership','wrong-count':'oracle wire size/membership','wrong-bitmap':'oracle wire size/membership','wrong-mode':'oracle wire identity','wrong-member':'oracle compact member identity','wrong-tp':'oracle compact native identity','wrong-psn':'oracle compact native identity','wrong-ssn':'oracle compact native identity','payload-mismatch':'oracle received payload mismatch','truncated':'truncated envelope','trailing':'oracle wire size/membership','missing-context':'unknown/already consumed oracle envelope','wrong-range':'oracle payload range','duplicate':'oracle mode/member/duplicate mismatch','undrained':'oracle native restoration metadata not drained','wrong-receiver':'oracle mode/member/duplicate mismatch','wrong-callback-group':'oracle receive identity','wrong-callback-sequence':'unknown/already consumed oracle envelope'}
rows=[]
for mode in ['full','compact-oracle','ideal-oracle']:
 for scenario in ['positive']+([] if mode=='full' else [s for s in failures if mode=='compact-oracle' or s not in ['wrong-member','wrong-tp','wrong-psn','wrong-ssn']]):
  d=out/(mode+'-'+scenario);r=run([out/'header-tests',scenario,mode],d,3600,case=out);text=(d/'console.txt').read_text()
  ok=(r['status']=='PASS' and 'PASS '+mode in text) if scenario=='positive' else (r['returncode']<0 and not r['guard'] and failures[scenario] in text)
  rows.append(dict(mode=mode,scenario=scenario,status='PASS' if ok else 'FAIL',expected_failure=None if scenario=='positive' else failures[scenario],returncode=r['returncode'],guard=r['guard'],wall_seconds=r['wall_seconds']))
  (out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert ok,(mode,scenario,text)
print('HEADER TESTS PASS',len(rows))
