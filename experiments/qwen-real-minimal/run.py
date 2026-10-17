#!/usr/bin/env python3
"""Nine real-routing cases, stage guards, private inputs and aggregate outputs."""
import argparse,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
projection=module('projection',H.parent/'tiered-logging/project-summary.py')
compact=module('compact',H.parent/'ep64-token-scaling/compact.py').compact

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--lib',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--frozen-counts',type=Path,required=True);p.add_argument('--layers',nargs='+',type=int,default=[0,37,52]);a=p.parse_args()
if not __debug__:raise RuntimeError('validation requires Python assertions enabled')
root=a.private.resolve();root.mkdir(exist_ok=True);ledger=[];status=dict(status='RUNNING');env=dict(os.environ,LD_LIBRARY_PATH=str(a.lib.resolve()),RELAY_GRAPH_TOOL=str(a.graph_tool.resolve()))
def persist():
 (root/'runs.json').write_text(json.dumps(ledger,indent=2)+'\n');(root/'status.json').write_text(json.dumps(status,indent=2)+'\n')
def check():
 if shutil.disk_usage(root).free<8*1024**3:raise RuntimeError('disk_free_guard')
 if shutil.disk_usage('/tmp').free<2*1024**3:raise RuntimeError('tmp_disk_free_guard')
 if psutil.virtual_memory().available<1536*1024**2:raise RuntimeError('host_available_memory_guard')
def stage(cmd,out):
 check();res=run(cmd,out,3600,case=root,env=env)
 if res['status']!='PASS':
  status.update(failure_resource=str(out/'resource.json'),reason=res['guard'] or 'nonzero_exit');raise RuntimeError('stage protected stop '+str(out))
 return res
try:
 for layer in a.layers:
  reference=None
  for strategy in ['no-balancing','direct','chunk-streaming']:
   case=root/f'layer-{layer}'/strategy;case.mkdir(parents=True,exist_ok=False);prepared=case/'prepared';dest=prepared/'run'
   rec=dict(layer=layer,strategy=strategy,status='RUNNING',routing_sha256=sha(root/'routing'/f'layer_{layer}.json'));ledger.append(rec);persist()
   rec['preparation_host']=stage([sys.executable,H/'prepare.py','--routing',root/'routing'/f'layer_{layer}.json','--out',prepared,'--graph-tool',a.graph_tool,'--strategy',strategy,'--layer',layer,'--source-manifest',a.source_manifest,'--frozen-counts',a.frozen_counts],case/'preparation-host')
   rec['preparation_summary']=json.loads((prepared/'preparation-summary.json').read_text());rec['capacity']=json.loads((prepared/'capacity.json').read_text())
   config=json.loads((dest/'config.json').read_text());plan=json.loads((dest/'plan.json').read_text());mapping=config['planner_input']['mapping']
   rt=config['runtime'];assert (rt['model_dim'],rt['ff_dim'],rt['dtype_bytes'],rt['weight_dtype_bytes'],rt['weight_bytes'])==(4096,1536,2,1,18874368)
   assert rt['peak_gflops']*rt['util_permille']==500000
   assert config['planner_input']['main_placement']==[e//2 for e in range(128)]
   assert config['planner_input']['slots']==[2]*64
   if reference is None:reference=mapping
   assert mapping==reference
   pre=[sys.executable,H.parent/'tiered-logging/preflight.py',dest,'--graph-tool',a.graph_tool,'--out',case/'preflight.json','--input-summary',dest/'input-summary.json']
   rec['preflight_host']=stage(pre,case/'preflight-host')
   rec['simulator_host']=stage([a.binary,'--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],case/'simulator-host')
   rec['validation']=json.loads((dest/'validation.json').read_text());assert rec['validation']['status']=='PASS'
   post=pre.copy();post[post.index('--out')+1]=case/'postflight.json';rec['postflight_host']=stage(post+['--execution-summary',dest/'online-summary.json'],case/'postflight-host')
   rec['summary'],rec['times']=projection.project(dest);rec['metrics']=json.loads((dest/'simulator-metrics.json').read_text());rec['online_summary']=json.loads((dest/'online-summary.json').read_text())
   assert rec['summary']['tokens']==256 and rec['summary']['assignments']==2048
   rec['npu_load']=[sum(p['quota'] for p in plan['physical'] if p['rank']==r) for r in range(64)]
   rec['status']='PASS';persist();print('VERIFIED',layer,strategy,rec['summary']['layer_latency_ps'],flush=True)
   # Compress only this newly generated private case, verified by existing tool.
   rec['private_compaction']=compact(prepared,case/'prepared-evidence');persist()
  rows=[r for r in ledger if r['layer']==layer]
  for r in rows:r['speedup']=rows[0]['summary']['layer_latency_ps']/r['summary']['layer_latency_ps']
  persist()
 status['status']='PASS'
except Exception as e:
 if ledger and ledger[-1]['status']=='RUNNING':ledger[-1].update(status='STOPPED',failure=str(e))
 status.update(status='STOPPED',error=str(e));print('STOP',e,flush=True)
finally:persist()
if status['status']!='PASS':sys.exit(2)
