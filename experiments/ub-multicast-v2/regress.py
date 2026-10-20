#!/usr/bin/env python3
"""Old fixtures compiled unchanged against candidate native libraries. Sequential and guarded."""
import argparse,sys,json,resource
from pathlib import Path
h=Path(__file__).resolve().parent;e=h.parent
sys.path.insert(0,str(e/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);resource.setrlimit(resource.RLIMIT_CORE,(0,0))
rows=[]
def stage(cmd,name):
 r=run(cmd,o/(name+'-host'),3600,case=o);rows.append(dict(name=name,status=r['status'],returncode=r['returncode'],guard=r['guard']));(o/'stages.json').write_text(json.dumps(rows,indent=2)+'\n');assert r['status']=='PASS',name
for name,src in [('singleton',e/'ub-lightweight-multicast-adapter/singleton.cc'),('multitarget',e/'ub-lightweight-multicast-adapter/multitarget.cc'),('network-poc',e/'ub-network-multicast-poc/network-poc.cc'),('concurrent',e/'ub-concurrent-multicast/concurrent.cc'),('pair-layer',e/'pair-jetty/pair-layer.cc')]:
 stage(['c++','-std=c++20','-O3','-g',src,'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-lcrypto','-o',o/name],name+'-build')
stage(['c++','-std=c++20','-O2',e/'multi-npu-relay/graph-tool.cc','-o',o/'graph-tool'],'graph-tool-build')
stage([sys.executable,e/'ub-lightweight-multicast-adapter/run-singleton.py','--shared','--binary',o/'singleton','--private',o/'singleton-results'],'singleton')
stage([sys.executable,e/'ub-lightweight-multicast-adapter/run-multi.py','--binary',o/'multitarget','--private',o/'multi-results','--singleton-gate',o/'singleton-results/results.json'],'full-multicast')
stage([sys.executable,e/'ub-network-multicast-poc/run.py','--binary',o/'network-poc','--private',o/'network-results','--public',o/'network-collected'],'network-poc')
stage([sys.executable,e/'ub-concurrent-multicast/run-concurrent.py','--binary',o/'concurrent','--out',o/'concurrent-results'],'concurrent')
stage([sys.executable,e/'qwen-real-batch-scaling/regress_small.py','--private',o/'application','--binary',o/'pair-layer','--lib',n/'build/lib','--graph-tool',o/'graph-tool'],'direct-chunk-small')
print('PASS old fixtures and small four-strategy regression')
