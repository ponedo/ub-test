#!/usr/bin/env python3
import argparse,sys
from pathlib import Path
h=Path(__file__).resolve().parent;sys.path.insert(0,str(h.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
for name,src,libs in [('layer','layer.cc',True),('graph-tool','graph-tool.cc',False),('pair-stress','pair-stress.cc',True)]:
 cmd=['c++','-std=c++20','-O2','-g',h/src]
 if libs:cmd+=['-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core']
 cmd+=['-o',o/name];assert run(cmd,o/(name+'-build'),3600,case=o)['status']=='PASS'
