#!/usr/bin/env python3
import argparse,sys,json,resource
from pathlib import Path
if not __debug__:raise RuntimeError('Assertions must remain enabled')
h=Path(__file__).resolve().parent;sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case');a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);b=a.build.resolve();resource.setrlimit(resource.RLIMIT_CORE,(0,0));results=[]
for case in ([a.case] if a.case else ['normal','data-once','duplicate','ack-once','response-once','persistent-bounded','persistent-exhaust','retrans-disabled']):
 r=run([b/'micro','--out='+str(o/case),'--loss='+case],o/(case+'-host'),3600,case=o)
 assert not r['guard'],r['guard']
 if case=='persistent-exhaust':
  assert r['returncode']!=0 and 'Avaliable retransmission attempts exhausted' in (o/(case+'-host/console.txt')).read_text()
 else:assert r['returncode']==0,case
 v=run([sys.executable,h/'verify.py',o/case,case],o/(case+'-verify-host'),3600,case=o);assert v['status']=='PASS',case
 results.append(json.loads((o/(case+'-verify-host/console.txt')).read_text()));(o/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print('Verified bounded retransmission cases')
