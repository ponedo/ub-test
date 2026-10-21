"""Fail-closed accepted / diagnostic OFF / ON deterministic observable-event gate."""
import argparse
from common import *
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
identities={n:json.loads((b/(n+'.json')).read_text()) for n in ['source-identity','accepted-identity','binary-identity']}
for x in identities.values():check(x)
inputs=freeze([p for case in ['no-replicas','singleton','multi-target','multi-expert'] for rate in [100,3136] for mode in STRATEGIES for p in [(ACCEPTED/'stage-a'/case/str(rate)/mode/n) for n in INPUTS]])
write(o/'identity-before.json',dict(**identities,input_identity=inputs));rows=[]
def stage(cmd,path,negative=None):
 r=run(cmd,path,1800,case=o)
 if negative:assert r['returncode']!=0 and not r['guard'] and negative in (path/'console.txt').read_text()
 else:assert r['status']=='PASS',str(path)
 return r
stage([b/'observer-fifo-test'],o/'observer-fifo-test-host')
def triple(source,base,fault=None,model='roofline'):
 for mode in MODES:
  d=base/mode;copy_inputs(source,d)
  stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool'],d/'preflight-host')
  extra=(['--invalidateGrant=1'] if fault=='invalidate-grant' else ['--nativeRetrans=1','--networkFault='+fault]) if fault else []
  cmd=simulator(b,d,mode,True,extra)
  cmd=[('--computeModel='+model) if str(x).startswith('--computeModel=') else x for x in cmd]
  stage(cmd,d/'simulator-host');validate(stage,b,d,fault,model)
  if mode=='on':validate_diagnostics(d)
  if mode!='accepted':parity(base/'accepted',d,True)
  elif not fault:
   # Stored accepted fixture used summary logging; this matched triplet uses events.
   # Do not relax the triplet comparison. Check baseline semantic outputs separately.
   original=summary(source);current=summary(d)
   assert original['log_level']=='summary' and current['log_level']=='events'
   original['log_level']='events'
   assert original==current,'Accepted baseline changed beyond requested log level'
   for n in ['expert-compute.csv','expert-ready.csv','replica-ready.csv']:assert (source/n).read_bytes()==(d/n).read_bytes()
  rows.append(dict(case=str(base.relative_to(o)),variant=mode,status='PASS'));write(o/'results.json',rows)
for case in ['no-replicas','singleton','multi-target','multi-expert']:
 for rate in [100,3136]:
  for strategy in STRATEGIES:triple(ACCEPTED/'stage-a'/case/str(rate)/strategy,o/case/str(rate)/strategy)
source=ACCEPTED/'stage-a/multi-target/3136/multicast-v2'
for fault in ['data-once','ack-once','invalidate-grant']:
 for model in ['legacy','roofline']:triple(source,o/'network'/model/fault,fault,model)
for fault,reason in [('weight-byte','payload byte mismatch'),('early-wqe','sender completed before target data ready'),('premature-ready','ready before target completion coverage'),('duplicate-completion','audit premature/duplicate sender completion')]:
 for mode in MODES:
  d=o/'negative'/fault/mode;copy_inputs(source,d);stage(simulator(b,d,mode,True,['--fault='+fault]),d/'simulator-host',reason)
for rate in ['100.5','100junk','100 junk','1e2','-1','0','18446744073709551616']:
 for mode in MODES:
  d=o/'invalid-rate'/rate/mode;copy_inputs(source,d);stage(simulator(b,d,mode,False,['--compute-tflops='+rate]),d/'simulator-host','ERROR:')
# Preserve legacy/parent regression coverage without rebuilding any accepted binary.
assert (ROOF/'compute-model.h').read_bytes()==(ROOT/'bandwidth-work/experiments/qwen-roofline-compute/compute-model.h').read_bytes()
stage([sys.executable,ROOF/'test-model.py',ACCEPTED/'build/model-probe',o/'model-unit'],o/'model-unit-host')
for case in ['no-replicas','singleton','multi-target','multi-expert']:
 for strategy in STRATEGIES:
  source=ACCEPTED/'stage-a'/case/'100'/strategy;base=o/'legacy'/case/strategy
  for mode in ['parent',*MODES]:
   d=base/mode;copy_inputs(source,d)
   cmd=simulator(b,d,'accepted' if mode=='parent' else mode,True)
   cmd=[x for x in cmd if not str(x).startswith('--computeModel=')]
   if mode=='parent':cmd[0]=ACCEPTED/'build/parent-layer'
   else:cmd+=['--computeModel=legacy']
   if mode=='parent':cmd=[x for x in cmd if not str(x).startswith(('--compute-tflops=','--hbm-bandwidth-gbps='))]
   stage(cmd,d/'simulator-host')
   stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool','--execution-summary',d/'online-summary.json'],d/'postflight-host')
   stage([sys.executable,OLD/'verify.py',d],d/'independent-host')
   if mode!='parent':
    stage([sys.executable,ROOF/'verify-compute.py',d,'--expected-model=legacy'],d/'compute-host')
    assert summary(base/'parent')==summary(d),'Legacy parent mismatch'
    assert (base/'parent/events.csv').read_bytes()==(d/'events.csv').read_bytes(),'Legacy parent event mismatch'
   if mode in ['off','on']:parity(base/'accepted',d,True)
   if mode=='on':validate_diagnostics(d)
for x in identities.values():check(x)
check(inputs);write(o/'status.json',dict(status='PASS',small_runs=96,legacy_runs=64,model_unit_pass=True,observer_fifo_test_pass=True,queue_observer_invariants_pass=True,fault_runs=18,negative_runs=12,invalid_cli_runs=21,event_order='EXACT events.csv',summary='EXACT excluding verification_wall_ns',identities=identities,input_identity=inputs))
print('PASS exact accepted/OFF/ON observable event and summary parity')
