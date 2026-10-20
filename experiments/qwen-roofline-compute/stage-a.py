import argparse,os,sys,json,hashlib,importlib.util,shutil
from pathlib import Path
from guard import run
H=Path(__file__).resolve().parent;OLD=H.parent/'ultraep-multicast-integration'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cases=load('accepted_cases',H.parent/'multi-npu-relay/cases.py');adapter=load('v2_adapter',OLD/'adapter.py')
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(b/'graph-tool')
rows=[]
def stage(cmd,d,negative=None):
 x=run(cmd,d,1800,case=o)
 if negative:assert x['returncode']!=0 and not x['guard'] and negative in (d/'console.txt').read_text()
 else:assert x['status']=='PASS',str(d)
 return x
stage([sys.executable,H/'test-model.py',b/'model-probe',o/'unit'],o/'unit-host')
parent=(OLD/'layer.cc').read_text();new=(H/'layer.cc').read_text()
for start,end in [('    void Compute(', '    void Ready('),('    void Ready(', '    void Gate('),('    void Gate(', '    void Run(')]:
 assert parent[parent.index(start):parent.index(end)]==new[new.index(start):new.index(end)],start
oldbody=parent.split('uint64_t Duration(uint32_t count){',1)[1].split('\n',1)[0];newbody=new.split('uint64_t LegacyDuration(uint32_t count){',1)[1].split('\n',1)[0];assert oldbody==newbody
matrix={'no-replicas':cases.loads(4,1,[32,0,0,0],slots=0),'singleton':cases.loads(4,1,[8,0,4,4]),'multi-target':cases.loads(4,1,[32,0,0,0]),'multi-expert':cases.loads(8,2,[128,128]+[0]*14,slots=3)}
for name,cfg in matrix.items():
 base=o/name/'base';nb=o/name/'no-bal-base';cases.base.emit(cfg,dict(weight_bytes=12288),'ultraep',base);cases.base.emit(cfg,dict(weight_bytes=12288),'no-balancing',nb)
 for mode in ['no-balancing','direct','chunk-streaming','multicast-v2']:
  ref=None
  for model,binary in [('parent',b/'parent-layer'),('legacy',b/'layer'),('roofline',b/'layer')]:
   d=o/name/mode/model;adapter.emit(nb if mode=='no-balancing' else base,dict(force_relay=True),'direct' if mode=='no-balancing' else mode,d)
   stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool'],d/'preflight-host')
   cmd=[binary,'--input='+str(d/'input.txt'),'--out='+str(d),'--logLevel=summary','--jettyMode=pair','--capacityMetrics='+str(d/'simulator-metrics.json')]
   if model!='parent':cmd+=['--computeModel='+model,'--compute-tflops=100','--hbm-bandwidth-gbps=2692']
   stage(cmd,d/'simulator-host');stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',b/'graph-tool','--execution-summary',d/'online-summary.json'],d/'postflight-host');stage([sys.executable,OLD/'verify.py',d],d/'independent-host')
   if model!='parent':stage([sys.executable,H/'verify-compute.py',d,'--expected-model='+model],d/'compute-host')
   s=json.loads((d/'online-summary.json').read_text());s.pop('verification_wall_ns')
   if model=='parent':ref=s
   elif model=='legacy':assert s==ref,'legacy semantic mismatch'
   rows.append(dict(case=name,strategy=mode,model=model,status='PASS',summary=s));(o/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
reference=o/'multi-target/multicast-v2/legacy'
for model in ['legacy','roofline']:
 for fault in ['data-once','ack-once','invalidate-grant']:
  d=o/'network'/model/fault;d.mkdir(parents=True)
  for f in reference.iterdir():
   if f.name in ['config.json','input.txt','plan.json','assignments.csv','transfers.csv','weight-edges.csv','graph-input.txt']:shutil.copyfile(f,d/f.name)
  stage([b/'layer','--input='+str(d/'input.txt'),'--out='+str(d),'--computeModel='+model,'--logLevel=events','--capacityMetrics='+str(d/'simulator-metrics.json'),*(['--invalidateGrant=1'] if fault=='invalidate-grant' else ['--nativeRetrans=1','--networkFault='+fault])],d/'simulator-host')
  stage([sys.executable,OLD/'verify.py',d,*(['--grant'] if fault=='invalidate-grant' else ['--fault='+fault])],d/'independent-host');stage([sys.executable,H/'verify-compute.py',d,'--expected-model='+model],d/'compute-host')
for fault,reason in [('weight-byte','payload byte mismatch'),('early-wqe','sender completed before target data ready'),('premature-ready','ready before target completion coverage'),('duplicate-completion','audit premature/duplicate sender completion')]:
 d=o/'negative'/fault;stage([b/'layer','--input='+str(reference/'input.txt'),'--out='+str(d),'--computeModel=roofline','--fault='+fault],d/'host',reason)
for rate in ['100.5','100junk','100 junk','1e2','-1','0','18446744073709551616']:
 d=o/'invalid-rate'/rate;stage([b/'layer','--input='+str(reference/'input.txt'),'--out='+str(d),'--computeModel=roofline','--compute-tflops='+rate],d/'host','ERROR:')
identity={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [b/'layer',b/'parent-layer',b/'graph-tool',*[x for x in sorted((a.native.resolve()/'build/lib').glob('libns3.44-*.so')) if '-test.so' not in x.name]]}
(o/'status.json').write_text(json.dumps(dict(status='PASS',legacy_exact_cases=16,roofline_cases=16,native_smoke=6,negative_correctness=4,invalid_cli=7,binary_identity=identity),indent=2)+'\n');print('PASS stage A')
