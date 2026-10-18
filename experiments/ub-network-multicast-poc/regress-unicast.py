#!/usr/bin/env python3
"""Fresh baseline/new native comparison using unchanged project-generated small MoE cases."""
import argparse,json,os,sys
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent
sys.path.insert(0,str(E/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args();a.private=a.private.resolve();a.private.mkdir(parents=True,exist_ok=False)
graph=a.private/'graph-tool'
r=run(['c++','-std=c++20','-O3',E/'multi-npu-relay/graph-tool.cc','-o',graph],a.private/'graph-build',3600,case=a.private);assert r['status']=='PASS'
results=[]
for label,native in [('baseline',a.baseline.resolve()),('multicast',a.native.resolve())]:
 binary=a.private/('pair-layer-'+label)
 cmd=['c++','-std=c++20','-O3','-g',E/'pair-jetty/pair-layer.cc','-I'+str(native/'build/include'),'-L'+str(native/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(native/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',binary]
 r=run(cmd,a.private/(label+'-build'),3600,case=a.private);assert r['status']=='PASS'
 cmd=[sys.executable,E/'qwen-real-batch-scaling/regress_small.py','--private',a.private/label,'--binary',binary,'--lib',native/'build/lib','--graph-tool',graph]
 r=run(cmd,a.private/(label+'-regression-host'),3600,case=a.private);assert r['status']=='PASS'
 old=json.loads((a.private/label/'results.json').read_text())
 results.append(old)
comparison=[]
for b,n in zip(*results):
 assert b['strategy']==n['strategy']
 b['summary'].pop('verification_wall_ns',None);n['summary'].pop('verification_wall_ns',None)
 assert b['summary']==n['summary'],b['strategy']
 comparison.append(dict(strategy=b['strategy'],status='PASS',all_simulation_summary_fields_equal=True,excluded=['verification_wall_ns']))
(a.private/'parity.json').write_text(json.dumps(comparison,indent=2)+'\n');print('FOUR STRATEGY PARITY PASS')
