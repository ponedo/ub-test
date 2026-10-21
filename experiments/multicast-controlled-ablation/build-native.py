#!/usr/bin/env python3
"""Configure/build the already patched native tree with unchanged resource guards."""
import argparse,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'cloudmatrix-bandwidth'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--tools',type=Path);a=p.parse_args()
n=a.native.resolve();out=a.out.resolve();assert n.is_dir() and not out.exists();out.mkdir(parents=True)
env=dict(os.environ)
if a.tools:
 tools=a.tools.resolve();env['PATH']=str(tools/'bin')+':'+env.get('PATH','');env['PYTHONPATH']=str(tools)
commands=[('configure',['cmake','-S',n,'-B',n/'cmake-cache','-G','Ninja','-DCMAKE_BUILD_TYPE=release','-DNS3_ENABLED_MODULES=unified-bus','-DNS3_ASSERT=ON','-DNS3_LOG=OFF','-DNS3_TESTS=ON','-DNS3_EXAMPLES=OFF','-DNS3_MPI=OFF','-DNS3_MTP=OFF','-DNS3_NATIVE_OPTIMIZATIONS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF']),('build',['cmake','--build',n/'cmake-cache','--target','unified-bus','-j2'])]
for name,cmd in commands:
 result=run(cmd,out/name,4800,case=out,env=env)
 if result['status']!='PASS':raise SystemExit(f'{name} failed: {result["status"]}')
(out/'status.json').write_text(json.dumps({'status':'PASS','scope':'unified-bus library target; not all native test suites'},indent=2)+'\n')
