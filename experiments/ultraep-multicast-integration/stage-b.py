#!/usr/bin/env python3
"""Fixed, private L37/N2048 four-strategy matrix. No implicit resume or expansion."""
import argparse,hashlib,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent;E=H.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
import adapter
p=argparse.ArgumentParser()
for k in ['build','native','stage-a','out','routing','manifest','counts']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();o=a.out.resolve();b=a.build.resolve();n=a.native.resolve()
def sha(x):return hashlib.sha256(Path(x).read_bytes()).hexdigest()
def semantic(x):
 d=json.loads(Path(x).read_text());d.pop('cpu_wall_ns',None);return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
identity={str(x.resolve()):sha(x) for x in [b/'layer',b/'graph-tool',n/'build/lib/libns3.44-unified-bus.so']}
gate=json.loads((a.stage_a/'stage-a-status.json').read_text());assert gate['status']=='PASS' and gate['full_matrix'] and gate['binary_identity']==identity,'Stage A build/gate mismatch'
expected={'routing':'4b2f70871b969730a8f85aace4357d28b2e069d2f0d16a738a0c35eca691a0e5','manifest':'d5708f02b9ffa6e19500725685272ad840760d9c6b5f5f475f12bc3560405db6','counts':'e3163d85c2ada0373cb73dad19a3efeac7d0774f1b56852aacdcf9b264c94c4e'}
for k,v in expected.items():assert sha(getattr(a,k))==v,k+' input identity'
o.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(b/'graph-tool');rows=[];ledger=dict(status='RUNNING',binary_identity=identity,input_identity=expected,preparation={},runs=rows)
def save():(o/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
def stage(cmd,path):
 r=run(cmd,path,3600,case=o)
 if r['status']!='PASS':raise RuntimeError('guard/nonzero stop: '+str(path))
 return r
save()
try:
 for mode in ['no-balancing','direct']:
  ledger['preparation'][mode]=stage([sys.executable,E/'qwen-real-minimal/prepare.py','--routing',a.routing.resolve(),'--out',o/('prepare-'+mode),'--graph-tool',b/'graph-tool','--tokens','2048','--layer','37','--source-manifest',a.manifest.resolve(),'--frozen-counts',a.counts.resolve(),'--strategy',mode],o/('prepare-'+mode+'-host'));save()
 params=json.loads((E/'qwen-prefill-token-scaling/fixed-config.json').read_text())['relay_parameters']
 for mode in ['no-balancing','direct','chunk-streaming','multicast-v2']:
  dest=o/mode;source=o/('prepare-no-balancing' if mode=='no-balancing' else 'prepare-direct')/'direct-input'
  emitted=stage([sys.executable,H/'adapter.py','--source',source,'--out',dest,'--strategy','direct' if mode=='no-balancing' else mode],o/(mode+'-adapter-host'))
  cfg=json.loads((dest/'config.json').read_text());runtime=cfg['runtime']
  assert cfg['planner_input']['npus']==64 and len(cfg['planner_input']['mapping'])==2048
  assert runtime['weight_bytes']==18874368 and runtime['segment_bytes']==1024
  rec=dict(strategy=mode,status='PREPARED',adapter_host=emitted,plan_sha256=sha(dest/'plan.json'),plan_semantic_sha256=semantic(dest/'plan.json'),assignments_sha256=sha(dest/'assignments.csv'),input_sha256=sha(dest/'input.txt'),config_sha256=sha(dest/'config.json'));rows.append(rec)
  pre=[sys.executable,H/'preflight.py',dest,'--graph-tool',b/'graph-tool','--out',dest/'preflight.json','--input-summary',dest/'input-summary.json']
  rec['preflight_host']=stage(pre,dest/'preflight-host');save()
 assert len({r['plan_semantic_sha256'] for r in rows[1:]})==1 and len({r['assignments_sha256'] for r in rows[1:]})==1
 assert rows[1]['plan_semantic_sha256']=='55b8de3bc0e6773ac265f84883f4c2940ec5ff9e049b29fcccbfb6275a0f0f94'
 assert rows[1]['assignments_sha256']=='1a7f767d035076f898f5ce7ee8ab02d65eb9f40d057cc2c99931e97c9c1bf566'
 ledger['capacity_gate']='PASS';save()
 for rec in rows:
  if rec['strategy']!='no-balancing' and rows[0]['simulator_host']['wall_seconds']*1220.776/129.570>3600:
   raise RuntimeError('RESOURCE_READMISSION: exact historical relative-work projection from measured NoBal exceeds3600s. Preserve results and diagnose before admission.')
  dest=o/rec['strategy'];assert identity=={k:sha(k) for k in identity},'build changed during experiment'
  rec['status']='RUNNING';save();print('START',rec['strategy'],flush=True)
  rec['simulator_host']=stage([b/'layer','--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],dest/'simulator-host')
  rec['postflight_host']=stage([sys.executable,H/'preflight.py',dest,'--graph-tool',b/'graph-tool','--out',dest/'postflight.json','--execution-summary',dest/'online-summary.json'],dest/'postflight-host')
  rec['independent_host']=stage([sys.executable,H/'verify.py',dest],dest/'independent-host')
  rec.update(status='PASS',summary=json.loads((dest/'online-summary.json').read_text()),metrics=json.loads((dest/'simulator-metrics.json').read_text()));save();print('VERIFIED',rec['strategy'],flush=True)
 assert len({r['summary']['combine_fnv1a64'] for r in rows})==1
 ledger['status']='PASS';save()
except Exception as e:
 ledger.update(status='STOPPED',failure=str(e));save();raise
