#!/usr/bin/env python3
import argparse,json,sys,subprocess,shutil,hashlib
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent;sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--layer',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--baseline-layer',type=Path,required=True);a=p.parse_args();assert shutil.which('cmake') and shutil.which('ninja'),'Restore the existing project build toolchain PATH/PYTHONPATH first (README)';a.out.mkdir(parents=True,exist_ok=False);n=a.native.resolve();out=a.out.resolve()
def guarded(cmd,name):
 r=run(cmd,out/name,3600,case=out);assert r['status']=='PASS',(name,r['status']);return r
for name,src in [('concurrent',X/'concurrent.cc'),('singleton',E/'ub-lightweight-multicast-adapter/singleton.cc'),('multitarget',E/'ub-lightweight-multicast-adapter/multitarget.cc')]:
 guarded(['c++','-std=c++20','-O3','-g',src,'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',out/name],name+'-build')
guarded([sys.executable,X/'run-concurrent.py','--binary',out/'concurrent','--out',out/'concurrent-results'],'concurrent-host')
for scenario,reason in [('capacity','multicast group capacity/configuration'),('oversize','group frame exceeds')]:
 cmd=[out/'concurrent','--out='+str(out/scenario),'--scenario='+scenario]+(['--pressure=1'] if scenario=='oversize' else [])
 r=run(cmd,out/(scenario+'-host'),3600,case=out);assert r['returncode']!=0 and not r['guard'] and reason in (out/(scenario+'-host/console.txt')).read_text()
guarded([sys.executable,E/'ub-lightweight-multicast-adapter/run-singleton.py','--shared','--binary',out/'singleton','--private',out/'singleton-results'],'singleton-host')
guarded([sys.executable,E/'ub-lightweight-multicast-adapter/run-multi.py','--binary',out/'multitarget','--private',out/'old-multi-results','--singleton-gate',out/'singleton-results/results.json'],'old-multi-host')
guarded([sys.executable,E/'ub-lightweight-multicast-adapter/test-verifier.py',out/'old-multi-results/three-target','--out',out/'old-verifier-mutations'],'old-verifier-host')
for label,binary in [('baseline',a.baseline_layer),('candidate',a.layer)]:
 guarded([sys.executable,E/'qwen-real-batch-scaling/regress_small.py','--private',out/label,'--binary',binary,'--lib',n/'build/lib','--graph-tool',a.graph_tool],label+'-host')
b=json.loads((out/'baseline/results.json').read_text());c=json.loads((out/'candidate/results.json').read_text());parity=[]
for old,new in zip(b,c):
 old['summary'].pop('verification_wall_ns',None);new['summary'].pop('verification_wall_ns',None);assert old==new or (old['strategy']==new['strategy'] and old['summary']==new['summary']);parity.append(dict(strategy=old['strategy'],status='PASS',all_simulated_summary_fields_equal=True))
(out/'application-parity.json').write_text(json.dumps(parity,indent=2)+'\n')
guarded([sys.executable,E/'ub-network-multicast-poc/run.py','--binary',n/'build/scratch/ns3.44-network-poc','--private',out/'network','--public',out/'network-collected'],'network-host')
r=run([sys.executable,E/'ub-network-multicast-poc/run-native-tests.py','--native',n,'--out',out/'native'],out/'native-host',3600,case=out)
rows=json.loads((out/'native/summary.json').read_text());assert len(rows)==49 and sum(x['status']=='PASS' for x in rows)==48 and [x['suite'] for x in rows if x['status']!='PASS']==['unified-bus-examples'];assert not r['guard']
(out/'status.json').write_text(json.dumps(dict(status='PASS_WITH_KNOWN_NATIVE_SUITE_FAILURE',native_pass=48,native_total=49,application_parity=parity),indent=2)+'\n');print('REGRESSIONS COMPLETE')
