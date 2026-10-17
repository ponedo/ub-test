#!/usr/bin/env python3
"""Assemble initial and explicitly authorized resumed runs without altering either."""
import argparse,json,os,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--initial',type=Path,required=True);p.add_argument('--resumed',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False)
def tree(s,d):shutil.copytree(s,d,copy_function=os.link)
for f in a.initial.iterdir():
 if f.is_file():shutil.copy2(f,out/f.name)
 elif f.name=='analysis':continue
 elif f.name.startswith('tokens-') and (a.resumed/f.name).exists():continue
 else:tree(f,out/f.name)
for f in a.resumed.iterdir():
 if f.is_dir() and f.name.startswith('tokens-'):tree(f,out/f.name)
attempts=out/'attempts';attempts.mkdir()
for name,root in [('initial',a.initial),('resumed',a.resumed)]:
 target=attempts/name;target.mkdir()
 for f in root.iterdir():
  if f.is_file():shutil.copy2(f,target/f.name)
 if name=='initial':
  for f in root.glob('tokens-*'):
   if (a.resumed/f.name).exists():tree(f,target/f.name)
first=json.loads((a.initial/'runs.json').read_text());second=json.loads((a.resumed/'runs.json').read_text());prior={(r['tokens'],r['strategy']):r for r in first};rows=[r for r in first if (r['tokens'],r['strategy']) not in {(x['tokens'],x['strategy']) for x in second}]+second
for r in second:
 old=prior.get((r['tokens'],r['strategy']))
 if old:assert old['input_hashes']==r['input_hashes'] and old['routing_sha256']==r['routing_sha256']
rows.sort(key=lambda r:(r['tokens'],['no-balancing','direct','chunk-streaming'].index(r['strategy'])))
status=json.loads((a.resumed/'status.json').read_text());status['completed_token_points']=sorted(set(status['completed_token_points']+json.loads((a.initial/'status.json').read_text())['completed_token_points']));status['attempts']=['attempts/initial','attempts/resumed'];status['previous_guard_failure_preserved']=True
if status['status']=='PASS':
 assert len(rows)==21 and len({(r['tokens'],r['strategy']) for r in rows})==21 and all(r.get('status')=='PASS' for r in rows)
 assert status['completed_token_points']==[256,1024,2048,4096,6250,8192,12500]
(out/'scan-console.txt').write_text('=== INITIAL ATTEMPT (preserved) ===\n'+(a.initial/'scan-console.txt').read_text()+'\n=== AUTHORIZED RESUMED ATTEMPT ===\n'+(a.resumed/'scan-console.txt').read_text())
(out/'runs.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'status.json').write_text(json.dumps(status,indent=2)+'\n')
print(json.dumps({'merged_rows':len(rows),'completed':status['completed_token_points'],'status':status['status']}))
