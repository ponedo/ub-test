import argparse,sys
from pathlib import Path
from guard import run
h=Path(__file__).resolve().parent;old=h.parent/'ultraep-multicast-integration'
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
for name,src,libs in [('layer',h/'layer.cc',True),('parent-layer',old/'layer.cc',True),('graph-tool',old/'graph-tool.cc',False),('model-probe',h/'model-probe.cc',False)]:
 cmd=['c++','-std=c++20','-O2','-g',src]
 if libs:cmd+=['-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core']
 cmd+=['-o',o/name];assert run(cmd,o/(name+'-build'),1800,case=o)['status']=='PASS'
