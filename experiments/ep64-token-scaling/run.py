#!/usr/bin/env python3
"""Sequential scale gates, real accepted ns-3 execution, strict verifier, unchanged guards."""
import argparse,csv,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run,snapshot
from compact import compact,sha
from restore import restore
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--lib',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--reference-raw',type=Path);p.add_argument('--tokens',type=int,nargs='+',default=[256,1024,2048,4096,6250,8192,12500]);a=p.parse_args()
raw=a.raw.resolve();raw.mkdir(parents=True,exist_ok=True)
assert a.tokens==sorted(set(a.tokens)) and set(a.tokens)<=set([256,1024,2048,4096,6250,8192,12500])
references=json.loads((a.reference_raw/'runs.json').read_text()) if a.reference_raw else []
ledger=[];current_record=None;status={'status':'RUNNING','completed_token_points':[]}
(raw/'host-start.json').write_text(json.dumps(snapshot(),indent=2)+'\n')
env={'PATH':str(Path(sys.executable).parent)+':/usr/bin:/bin','LANG':'C.UTF-8','LD_LIBRARY_PATH':str(a.lib.resolve()),'RELAY_GRAPH_TOOL':str(a.graph_tool.resolve())}
def persist():
 (raw/'runs.json').write_text(json.dumps(ledger,indent=2)+'\n');(raw/'status.json').write_text(json.dumps(status,indent=2)+'\n')
def check_guard():
 if shutil.disk_usage(raw).free<8*1024**3:raise RuntimeError('disk_free_guard preflight')
 if shutil.disk_usage('/tmp').free<2*1024**3:raise RuntimeError('tmp_disk_free_guard preflight')
def checked(cmd,where):
 check_guard();r=run(cmd,where,300,case=raw,env=env)
 if r['status']!='PASS':
  status['failure_resource']=str(where/'resource.json');status['failure_measurement']=r
  if current_record is not None:current_record.update(status='FAIL',failure_resource=str(where/'resource.json'),failure_reason=r['guard'] or 'nonzero_exit')
  raise RuntimeError('stage failed '+str(where)+' '+str(r['guard']))
 return r
try:
 for tokens in a.tokens:
  current_record=None
  check_guard();point=raw/f'tokens-{tokens}';point.mkdir(exist_ok=False)
  prep=point/'prepared'
  pr=checked([sys.executable,str(H/'prepare.py'),'--tokens',tokens,'--out',prep,'--graph-tool',a.graph_tool],point/'preparation-host')
  pm=json.loads((prep/'preparation-metrics.json').read_text());load=json.loads((prep/'expert-load.json').read_text())
  for name in ['routing.csv','expert-load.json','preparation-metrics.json']:shutil.copy2(prep/name,point/name)
  if a.reference_raw and (a.reference_raw/f'tokens-{tokens}'/'routing.csv').exists():
   assert sha(prep/'routing.csv')==sha(a.reference_raw/f'tokens-{tokens}'/'routing.csv'),'restart routing changed'
  compact(prep,point/'prepared-evidence')
  reference={};rows=[]
  for strategy in ['no-balancing','direct','chunk-streaming']:
   arm=point/strategy;dest=arm/'run';restore(point/'prepared-evidence',dest,prefix=strategy)
   rec={'tokens':tokens,'assignments':tokens*8,'strategy':strategy,'routing_sha256':pm['shared_routing_sha256'],'input_hashes':{x.name:sha(x) for x in dest.iterdir() if x.is_file()},'expert_load':load,'preparation_host':pr,'planner_cpu_wall_seconds':pm['planner_cpu_wall_seconds']['no-balancing' if strategy=='no-balancing' else 'ultraep']};ledger.append(rec);current_record=rec;persist()
   for old in references:
    if old['tokens']==tokens and old['strategy']==strategy:
     assert rec['input_hashes']==old['input_hashes'],'restart input bytes changed'
     (point/'restart-input-parity.json').write_text(json.dumps({'status':'PASS','reference_raw':str(a.reference_raw),'routing_sha256':rec['routing_sha256'],'strategy':strategy,'old_input_hashes':old['input_hashes'],'new_input_hashes':rec['input_hashes']},indent=2)+'\n')
   cmd=[a.binary.resolve(),'--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode=pair']
   rec['simulator_host']=checked(cmd,arm/'simulator-host');persist()
   rec['verifier_host']=checked([sys.executable,str(H.parent/'pair-jetty/verify.py'),dest,'pair'],arm/'verifier-host')
   rec['summary']=json.loads((dest/'summary.json').read_text());rec['metrics']=json.loads((dest/'simulator-metrics.json').read_text());rec['validation']=json.loads((dest/'pair-validation.json').read_text())
   # Actual event spans include local transfers; per-NPU compute overlaps other ranks.
   spans={};times={}
   with (dest/'events.csv').open() as f:
    for e in csv.DictReader(f):
     key=(e['event'],int(e['stage']));t=int(e['time_ps']);spans.setdefault(key,[t,t]);spans[key]=[min(spans[key][0],t),max(spans[key][1],t)]
   for name,stage in [('dispatch',0),('combine',1)]:
    times[name+'_start_ps']=spans[('send',stage)][0];times[name+'_end_ps']=spans[('data_ready',stage)][1];times[name+'_span_ps']=times[name+'_end_ps']-times[name+'_start_ps']
   times['compute_start_ps']=spans[('compute_start',-1)][0];times['compute_end_ps']=spans[('compute_end',-1)][1];times['compute_span_ps']=times['compute_end_ps']-times['compute_start_ps']
   rec['event_spans']=times
   c=json.loads((dest/'config.json').read_text());plan=json.loads((dest/'plan.json').read_text())
   rec['plan_load']=[sum(p['quota'] for p in plan['physical'] if p['rank']==r) for r in range(64)]
   rec['physical_quota_sum']=sum(p['quota'] for p in plan['physical']);assert rec['physical_quota_sum']==tokens*8
   routing=c['planner_input']['mapping']
   if not reference:reference={'routing':routing,'plan':None}
   assert routing==reference['routing']
   if strategy=='direct':reference['plan']=plan
   if strategy=='chunk-streaming':assert plan==reference['plan']
   assert rec['summary']['tokens']==tokens and rec['summary']['assignments']==tokens*8
   rec['status']='PASS';persist()
   # Retain compact readable run summary alongside losslessly packed raw bytes.
   (point/(strategy+'-result.json')).write_text(json.dumps(rec,indent=2)+'\n')
   rec['evidence_compaction']=compact(arm,point/(strategy+'-evidence'));persist();rows.append(rec)
   print('VERIFIED',tokens,strategy,rec['summary']['layer_latency_ps'],flush=True)
  for rec in rows:
   rec['speedup']=rows[0]['summary']['layer_latency_ps']/rec['summary']['layer_latency_ps']
   (point/(rec['strategy']+'-result.json')).write_text(json.dumps(rec,indent=2)+'\n')
  status['completed_token_points'].append(tokens);persist()
 status['status']='PASS'
except Exception as ex:
 status.update(status='STOPPED',reason=str(ex));print('STOP',ex,flush=True)
finally:persist()
if status['status']!='PASS':sys.exit(2)
