#!/usr/bin/env python3
"""Fixed, private L37/N2048 four-strategy matrix. No implicit resume or expansion."""
import argparse,hashlib,json,os,sys,copy,re
from pathlib import Path
import os
if not __debug__ or os.environ.get('PYTHONOPTIMIZE'):
 raise RuntimeError('Python optimization is forbidden: all validation assertions must execute')
H=Path(__file__).resolve().parent;E=H.parent
from guard import run
p=argparse.ArgumentParser()
for k in ['build','native','stage-a','out','routing','manifest','counts','source-identity']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();o=a.out.resolve();b=a.build.resolve();n=a.native.resolve()
def sha(x):return hashlib.sha256(Path(x).read_bytes()).hexdigest()
def semantic(x):
 d=json.loads(Path(x).read_text());d.pop('cpu_wall_ns',None);return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
identity={str(x.resolve()):sha(x) for x in [b/'layer',b/'parent-layer',b/'graph-tool',*[x for x in sorted((n/'build/lib').glob('libns3.44-*.so')) if '-test.so' not in x.name]]}
assert len(identity)>3, 'native shared library identities missing'
source_identity=json.loads(a.source_identity.read_text())
assert source_identity and all(sha(k)==v for k,v in source_identity.items()), 'source identity mismatch'
gate_path=a.stage_a/'status.json';gate=json.loads(gate_path.read_text())
assert gate['status']=='PASS' and gate['binary_identity']==identity and gate['source_identity']==source_identity, 'Stage A immutable identity mismatch'
assert gate['link_gbps']==[100,3136] and gate['strategies']==['no-balancing','direct','chunk-streaming','multicast-v2']
assert all(gate[k] is True for k in ['small_cases_pass','native_rate_probe_pass','fault_smoke_pass']), 'small-stage correctness gate missing' 
baseline_path=E/'qwen-roofline-compute/results/summary.json'
assert sha(baseline_path)=='889b1b5346a11696d9d8b6ba6a6d48b4d560325efc61554f6275de26f05e879f', 'accepted baseline summary identity mismatch'
baseline_summary=json.loads(baseline_path.read_text());assert baseline_summary['status']=='PASS' and baseline_summary['native_source_unchanged'] is True
baseline_identity={x['strategy']:x for x in baseline_summary['planning_identity']}
reuse=dict(status='PENDING',accepted_commit='3c2275eafea79426a441c819c8b65268492ff08e',accepted_summary_sha256=sha(baseline_path),source_identity_sha256=sha(a.source_identity),native_source_hashes=109,source_files_unchanged=True,binary_identity_note='Same accepted source and build recipe; new binary paths and hashes are recorded, not claimed byte-identical to the historical build.',small_stage_note='Current small-stage PASS is required; historical aggregate summary comparisons are partial numerical checks, not full historical execution replay.',strategies=[])
expected={'routing':'4b2f70871b969730a8f85aace4357d28b2e069d2f0d16a738a0c35eca691a0e5','manifest':'d5708f02b9ffa6e19500725685272ad840760d9c6b5f5f475f12bc3560405db6','counts':'e3163d85c2ada0373cb73dad19a3efeac7d0774f1b56852aacdcf9b264c94c4e'}
for k,v in expected.items():assert sha(getattr(a,k))==v,k+' input identity'
o.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(b/'graph-tool');rows=[];ledger=dict(status='RUNNING',accepted_commit='3c2275e',link_gbps=3136,baseline_link_gbps=100,checkpoint_decision='continue_full_matrix',source_identity=source_identity,stage_a_path=str(gate_path.resolve()),stage_a_sha256=sha(gate_path),binary_identity=identity,input_identity=expected,input_paths={k:str(getattr(a,k).resolve()) for k in expected},preparation={},runs=rows)
def save():
 (o/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 (o/'baseline-reuse.json').write_text(json.dumps(reuse,indent=2)+'\n')
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
  emitted=stage([sys.executable,E/'ultraep-multicast-integration/adapter.py','--source',source,'--out',dest,'--strategy','direct' if mode=='no-balancing' else mode],o/(mode+'-adapter-host'))
  cfg=json.loads((dest/'config.json').read_text());runtime=cfg['runtime']
  actual=dict(strategy=mode,plan_semantic_sha256=semantic(dest/'plan.json'),assignments_sha256=sha(dest/'assignments.csv'),input_sha256=sha(dest/'input.txt'),config_sha256=sha(dest/'config.json'))
  assert actual==baseline_identity[mode], '100 Gbps baseline parity mismatch for '+mode+'; stop, do not reuse'
  reuse['strategies'].append(dict(actual,status='EXACT_HASH_MATCH'));save()
  baseline_cfg_bytes=(dest/'config.json').read_bytes()
  baseline_cfg=copy.deepcopy(cfg);baseline_text=(dest/'input.txt').read_text()
  assert runtime['link_gbps']==100 and cfg['parameters']['link_gbps']==100
  runtime['link_gbps']=3136;cfg['parameters']['link_gbps']=3136
  matches=list(re.finditer(r'\S+',baseline_text));assert matches[12].group()=='100'
  token=matches[12];changed_text=baseline_text[:token.start()]+'3136'+baseline_text[token.end():]
  assert baseline_text.split()[:12]+baseline_text.split()[13:]==changed_text.split()[:12]+changed_text.split()[13:]
  (dest/'baseline-config.json').write_bytes(baseline_cfg_bytes)
  (dest/'baseline-input.txt').write_text(baseline_text)
  (dest/'config.json').write_text(json.dumps(cfg,indent=2)+'\n');(dest/'input.txt').write_text(changed_text)
  assert [int(x.group()) for x in matches[:6]]==[64,128,8,2048,4096,1536]
  assert cfg['planner_input']==baseline_cfg['planner_input']
  assert cfg['planner_input']['npus']==64 and len(cfg['planner_input']['mapping'])==2048
  assert runtime['weight_bytes']==18874368 and runtime['segment_bytes']==1024
  rec=dict(strategy=mode,status='PREPARED',adapter_host=emitted,plan_sha256=sha(dest/'plan.json'),plan_semantic_sha256=semantic(dest/'plan.json'),assignments_sha256=sha(dest/'assignments.csv'),input_sha256=sha(dest/'input.txt'),config_sha256=sha(dest/'config.json'),baseline_input_sha256=sha(dest/'baseline-input.txt'),baseline_config_sha256=sha(dest/'baseline-config.json'),immutable_files={x.name:sha(x) for x in dest.iterdir() if x.is_file()});rows.append(rec)
  pre=[sys.executable,E/'ultraep-multicast-integration/preflight.py',dest,'--graph-tool',b/'graph-tool','--out',dest/'preflight.json','--input-summary',dest/'input-summary.json']
  rec['preflight_host']=stage(pre,dest/'preflight-host');save()
 assert len({r['plan_semantic_sha256'] for r in rows[1:]})==1 and len({r['assignments_sha256'] for r in rows[1:]})==1
 assert rows[1]['plan_semantic_sha256']=='55b8de3bc0e6773ac265f84883f4c2940ec5ff9e049b29fcccbfb6275a0f0f94'
 assert rows[1]['assignments_sha256']=='1a7f767d035076f898f5ce7ee8ab02d65eb9f40d057cc2c99931e97c9c1bf566'
 ledger['capacity_gate']='PASS';save()
 assert all(sha(k)==v for k,v in source_identity.items()), 'source changed during preparation'
 assert all(sha(k)==v for k,v in identity.items()), 'binary changed during preparation'
 reuse['status']='PASS';reuse['reuse_basis']='All four baseline config/input/assignments SHA256 and semantic Planner SHA256 exactly match accepted published evidence; unchanged accepted source and current two-rate small-stage gate.'
 ledger['baseline_reuse']='EXACT_INPUT_CONFIG_PLANNER_PARITY';ledger['baseline_evidence_path']=str(baseline_path.resolve());ledger['baseline_evidence_sha256']=sha(baseline_path)
 ledger["status"]="PREPARED";save()
except Exception as e:
 reuse.update(status="STOPPED",failure=str(e));ledger.update(status="STOPPED",failure=str(e));save();raise

