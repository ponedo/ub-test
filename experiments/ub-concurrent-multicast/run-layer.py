#!/usr/bin/env python3
"""Fixed small end-to-end matrix, all strategies share exactly the same accepted plan."""
import argparse,sys,json,os,subprocess,hashlib,csv
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
sys.path.insert(0,str(E/'multi-npu-relay'));import cases,adapter
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case',default='multi4_force');p.add_argument('--log-level',default='summary');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve());ledger=[]
# Same bounded synthetic fixtures as the accepted relay cases, without loading its unrelated EP64 artifact.
topk2=cases.loads(4,2,[0]*8,slots=2);topk2.update(top_k=2,mapping=[dict(source=i%4,experts=[0,1]) for i in range(32)])
single=cases.loads(4,1,[8,0,4,4]);multi=cases.loads(4,1,[32,0,0,0]);many=cases.loads(8,2,[40]*4+[0]*12,slots=3)
selected={'topk2_4':(topk2,{},dict(force_relay=True)),'single4':(single,{},{}),'slots_zero4':(cases.loads(4,1,[32,0,0,0],slots=0),{},{}),'multi4_force':(multi,{},dict(force_relay=True)),'tail4':(multi,dict(model_dim=65,ff_dim=129,segment_bytes=333),dict(force_relay=True,chunk_bytes=2000)),'multi_expert8':(many,{},dict(force_relay=True)),'slow_relay8':(cases.loads(8,1,[64]+[0]*7),{},dict(slow_relay_rank=1,slow_relay_ns=20000))};names=['single4','slots_zero4','multi4_force','tail4','multi_expert8','slow_relay8','topk2_4'] if a.case=='all' else [a.case]
for name in names:
 cfg,model,relay=selected[name];base=a.out/name/'base';cases.base.emit(cfg,model,'ultraep',base);identity={x:hashlib.sha256((base/x).read_bytes()).hexdigest() for x in ['plan.json','assignments.csv']}
 for mode in ['direct','chunk-streaming','multicast']:
  dest=a.out/name/mode;adapter.emit(base,relay,mode,dest);assert all(hashlib.sha256((dest/x).read_bytes()).hexdigest()==h for x,h in identity.items())
  cmd=[sys.executable,E/'tiered-logging/preflight.py',dest,'--graph-tool',a.graph_tool,'--out',dest/'preflight.json','--input-summary',dest/'input-summary.json']
  for stage,command in [('preflight',cmd),('simulator',[a.binary,'--input='+str(dest/'input.txt'),'--out='+str(dest),'--logLevel='+a.log_level,'--jettyMode=pair','--capacityMetrics='+str(dest/'simulator-metrics.json')]),('postflight',cmd+['--execution-summary',dest/'online-summary.json'])]:
   r=run(command,dest/(stage+'-host'),3600,case=a.out);assert r['status']=='PASS',(name,mode,stage)
  summary=json.loads((dest/'online-summary.json').read_text());validation=json.loads((dest/'validation.json').read_text());assert validation['status']=='PASS'
  row=dict(case=name,strategy=mode,status='PASS',plan_hash=identity['plan.json'],assignments_hash=identity['assignments.csv'],summary=summary,validation=validation,host={stage:json.loads((dest/(stage+'-host/resource.json')).read_text()) for stage in ['preflight','simulator','postflight']});ledger.append(row)
  (a.out/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
 rows=ledger[-3:];assert len({r['summary']['combine_fnv1a64'] for r in rows})==1;assert len({r['summary']['completed_tokens'] for r in rows})==1
print('PASS end-to-end fixed matrix')
