#!/usr/bin/env python3
"""Explicit continuation of the same frozen run, never implicit reuse of history."""
import argparse,hashlib,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();b=a.build.resolve();original=r/'ledger.json';frozen=r/'ledger-before-explicit-resume.json';assert not frozen.exists();x=json.loads(original.read_text());assert x['status']=='STOPPED' and x['failure'].startswith('RESOURCE_READMISSION:')
assert [z['strategy'] for z in x['runs']]==['no-balancing','direct','chunk-streaming','multicast-v2']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for path,digest in x['binary_identity'].items():assert sha(path)==digest,'changed binary/native library'
assert str(b/'layer') in x['binary_identity'] and str(b/'graph-tool') in x['binary_identity']
for row in x['runs']:
 d=r/row['strategy']
 for key,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert sha(d/name)==row[key],(row['strategy'],name)
 assert row['status'] in ['PASS','PREPARED']
 if row['status']=='PASS':
  assert row['strategy']=='no-balancing' and json.loads((d/'online-summary.json').read_text())==row['summary']
  for stage in ['simulator','postflight','independent']:
   actual=json.loads((d/(stage+'-host')/'resource.json').read_text());assert actual==row[stage+'_host'] and actual['status']=='PASS' and actual['guard'] is None
  assert json.loads((d/'validation.json').read_text())['status']=='PASS'
first=x['runs'][0];assert first['status']=='PASS';projection=first['simulator_host']['wall_seconds']*1220.776/129.570
assert projection<=3600,'Exact projection exceeds unchanged wall guard; diagnose before resume'
frozen.write_text(original.read_text());x.update(status='RUNNING',explicit_resume=dict(reason='Replace rounded380s admission heuristic with exact historical relative-work projection; same verified NoBal, native build, input and3600s hard guard.',projected_max_wall_seconds=projection));x.pop('failure',None)
def save():original.write_text(json.dumps(x,indent=2)+'\n')
def stage(cmd,out):
 host=run(cmd,out,3600,case=r);assert host['status']=='PASS',str(out);return host
save()
try:
 for row in x['runs'][1:]:
  assert all(sha(path)==digest for path,digest in x['binary_identity'].items());d=r/row['strategy'];row['status']='RUNNING';save();print('START',row['strategy'],flush=True)
  row['simulator_host']=stage([b/'layer','--input='+str(d/'input.txt'),'--out='+str(d),'--capacityMetrics='+str(d/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],d/'simulator-host')
  row['postflight_host']=stage([sys.executable,H/'preflight.py',d,'--graph-tool',b/'graph-tool','--out',d/'postflight.json','--execution-summary',d/'online-summary.json'],d/'postflight-host')
  row['independent_host']=stage([sys.executable,H/'verify.py',d],d/'independent-host');row.update(status='PASS',summary=json.loads((d/'online-summary.json').read_text()),metrics=json.loads((d/'simulator-metrics.json').read_text()));save();print('VERIFIED',row['strategy'],flush=True)
 assert len({row['summary']['combine_fnv1a64'] for row in x['runs']})==1
 x['status']='PASS';save()
except Exception as e:x.update(status='STOPPED',failure=str(e));save();raise
