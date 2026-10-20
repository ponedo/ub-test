#!/usr/bin/env python3
"""Only build v2 small fixtures; unchanged host limits, sequential stages."""
import argparse,sys,os
from pathlib import Path
h=Path(__file__).resolve().parent
sys.path.insert(0,str(h.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--only',choices=['micro','codec-test','association-test']);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('fresh output required')
a.out.mkdir(parents=True);n=a.native.resolve()
for name in ([a.only] if a.only else ['codec-test','association-test','micro']):
 cmd=['c++','-std=c++20','-O2','-g',h/(name+'.cc'),'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',a.out/name]
 r=run(cmd,a.out/(name+'-build'),3600,case=a.out)
 if r['status']!='PASS':raise SystemExit(2)
