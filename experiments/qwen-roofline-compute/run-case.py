import argparse,json,sys,hashlib
from pathlib import Path
from guard import run
H=Path(__file__).resolve().parent;OLD=H.parent/'ultraep-multicast-integration'
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('mode');p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();d=r/a.mode;b=a.build.resolve();ledger=json.loads((r/'ledger.json').read_text());record=next(x for x in ledger['runs'] if x['strategy']==a.mode);assert record['status']=='PREPARED'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(k)==v for k,v in ledger['binary_identity'].items())
for name in ['layer','parent-layer','graph-tool']:
 assert str(b/name) in ledger['binary_identity'] and sha(b/name)==ledger['binary_identity'][str(b/name)],'wrong build path'
for k,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert sha(d/name)==record[k]
def save():(d/'run-result.json').write_text(json.dumps(record,indent=2)+'\n')
def stage(cmd,path):
 x=run(cmd,path,4800,case=r)
 if x['status']!='PASS':raise RuntimeError('guard/nonzero '+str(path)+' '+str(x['guard']))
 return x
record.update(status='RUNNING',compute_model='roofline',compute_tflops=100,hbm_bandwidth_gbps=2692);save()
try:
 record['simulator_host']=stage([b/'layer','--input='+str(d/'input.txt'),'--out='+str(d),'--computeModel=roofline','--compute-tflops=100','--hbm-bandwidth-gbps=2692','--capacityMetrics='+str(d/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],d/'simulator-host');save()
 record['postflight_host']=stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool','--out',d/'postflight.json','--execution-summary',d/'online-summary.json'],d/'postflight-host');save()
 record['independent_host']=stage([sys.executable,OLD/'verify.py',d],d/'independent-host');save()
 record['compute_host']=stage([sys.executable,H/'verify-compute.py',d,'--expected-model=roofline'],d/'compute-host');save()
 record.update(status='PASS',summary=json.loads((d/'online-summary.json').read_text()),metrics=json.loads((d/'simulator-metrics.json').read_text()));save();print('VERIFIED',a.mode,flush=True)
except Exception as e:record.update(status='FAIL',failure=str(e));save();raise
