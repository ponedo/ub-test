#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--old',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);results=[]
def stable(x):
 if isinstance(x,dict):return {k:stable(v) for k,v in x.items() if k!='verification_wall_ns'}
 if isinstance(x,list):return [stable(v) for v in x]
 return x
for name in ['nb-small','direct-small','chunk-small','multichunk-multita','ep64-n256']:
 out=a.out/name;out.mkdir();r=run([a.binary,'--input='+str((a.fixtures/name/'input.txt').resolve()),'--out='+str(out.resolve()),'--logLevel=summary','--jettyMode=pair','--capacityMetrics='+str((out/'simulator-metrics.json').resolve())],out/'host',3600,case=out);assert r['status']=='PASS'
 old=a.old/name/'summary/run'
 hashes={}
 for f in ['online-summary.json','validation.json','simulator-metrics.json']:
  x=json.loads((out/f).read_text());y=json.loads((old/f).read_text());assert stable(x)==stable(y),(name,f);hashes[f]=dict(old_sha256=hashlib.sha256((old/f).read_bytes()).hexdigest(),new_sha256=hashlib.sha256((out/f).read_bytes()).hexdigest(),equivalent_excluding_verification_wall_ns=True)
 results.append(dict(case=name,status='PASS',checks=hashes,host=r))
(a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS 5 unchanged small/EP64 output regressions')
