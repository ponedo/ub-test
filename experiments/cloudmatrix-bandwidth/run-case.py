import argparse,json,sys,hashlib,time
from pathlib import Path
import os
if not __debug__ or os.environ.get('PYTHONOPTIMIZE'):
 raise RuntimeError('Python optimization is forbidden: all validation assertions must execute')
from guard import run
H=Path(__file__).resolve().parent;OLD=H.parent/'ultraep-multicast-integration'
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('mode');p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();d=r/a.mode;b=a.build.resolve();ledger=json.loads((r/'ledger.json').read_text());record=next(x for x in ledger['runs'] if x['strategy']==a.mode);assert record['status']=='PREPARED'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(k)==v for k,v in ledger['binary_identity'].items())
assert all(sha(k)==v for k,v in ledger['source_identity'].items()), 'source changed'
assert sha(ledger['stage_a_path'])==ledger['stage_a_sha256'], 'small-stage gate changed'
assert all(sha(ledger['input_paths'][k])==v for k,v in ledger['input_identity'].items()), 'real input changed'
assert all(sha(d/k)==v for k,v in record['immutable_files'].items()), 'execution artifact changed'
assert sha(ledger['baseline_evidence_path'])==ledger['baseline_evidence_sha256'], 'baseline accepted evidence changed'
assert ledger['link_gbps']==3136
cfg=json.loads((d/'config.json').read_text());original=json.loads((d/'baseline-config.json').read_text())
for section in ['runtime','parameters']:
 assert cfg[section]['link_gbps']==3136 and original[section]['link_gbps']==100
 original[section]['link_gbps']=3136
assert cfg==original, 'configuration changed beyond network rate'
a_tokens=(d/'input.txt').read_text().split();b_tokens=(d/'baseline-input.txt').read_text().split()
assert a_tokens[12]=='3136' and b_tokens[12]=='100';b_tokens[12]='3136'
assert a_tokens==b_tokens, 'execution input changed beyond network rate' 
for name in ['layer','parent-layer','graph-tool']:
 assert str(b/name) in ledger['binary_identity'] and sha(b/name)==ledger['binary_identity'][str(b/name)],'wrong build path'
for k,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert sha(d/name)==record[k]
def save():(d/'run-result.json').write_text(json.dumps(record,indent=2)+'\n')
case_started=time.monotonic()
def stage(cmd,path):
 remaining=4800-(time.monotonic()-case_started)
 if remaining<=0:raise RuntimeError('4800 second whole-case wall guard')
 x=run(cmd,path,remaining,case=r)
 if x['status']!='PASS':raise RuntimeError('guard/nonzero '+str(path)+' '+str(x['guard']))
 return x
record.update(status='RUNNING',compute_model='roofline',compute_tflops=100,hbm_bandwidth_gbps=2692);save()
try:
 record['simulator_host']=stage([b/'layer','--input='+str(d/'input.txt'),'--out='+str(d),'--computeModel=roofline','--compute-tflops=100','--hbm-bandwidth-gbps=2692','--capacityMetrics='+str(d/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],d/'simulator-host');save()
 record['postflight_host']=stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool','--out',d/'postflight.json','--execution-summary',d/'online-summary.json'],d/'postflight-host');save()
 record['independent_host']=stage([sys.executable,OLD/'verify.py',d],d/'independent-host');save()
 record['compute_host']=stage([sys.executable,H.parent/'qwen-roofline-compute/verify-compute.py',d,'--expected-model=roofline'],d/'compute-host');save()
 assert all(sha(k)==v for k,v in ledger['source_identity'].items())
 assert all(sha(k)==v for k,v in ledger['binary_identity'].items())
 assert all(sha(d/k)==v for k,v in record['immutable_files'].items())
 record.update(status='PASS',case_wall_seconds=time.monotonic()-case_started,summary=json.loads((d/'online-summary.json').read_text()),metrics=json.loads((d/'simulator-metrics.json').read_text()));save();print('VERIFIED',a.mode,flush=True)
except Exception as e:record.update(status='FAIL',failure=str(e));save();raise

