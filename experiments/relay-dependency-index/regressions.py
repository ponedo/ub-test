#!/usr/bin/env python3
"""Fresh, isolated, bounded regression runs. Never modifies native or old evidence."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent; R=H.parents[1]; W=R.parent
sys.path.insert(0,str(R/'experiments/wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args(); O=a.out.resolve();O.mkdir(parents=True,exist_ok=a.resume)
LIB=W/'wqe-completion-native/build/lib'; ENV=dict(os.environ,LD_LIBRARY_PATH=str(LIB));G=W/'tiered-logging-raw/regressions-final/aux/graph-tool'
report={'status':'RUNNING','runs':[],'scope':'Original Planner tests, PairJetty basic/lifecycle/negative, relay tracker/topology subset, tiered helpers/preflight/all-mode faults. Full historical integration matrix is not rerun.'}
if a.resume:
 previous=json.loads((O/'results.json').read_text());
 if previous['binary_sha256']!=hashlib.sha256(a.binary.read_bytes()).hexdigest():raise RuntimeError('Cannot resume with a changed binary')
 for name,digest in previous['source_sha256'].items():
  if hashlib.sha256((R/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Cannot resume with changed source: '+name)
 report['runs']=previous['runs'];report['prior_runner_errors']=[previous.get('error')]
def save(): (O/'results.json').write_text(json.dumps(report,indent=2)+'\n')
def execute(name,cmd,expected=None):
 if a.resume and any(x['name']==name and x['status']=='PASS' for x in report['runs']):return
 result=run(cmd,O/'host'/name,300,cwd=O,case=O,env=ENV);console=(O/'host'/name/'console.txt').read_text();ok=result['status']=='PASS' if expected is None else result['guard'] is None and result['returncode']>0 and any(x in console for x in expected)
 report['runs'].append(dict(name=name,status='PASS' if ok else 'FAIL',expected=expected,resource=str(O/'host'/name/'resource.json'),command=list(map(str,cmd)),console_tail=console[-1200:]));save()
 if not ok:raise RuntimeError(name+' failed: '+console[-1200:])
 return result
def copyinputs(src,dst):
 dst.mkdir(parents=True,exist_ok=a.resume)
 for n in ('input.txt','config.json','plan.json','assignments.csv','transfers.csv','graph-input.txt','weight-edges.csv'):
  if (src/n).exists():shutil.copy2(src/n,dst/n)
def simulate(name,src,dst,mode='debug',fault=None):
 copyinputs(src,dst);cmd=[a.binary,'--input='+str(dst/'input.txt'),'--out='+str(dst),'--logLevel='+mode,'--jettyMode=pair','--capacityMetrics='+str(dst/'simulator-metrics.json')]
 if fault:cmd+=['--fault='+fault]
 return cmd
try:
 # Isolate the original Planner scripts, including their original output paths.
 iso=O/'source';q=iso/'planner/quota';shutil.copytree(R/'planner/quota',q,ignore=shutil.ignore_patterns('evidence','__pycache__'),dirs_exist_ok=a.resume);(q/'evidence').mkdir(exist_ok=a.resume)
 fixture=iso/'experiments/no-balancing-layer/evidence/n64/config.json';fixture.parent.mkdir(parents=True,exist_ok=a.resume);fixture.write_bytes(subprocess.check_output(['git','show','HEAD:experiments/no-balancing-layer/evidence/n64/config.json'],cwd=R))
 for script in ('test_numeric_bounds.py','run_tests.py','test_replication_reference.py','test_compatible.py'):
  for optimized in (False,True):execute('planner-'+script+('-optimized' if optimized else ''),[sys.executable]+(['-O'] if optimized else [])+[q/'tests'/script])
 execute('tracker-build',['c++','-std=c++20','-O2',R/'experiments/multi-npu-relay/tracker-tests.cc','-o',O/'tracker-tests']);execute('relay-tracker',[O/'tracker-tests'])
 # Execute the original 120-trial graph/reference portion unchanged, excluding old full-matrix integration.
 source=(R/'experiments/multi-npu-relay/tests.py').read_text().split('for name in [d for d in out.iterdir()')[0]
 (O/'relay-topology-subset.py').write_text(source+'\nprint("PASS original topology oracle trials:",len(records),"order differences:",order_differences,"load differences:",load_differences)\n')
 ENV['PYTHONPATH']=str(R/'experiments/multi-npu-relay');ENV['RELAY_GRAPH_TOOL']=str(G)
 execute('relay-topology',[sys.executable,O/'relay-topology-subset.py','--out',O])
 execute('pair-basic',[sys.executable,R/'experiments/pair-jetty/run-basic-probe.py','--binary',W/'pair-jetty-raw/pair-probe','--out',O/'pair-basic'])
 probe=W/'tiered-logging-raw/regressions-final/pair-lifecycle/pair-lifecycle-probe'
 for n in (2,3,4):execute('pair-directional-'+str(n),[probe,'--mode=directional','--nodes='+str(n),'--output='+str(O/('directional-'+str(n)))])
 for mode in ('cancel','fail','wrap'):execute('pair-'+mode,[probe,'--mode='+mode,'--count=22000','--output='+str(O/mode)])
 execute('tiered-helpers',[sys.executable,R/'experiments/tiered-logging/test-harness.py'])
 inputs=W/'tiered-logging-raw/harness-smoke-1/inputs';canary=inputs/'multichunk-multita';slow=inputs/'slow-relay-fault'
 execute('preflight-original',[sys.executable,R/'experiments/tiered-logging/test-preflight.py','--case',canary,'--graph-tool',G,'--out',O/'preflight-original.json'])
 spec=importlib.util.spec_from_file_location('pf',R/'experiments/tiered-logging/preflight.py');pf=importlib.util.module_from_spec(spec);spec.loader.exec_module(pf)
 mutations=[]
 for mode in ('scan','indexed'):
  for mutation in ('missing-dependency','wrong-group','duplicate-dependency','reversed-dependencies'):
   dest=O/'preflight-mutations'/mode/mutation;copyinputs(slow,dest);c=json.loads((dest/'config.json').read_text());x=next(t for t in c['transfers'] if t['dependencies']);deps=x['dependencies']
   if mutation=='missing-dependency':x['dependencies']=deps[1:]
   elif mutation=='wrong-group':x['dependencies']=[0]+deps[1:]
   elif mutation=='duplicate-dependency':x['dependencies']=deps+[deps[0]]
   else:
    x=next((t for t in c['transfers'] if len(t['dependencies'])>1),None)
    if x is None:raise RuntimeError('fixture lacks multiple group parents')
    x['dependencies']=list(reversed(x['dependencies']))
   (dest/'config.json').write_text(json.dumps(c))
   try:pf.check(dest,G,dependency_mode=mode)
   except ValueError as e:mutations.append(dict(mode=mode,mutation=mutation,status='PASS',error=str(e)))
   else:raise RuntimeError('accepted mutation '+mutation)
 report['preflight_mutations']=mutations;save()
 gate=O/'gate'
 for name,src in [('multi4_force',canary),('slow_relay8',slow)]:
  dest=gate/(name+'-chunk-streaming')/'pair/run';execute('gate-'+name,simulate(name,src,dest));execute('verify-'+name,[sys.executable,R/'experiments/pair-jetty/verify.py',dest,'pair'])
 execute('pair-original-negatives',[sys.executable,R/'experiments/pair-jetty/run-negative-tests.py','--binary',a.binary,'--lib',LIB,'--gate-c',gate,'--out',O/'pair-negative'])
 # Import the exact original tiered fault catalog without running its CLI.
 sys.path.insert(0,str(R/'experiments/tiered-logging'));spec=importlib.util.spec_from_file_location('tiered_runner',R/'experiments/tiered-logging/run.py');tr=importlib.util.module_from_spec(spec);spec.loader.exec_module(tr)
 for fault,messages in tr.FAULTS.items():
  for mode in ('summary','events','debug'):
   dest=O/'tiered-faults'/fault/mode;execute('tiered-'+fault+'-'+mode,simulate(fault,slow if fault=='early-group' else canary,dest,mode,fault),messages)
   assert json.loads((dest/'validation.json').read_text())['status']=='FAIL'
 report['status']='PASS'
except Exception as e:report['status']='FAIL';report['error']=str(e);raise
finally:
 report['source_sha256']={str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [R/'experiments/pair-jetty/pair-layer.cc',R/'experiments/pair-jetty/online-validation.inc',R/'experiments/multi-npu-relay/adapter.py',R/'experiments/tiered-logging/preflight.py']};report['binary_sha256']=hashlib.sha256(a.binary.read_bytes()).hexdigest();save()
