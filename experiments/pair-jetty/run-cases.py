#!/usr/bin/env python3
"""Sequential guarded real ns-3 runs, unchanged accepted inputs and strict verifier."""
import argparse,importlib.util,json,os,shutil,sys,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path[:0]=[str(H.parent/'wqe-completion-fix'),str(H.parents[2]/'prefill-cpu-tools')]
from guard import run

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
V=module('pair_verify',H.parent/'multi-npu-relay/verify.py')
L=module('pair_logical',H.parent/'jetty-resource-mapping/harness.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--group',choices=['nb','weights','all','one'],required=True);p.add_argument('--lib',type=Path,required=True);p.add_argument('--modes',nargs='+',choices=['per-wqe','pair'],default=['per-wqe','pair']);a=p.parse_args()
a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);ledger=[]
inputs=[a.inputs] if a.group=='one' else sorted(d.parent for d in a.inputs.glob('*/*/input.txt') if (d.parent.name=='no-balancing')==(a.group=='nb') or a.group=='all')
try:
 for source in inputs:
  caseid=source.parent.name+'-'+source.name;rows={}
  for mode in a.modes:
   case=a.out/caseid/mode;dest=case/'run';dest.mkdir(parents=True)
   for name in ['input.txt','config.json','plan.json','assignments.csv','transfers.csv','graph-input.txt','weight-edges.csv']:
    if (source/name).exists():shutil.copy2(source/name,dest/name)
   cmd=[str(a.binary.resolve()),'--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode='+mode,'--logLevel=debug']
   record={'case':caseid,'mode':mode,'inputs':{x.name:sha(x) for x in dest.iterdir()},'command':cmd}
   ledger.append(record)
   result=run(cmd,case/'host',300,case=case,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LD_LIBRARY_PATH':str(a.lib.resolve())})
   record['host']=result
   if result['status']!='PASS':raise RuntimeError('simulation failed '+caseid+' '+mode)
   verification=run([sys.executable,str(H/'verify.py'),str(dest),mode],case/'verifier-host',300,case=case)
   record['verifier_host']=verification
   if verification['status']!='PASS':raise RuntimeError('verification failed '+caseid+' '+mode)
   summary=json.loads((dest/'summary.json').read_text())
   record['verification']='PASS';record['summary']=summary;record['metrics']=json.loads((dest/'simulator-metrics.json').read_text())
   rows[mode]=json.loads((dest/'pair-validation.json').read_text())['logical']
   record['logical']=rows[mode]
   (a.out/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
  different=[k for k in rows['pair'] if rows['pair'][k]!=rows['per-wqe'][k]] if {'pair','per-wqe'}<=rows.keys() else []
  ledger[-1]['logical_differences']=different
  if different:raise RuntimeError('logical parity failed '+str(different))
  print(caseid,'PASS',flush=True)
finally:
 (a.out/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
