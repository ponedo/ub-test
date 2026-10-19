#!/usr/bin/env python3
"""Negative tests of the independent verifier, using copies of owned small evidence."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
X=Path(__file__).resolve().parent
cases=['payload','early-group','missing-feedback','wrong-wire-size','early-chunk']
rows=[]
for kind in cases:
 target=a.out/kind;target.mkdir()
 for f in a.source.iterdir():
  if f.suffix in ('.csv','.bin') or f.name=='summary.json':shutil.copyfile(f,target/f.name)
 if kind=='payload':
  f=next(target.glob('payload-*.bin'));b=bytearray(f.read_bytes());b[-1]^=1;f.write_bytes(b)
 else:
  f=target/('wire.csv' if kind=='wrong-wire-size' else 'events.csv')
  with f.open() as stream:r=list(csv.DictReader(stream));fields=list(r[0])
  if kind=='missing-feedback':r.pop(next(i for i,x in enumerate(r) if x['event']=='feedback_received'))
  elif kind=='wrong-wire-size':x=next(x for x in r if x['packet_class']=='multicast_data');x['bytes']=str(int(x['bytes'])-1)
  else:x=next(x for x in r if x['event']==('group_complete' if kind=='early-group' else 'chunk_ready'));x['time_ps']='0'
  with f.open('w') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(r)
 result=subprocess.run([sys.executable,X/'verify-multi.py',target,'--scenario','basic','--bytes','16384'],capture_output=True,text=True)
 assert result.returncode!=0 and 'AssertionError' in result.stderr,kind
 rows.append({'mutation':kind,'status':'DETECTED','returncode':result.returncode})
(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print('5 verifier mutations detected')
