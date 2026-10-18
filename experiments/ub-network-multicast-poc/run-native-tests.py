#!/usr/bin/env python3
"""Run actual original UB suites, record all failures rather than hiding unsupported fixtures."""
import argparse,json,os,subprocess,sys,resource
from pathlib import Path
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.native=a.native.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
os.environ['CLICOLOR']='0'
os.environ['USER']='builder'
bin=a.native/'build/utils/ns3.44-test-runner';names=subprocess.check_output([bin,'--list'],text=True).splitlines();names=[n for n in names if n.startswith('unified-bus')];result=[]
for n in names:
 r=run([bin,'--suite='+n,'--verbose','--fullness=QUICK'],a.out/n,3600,cwd=a.native,case=a.out)
 result.append(dict(suite=n,status=r['status'],returncode=r['returncode'],guard=r['guard'],wall_seconds=r['wall_seconds'],cpu_seconds=r['user_cpu_seconds']+r['system_cpu_seconds'],peak_rss_kib=r['peak_rss_kib']))
 (a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 if r['guard']:break
print('UB suites',sum(x['status']=='PASS' for x in result),'/',len(names))
if len(result)!=len(names) or any(r['status']!='PASS' for r in result):sys.exit(1)
