#!/usr/bin/env python3
"""Build isolated experiment and production regression binary; native source stays pinned."""
import argparse,hashlib,json,sys
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
for path,h in json.loads((X/'native-source-sha256.json').read_text()).items():assert hashlib.sha256((n/path).read_bytes()).hexdigest()==h,path
for name,source in [('fanout',X/'fanout.cc'),('pair-layer',E/'pair-jetty/pair-layer.cc')]:
 cmd=['c++','-std=c++20','-O3','-g',source,'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-lcrypto','-o',out/name]
 result=run(cmd,out/(name+'-build'),3600,case=out)
 if result['status']!='PASS':raise SystemExit(2)
(out/'binary-hashes.json').write_text(json.dumps({name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['fanout','pair-layer']},indent=2)+'\n')
