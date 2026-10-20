#!/usr/bin/env python3
import argparse,sys,os,json
from pathlib import Path
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
import adapter
p=argparse.ArgumentParser()
for k in ['build','legacy-build','stage-a','out']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);b=a.build.resolve();os.environ['RELAY_GRAPH_TOOL']=str(b/'graph-tool')
adapter.emit(a.stage_a.resolve()/'multi-target/base',dict(force_relay=True),'two-stage',o/'input')
for name,binary in [('candidate',b/'layer'),('legacy',a.legacy_build.resolve()/'pair-layer')]:
 dest=o/name;dest.mkdir();cmd=[binary,'--input='+str(o/'input/input.txt'),'--out='+str(dest),'--logLevel=summary','--jettyMode=pair'];assert run(cmd,dest/'host',3600,case=o)['status']=='PASS'
 assert run([sys.executable,H/'preflight.py',o/'input','--graph-tool',b/'graph-tool','--execution-summary',dest/'online-summary.json'],dest/'postflight',3600,case=o)['status']=='PASS'
x=json.loads((o/'candidate/online-summary.json').read_text());y=json.loads((o/'legacy/online-summary.json').read_text());x.pop('verification_wall_ns');y.pop('verification_wall_ns');assert x==y
(o/'status.json').write_text(json.dumps(dict(status='EXACT_MATCH',strategy='two-stage',summary=x),indent=2)+'\n')
