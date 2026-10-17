#!/usr/bin/env python3
import argparse,json,os,resource,subprocess,time
from pathlib import Path
CASES={'single-single':['--mode=singleonesegment'],'single-multi':['--mode=single'],'multi-single':['--mode=onesegment'],'multi-interleave':[],'late-overlap':['--lateNs=25000'],'pressure':['--count=16','--segments=32','--lateNs=25000','--duplicateDone=1']}
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for name,options in CASES.items():
 cmd=[str(a.binary.resolve()),'--output='+str(a.out/name)]+options;t=time.monotonic()
 with (a.out/(name+'.stdout')).open('w') as f:
  r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=30,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
 rows.append({'case':name,'rc':r.returncode,'wall':time.monotonic()-t,'command':cmd});(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
 if r.returncode:raise SystemExit('Probe failed: '+name)
