#!/usr/bin/env python3
"""Build the identical microbenchmark with its accepted pre-change headers."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent;R=E.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
BASE='b2b990d1fea69f7e1a1e7ed615494f821aa71913'
HASHES={'adapter.h':'eec78c578e44de3c6f8bcc962c655b32ace53e9e0871907ba45580ca0d61d4e6','group-manager.h':'d242440302e4ff91779da8a9d93c4dd85d9008144447cd0929a3bc70a7d7efa5'}
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--original-files',type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);n=a.native.resolve()
for rel in ['ub-multicast-fanout-header/fanout.cc','pair-jetty/pair-layer.cc','pair-jetty/online-validation.inc','pair-jetty/multicast-integration.inc','pair-jetty/pair-jetty-manager.h','no-balancing-layer/nb-tracker.h','direct-weight-forward/weight-distribution.h']:
 dest=out/'experiments'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(E/rel,dest)
for name,rel in [('adapter.h','ub-lightweight-multicast-adapter/adapter.h'),('group-manager.h','ub-concurrent-multicast/group-manager.h')]:
 data=(a.original_files/name).read_bytes() if a.original_files else subprocess.check_output(['git','show',BASE+':experiments/'+rel],cwd=R)
 assert hashlib.sha256(data).hexdigest()==HASHES[name],name
 dest=out/'experiments'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
cmd=['c++','-std=c++20','-O3','-g','-DFANOUT_LEGACY_HEADER',out/'experiments/ub-multicast-fanout-header/fanout.cc','-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-lcrypto','-o',out/'fanout']
r=run(cmd,out/'build',3600,case=out);assert r['status']=='PASS'
(out/'legacy-source-hashes.json').write_text(json.dumps(HASHES,indent=2)+'\n')
