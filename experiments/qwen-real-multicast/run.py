#!/usr/bin/env python3
"""Fixed N2048 matrix; stop at first protected or correctness failure."""
import argparse,json,sys,os,hashlib,shutil
from pathlib import Path
E=Path(__file__).resolve().parent.parent;X=Path(__file__).resolve().parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser()
for k in ['private','reference','binary','graph-tool','manifest','counts']:p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--resume-ledger',type=Path)
p.add_argument('--phase',choices=['prepare-multicast','run'],required=True);a=p.parse_args();root=a.private.resolve();root.mkdir(exist_ok=True);env=dict(os.environ,RELAY_GRAPH_TOOL=str(a.graph_tool.resolve()));ledger=[]
ledger_path=root/(a.phase+'-ledger.json')
if ledger_path.exists() and not a.resume_ledger:raise RuntimeError('existing ledger: use a fresh private directory; no automatic restart')
if a.resume_ledger and a.resume_ledger.resolve()==ledger_path.resolve():raise RuntimeError('preserve original ledger separately before explicit resume')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def semantic_plan(p):
 d=json.loads(p.read_text());d.pop('cpu_wall_ns',None)
 return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
prior=json.loads(a.resume_ledger.read_text()) if a.resume_ledger else []
prior={(r['layer'],r['strategy']):r for r in prior}
def save(): (root/(a.phase+'-ledger.json')).write_text(json.dumps(ledger,indent=2)+'\n')
def stage(cmd,out):
 r=run(cmd,out,3600,case=root,env=env)
 if r['status']!='PASS':raise RuntimeError(f'protected/nonzero stop: {out}: {r["guard"]}')
 return r
try:
 for layer in [37,0,52]:
  for strategy in (['multicast'] if a.phase=='prepare-multicast' else ['no-balancing','direct','chunk-streaming','multicast']):
   case=root/f'L{layer}'/strategy;case.mkdir(parents=True,exist_ok=True);prep=case/'prepared';dest=prep/('multicast-run' if strategy=='multicast' else 'run')
   rec=dict(layer=layer,tokens=2048,strategy=strategy,status='RUNNING',routing_sha256=sha(a.reference/'routing'/f'layer_{layer}.json'));ledger.append(rec);save()
   old=prior.get((layer,strategy))
   if old is not None:
    # Resume is only used after the prior driver exits. Preserve its ledger separately.
    assert a.phase=='run' and old.get('summary') and old.get('validation',{}).get('status')=='PASS'
    for st in ['preparation','preflight','simulator','postflight']:
     actual=json.loads((case/(st+'-host/resource.json')).read_text());assert actual['status']=='PASS' and actual['guard'] is None
     assert actual==old[st+'_host']
    assert sha(dest/'input.txt')==old['input_sha256'] and sha(dest/'plan.json')==old['plan_sha256']
    assert sha(dest/'assignments.csv')==old['assignments_sha256'] and rec['routing_sha256']==old['routing_sha256']
    assert json.loads((dest/'online-summary.json').read_text())==old['summary']
    assert json.loads((dest/'validation.json').read_text())==old['validation']
    rec.update(old);rec.pop('failure',None);rec.update(status='PASS',plan_semantic_sha256=semantic_plan(dest/'plan.json'),resumed_verified_case=True)
    save()
    # No simulator rerun: layer-level identity checks still execute below.
    if strategy!='multicast':continue
   if old is None:
    if a.phase=='prepare-multicast' or strategy!='multicast':
     rec['preparation_host']=stage([sys.executable,X/'prepare.py','--reference',a.reference,'--out',prep,'--graph-tool',a.graph_tool,'--manifest',a.manifest,'--counts',a.counts,'--layer',layer,'--strategy',strategy],case/'preparation-host')
    else:rec['preparation_host']=json.loads((case/'preparation-host/resource.json').read_text())
    rec['plan_semantic_sha256']=semantic_plan(dest/'plan.json')
    rec['capacity']=json.loads((prep/'capacity.json').read_text());rec['plan_sha256']=sha(dest/'plan.json');rec['assignments_sha256']=sha(dest/'assignments.csv');rec['input_sha256']=sha(dest/'input.txt')
    cfg=json.loads((dest/'config.json').read_text());rec['mapping_sha256']=hashlib.sha256(json.dumps(cfg['planner_input']['mapping'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    pre=[sys.executable,E/'tiered-logging/preflight.py',dest,'--graph-tool',a.graph_tool,'--out',case/'preflight.json','--input-summary',dest/'input-summary.json']
    if a.phase=='prepare-multicast' or strategy!='multicast':rec['preflight_host']=stage(pre,case/'preflight-host')
    else:rec['preflight_host']=json.loads((case/'preflight-host/resource.json').read_text())
    if a.phase=='prepare-multicast':rec['status']='PREPARED';save();continue
    gate=json.loads((root/'capacity-approved.json').read_text());assert gate['status']=='PASS' and set(gate['layers'])=={'0','37','52'}
    for gl in [0,37,52]:
     gd=root/f'L{gl}'/'multicast'/'prepared'/'multicast-run';entry=gate['layers'][str(gl)]
     assert sha(gd/'input.txt')==entry['input_sha256'] and sha(gd/'config.json')==entry['config_sha256']
    assert rec['preparation_host']['status']=='PASS' and rec['preflight_host']['status']=='PASS'
    assert json.loads((case/'preflight.json').read_text())['status']=='PASS'
    rec['simulator_host']=stage([a.binary,'--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],case/'simulator-host')
    rec['validation']=json.loads((dest/'validation.json').read_text());assert rec['validation']['status']=='PASS'
    post=pre.copy();post[post.index('--out')+1]=case/'postflight.json';rec['postflight_host']=stage(post+['--execution-summary',dest/'online-summary.json'],case/'postflight-host')
    rec['summary']=json.loads((dest/'online-summary.json').read_text());rec['metrics']=json.loads((dest/'simulator-metrics.json').read_text());rec['status']='PASS';save();print('CASE VERIFIED',layer,strategy,flush=True)
  if a.phase=='run':
   rows=ledger[-4:];assert len({r['mapping_sha256'] for r in rows})==1
   assert len({r['plan_semantic_sha256'] for r in rows[1:]})==1
   assert len({r['assignments_sha256'] for r in rows[1:]})==1
   assert len({r['summary']['combine_fnv1a64'] for r in rows})==1
   print('LAYER VERIFIED',layer,flush=True)
except Exception as e:
 if ledger:ledger[-1].update(status='STOPPED',failure=str(e))
 save();raise
save()
