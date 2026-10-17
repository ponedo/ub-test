#!/usr/bin/env python3
"""Select one serialized layer and an exact real-token prefix, privately."""
import argparse,hashlib,json
from pathlib import Path
import source_audit

def extract(manifest,counts,layer,tokens,audit_out):
 if type(layer)!=int or not 0<=layer<94:raise ValueError('serialized layer outside0..93')
 if type(tokens)!=int or not 1<=tokens<=4275:raise ValueError('batch prefix outside1..4275')
 summary,_=source_audit.audit(manifest,counts,audit_out)
 requests=json.loads(Path(manifest).read_text())['requests'];selected=[]
 for req in requests:
  path=Path(req['file_path']);path=path if path.is_absolute() else Path(manifest).parent/path
  source=json.loads(path.read_text(),object_pairs_hook=source_audit.unique)
  for ordinal,experts in enumerate(source[0][str(layer)]):
   if len(selected)==tokens:break
   selected.append(dict(request_id=req['request_id'],token_ordinal=ordinal,experts=experts))
  if len(selected)==tokens:break
 if len(selected)!=tokens or len({(r['request_id'],r['token_ordinal']) for r in selected})!=tokens:raise ValueError('insufficient or duplicate source tokens')
 return dict(serialized_layer=layer,tokens=selected,source_manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest())
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--frozen-counts',type=Path,required=True);p.add_argument('--layer',type=int,required=True);p.add_argument('--tokens',type=int,default=256);p.add_argument('--out',type=Path,required=True);p.add_argument('--audit-out',type=Path,required=True);a=p.parse_args()
 if a.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):raise ValueError('routing output must be private outside repository')
 result=extract(a.manifest,a.frozen_counts,a.layer,a.tokens,a.audit_out);a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x') as f:json.dump(result,f,separators=(',',':'));f.write('\n')
 a.out.chmod(0o600)
 if json.loads(a.out.read_text())!=result:raise ValueError('export readback mismatch')
 print(json.dumps(dict(tokens=a.tokens,layer=a.layer,sha256=hashlib.sha256(a.out.read_bytes()).hexdigest())))
if __name__=='__main__':main()
