#!/usr/bin/env python3
import sys,os,json,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw';N=W/'wqe-completion-native'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
assert subprocess.check_output(['git','-C',str(N),'rev-parse','HEAD^{tree}'],text=True).strip()=='c27d1faef570e6da9900a71aa0a37180a58dfba8'
subprocess.run(['git','-C',str(N),'diff','--exit-code'],check=True)
(R/'build').mkdir(parents=True,exist_ok=True)
cmd=['c++','-std=c++20','-O3','-g',str(H.parent/'pair-jetty/pair-layer.cc'),'-I'+str(N/'build/include'),'-L'+str(N/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(N/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',str(R/'build/pair-layer')]
r=run(cmd,R/'build-host',300,case=R)
assert r['status']=='PASS'
