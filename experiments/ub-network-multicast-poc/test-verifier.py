#!/usr/bin/env python3
"""Mutate temporary evidence copies; accepted source and receiver files remain untouched."""
import argparse,csv,json,shutil,tempfile
from pathlib import Path
from verify import verify,rows

def write(p,data):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('case',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 assert verify(a.case)['status']=='PASS';results=[]
 for kind in ['corrupt_payload','truncate_payload','duplicate_target','wrong_member','early_complete','duplicate_credit_return','wrong_source_copy_count']:
  with tempfile.TemporaryDirectory(prefix='network-verifier-') as td:
   dst=Path(td)/'case';shutil.copytree(a.case,dst,ignore=shutil.ignore_patterns('host'))
   if kind in ['corrupt_payload','truncate_payload']:
    p=next(dst.glob('rank*-object*.bin'));b=bytearray(p.read_bytes())
    if kind=='corrupt_payload':b[0]^=1
    else:b=b[:-1]
    p.write_bytes(b)
   elif kind in ['duplicate_target','wrong_member','early_complete']:
    p=dst/'targets.csv';r=rows(p)
    if kind=='duplicate_target':r.append(r[0].copy())
    elif kind=='wrong_member':r[0]['rank']='4'
    else:r[0]['complete_ns']='0'
    write(p,r)
   else:
    p=dst/'ports.csv';r=rows(p)
    if kind=='duplicate_credit_return':r[0]['credit_returned']=str(int(r[0]['credit_returned'])+1)
    else:r[0]['data_tx_bytes']=str(int(r[0]['data_tx_bytes'])+1)
    write(p,r)
   try:verify(dst)
   except (AssertionError,FileNotFoundError):results.append(dict(fault=kind,status='DETECTED'))
   else:raise RuntimeError('Verifier missed '+kind)
 a.out.write_text(json.dumps(results,indent=2)+'\n');print('VERIFIER MUTATIONS PASS',len(results))
if __name__=='__main__':main()
