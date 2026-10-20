#!/usr/bin/env python3
"""Predeclared small cases; never choose cases after observing performance."""
import argparse,sys,os,json,hashlib,importlib.util,resource
from pathlib import Path
H=Path(__file__).resolve().parent;E=H.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
spec=importlib.util.spec_from_file_location('accepted_cases',E/'multi-npu-relay/cases.py');cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
import adapter
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case');p.add_argument('--skip-faults',action='store_true');a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);b=a.build.resolve();os.environ['RELAY_GRAPH_TOOL']=str(b/'graph-tool');resource.setrlimit(resource.RLIMIT_CORE,(0,0));results=[]
matrix={
 'no-replicas':(cases.loads(4,1,[32,0,0,0],slots=0),{},{}),
 'singleton':(cases.loads(4,1,[8,0,4,4]),{},{}),
 'multi-target':(cases.loads(4,1,[32,0,0,0]),{},dict(force_relay=True)),
 'disjoint-experts':(cases.loads(8,2,[128,128]+[0]*14,slots=3),{},dict(force_relay=True)),
 'window-disjoint':(cases.loads(8,2,[128,128]+[0]*14,slots=3),dict(weight_bytes=1048576),dict(force_relay=True)),
 'shared-receivers':(json.loads((H/'synthetic-overlap-input.json').read_text()),dict(weight_bytes=49152),{}),
 'delayed-ready':(cases.loads(4,1,[32,0,0,0]),dict(weight_completion_ns=10000),dict(force_relay=True)),
 'tail-segment':(cases.loads(4,1,[32,0,0,0]),dict(segment_bytes=333),dict(force_relay=True,chunk_bytes=2000)),
}
def stage(cmd,path,negative=None):
 r=run(cmd,path,3600,case=o)
 if negative:assert r['returncode']!=0 and not r['guard'] and negative in (path/'console.txt').read_text()
 else:assert r['status']=='PASS',str(path)
 return r
for name in ([a.case] if a.case else matrix):
 cfg,model,relay=matrix[name];base=o/name/'base';cases.base.emit(cfg,dict({'weight_bytes':12288},**model),'ultraep',base)
 baseline=o/name/'no-bal-base';cases.base.emit(cfg,dict({'weight_bytes':12288},**model),'no-balancing',baseline)
 for mode in ['no-balancing','direct','chunk-streaming','multicast-v2']:
  dest=o/name/mode;adapter.emit(baseline if mode=='no-balancing' else base,relay,'direct' if mode=='no-balancing' else mode,dest)
  pre=[sys.executable,H/'preflight.py',dest,'--graph-tool',b/'graph-tool','--out',dest/'preflight.json','--input-summary',dest/'input-summary.json']
  stage(pre,dest/'preflight-host');stage([b/'layer','--input='+str(dest/'input.txt'),'--out='+str(dest),'--logLevel=events','--jettyMode=pair','--capacityMetrics='+str(dest/'simulator-metrics.json')],dest/'simulator-host')
  stage(pre+['--execution-summary',dest/'online-summary.json'],dest/'postflight-host')
  stage([sys.executable,H/'verify.py',dest],dest/'independent-host')
  summary=json.loads((dest/'online-summary.json').read_text());results.append(dict(case=name,mode=mode,status='PASS',summary=summary,metrics=json.loads((dest/'simulator-metrics.json').read_text())))
  (o/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 rows=results[-4:];assert len({x['summary']['combine_fnv1a64'] for x in rows})==1
 configs={m:json.loads((o/name/m/'config.json').read_text()) for m in ['direct','multicast-v2']}
 assert configs['direct']['assignments']==configs['multicast-v2']['assignments'] and configs['direct']['transfers']==configs['multicast-v2']['transfers']
 assert rows[1]['metrics']['jettys']==rows[3]['metrics']['jettys']
 g=configs['multicast-v2']['multicast_groups']
 if name=='no-replicas':assert not g
 if name=='singleton':assert any(len(x['members'])==1 for x in g)
 if name=='multi-target':assert any(len(x['members'])>=2 for x in g)
 if name in ['disjoint-experts','window-disjoint']:
  assert len(g)>=2 and any(x['source']==y['source'] for i,x in enumerate(g) for y in g[i+1:])
 if name=='shared-receivers':
  assert any(x['source']!=y['source'] and set(m['target'] for m in x['members'])&set(m['target'] for m in y['members']) for i,x in enumerate(g) for y in g[i+1:])
 if name in ['disjoint-experts','window-disjoint','shared-receivers']:
  import csv
  wire=list(csv.DictReader((o/name/'multicast-v2/weight-packets.csv').open()));intervals={}
  for group in g:
   tids={m['task'] for m in group['members']};times=[int(x['time_ps']) for x in wire if x['kind']=='first_native' and int(x['task']) in tids];assert times
   intervals[group['group']]=(min(times),max(times))
  assert any(max(x[0],y[0])<min(x[1],y[1]) for i,x in enumerate(intervals.values()) for y in list(intervals.values())[i+1:]),'no actual first-send overlap'
  (o/name/'concurrency.json').write_text(json.dumps(dict(status='PASS',first_native_intervals=intervals),indent=2)+'\n')
if not a.skip_faults:
 import shutil
 reference=o/'multi-target/multicast-v2';assert reference.exists()
 for fault,reason in [('weight-byte','payload byte mismatch'),('early-wqe','sender completed before target data ready'),('premature-ready','ready before target completion coverage'),('duplicate-completion','audit premature/duplicate sender completion')]:
  dest=o/'faults'/fault;dest.mkdir(parents=True)
  stage([b/'layer','--input='+str(reference/'input.txt'),'--out='+str(dest),'--logLevel=events','--fault='+fault],dest/'host',reason)
 for fault in ['data-once','ack-once','invalidate-grant']:
  dest=o/'network'/fault;dest.mkdir(parents=True)
  for file in ['config.json','input.txt','plan.json','assignments.csv','transfers.csv','weight-edges.csv','graph-input.txt']:shutil.copyfile(reference/file,dest/file)
  stage([b/'layer','--input='+str(dest/'input.txt'),'--out='+str(dest),'--logLevel=events',*(['--invalidateGrant=1'] if fault=='invalidate-grant' else ['--nativeRetrans=1','--networkFault='+fault]),'--capacityMetrics='+str(dest/'simulator-metrics.json')],dest/'host')
  stage([sys.executable,H/'preflight.py',dest,'--graph-tool',b/'graph-tool','--execution-summary',dest/'online-summary.json'],dest/'postflight-host')
  stage([sys.executable,H/'verify.py',dest,*(['--grant'] if fault=='invalidate-grant' else ['--fault='+fault])],dest/'independent-host')
 if not a.case:
  for name,size,delay in [('paired-small',12288,1000),('paired-window',1048576,200000)]:
   dest=o/'pair-stress'/name
   stage([b/'pair-stress','--out='+str(dest),'--bytes='+str(size),'--delayNs='+str(delay)],dest/'host')
   stress=json.loads((dest/'summary.json').read_text());assert stress['status']=='PASS' and stress['groups']==5 and stress['children']==10 and stress['pair_jetties']==9
   if size>512*1024:assert stress['peak_ta_inflight']==512
identity={str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest() for x in [b/'layer',b/'graph-tool',a.native.resolve()/'build/lib/libns3.44-unified-bus.so']}
(o/'stage-a-status.json').write_text(json.dumps(dict(status='PASS',full_matrix=not a.case and not a.skip_faults,binary_identity=identity,cases=list(matrix) if not a.case else [a.case],modes=4),indent=2)+'\n')
print('PASS stage A')
