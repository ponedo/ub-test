#!/usr/bin/env python3
"""Recover metadata-only bootstrap omission without rerunning completed48 cases."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;REPO=H.parents[1];sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--tools',type=Path,required=True);a=p.parse_args();out=a.out.resolve();source=out/'source';evidence=out/'old-evidence';recover=out/'recovery';recover.mkdir(exist_ok=False)
# Exact accepted metadata fixtures, no oracle modifications or simulated rerun.
files=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','--name-only','HEAD','experiments/direct-weight-forward/evidence'],text=True).splitlines();hashes={}
for name in files:
 if not name.endswith('.json'):continue
 data=subprocess.check_output(['git','-C',str(REPO),'show','HEAD:'+name]);dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
(recover/'restored-fixtures.json').write_text(json.dumps(hashes,indent=2)+'\n')
comparison=json.loads((evidence/'comparison.json').read_text());assert len(comparison)==12 and all(len(b)==4 for b in comparison.values())
env={'PATH':str(a.tools.resolve()/'bin')+':'+str(Path(sys.executable).parent)+':/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','HOME':str(out/'home'),'PYTHONPATH':str(a.tools.resolve()),'NS3_ROOT':str(a.native.resolve()),'BUILD_TOOLS':str(a.tools.resolve()),'BUILD_JOBS':'4','LD_LIBRARY_PATH':str(a.native.resolve()/'build/lib'),'EVIDENCE':str(evidence),'RELAY_GRAPH_TOOL':str(out/'aux/graph-tool')}
records=[]
for name,script,flags in [('normal','tests.py',[]),('optimized','tests.py',['-O']),('prior-chain','regressions.py',[])]:
 cmd=[sys.executable,*flags,str(source/'experiments/multi-npu-relay'/script),'--ns3',str(a.native.resolve()),'--out',str(evidence)]
 result=run(cmd,recover/name,300,cwd=source,case=out,env=env);records.append({'name':name,'resource':result});(recover/'results.json').write_text(json.dumps(records,indent=2)+'\n')
 if result['status']!='PASS':raise SystemExit('recovery failed '+name)
print('PASS retained48case suite + normal/optimized + prior chain')
