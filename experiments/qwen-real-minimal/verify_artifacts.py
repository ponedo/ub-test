#!/usr/bin/env python3
"""Independent finalized private archive audit; emit hashes and counts only."""
import argparse,hashlib,io,json,tarfile
from pathlib import Path

def sha(x):return hashlib.sha256(x).hexdigest()
def stable(x):
 if isinstance(x,dict):return {k:stable(v) for k,v in x.items() if k!='cpu_wall_ns'}
 if isinstance(x,list):return [stable(v) for v in x]
 return x

def main():
 p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();records=json.loads((a.private/'runs.json').read_text());rows=[];plans={}
 terminal=json.loads((a.private/'status.json').read_text())
 expected={(layer,strategy) for layer in [0,37,52] for strategy in ['no-balancing','direct','chunk-streaming']}
 identities=[(r['layer'],r['strategy']) for r in records]
 if terminal.get('status')!='PASS' or len(records)!=9 or set(identities)!=expected or any(r.get('status')!='PASS' for r in records):raise ValueError('final audit requires terminal PASS and exactly nine unique completed cases')
 for rec in records:
  if rec['status']!='PASS':continue
  layer=rec['layer'];strategy=rec['strategy'];root=a.private/f'layer-{layer}'/strategy/'prepared-evidence'
  manifest=json.loads((root/'manifest.json').read_text());blob=b''.join((root/x['name']).read_bytes() for x in manifest['parts'])
  if sha(blob)!=manifest['archive_sha256']:raise ValueError('archive hash changed')
  with tarfile.open(fileobj=io.BytesIO(blob),mode='r:xz') as archive:
   def read(name):
    b=archive.extractfile(name).read()
    if sha(b)!=manifest['files'][name]['sha256']:raise ValueError('archived file changed')
    return json.loads(b)
   config=read('run/config.json');plan=read('run/plan.json');online=read('run/online-summary.json');validation=read('run/validation.json')
  source=(a.private/'routing'/f'layer_{layer}.json').read_bytes()
  if sha(source)!=rec['routing_sha256']:raise ValueError('source hash drift')
  tokens=json.loads(source)['tokens'];expected=[dict(source=i%64,experts=x['experts']) for i,x in enumerate(tokens)]
  if config['planner_input']['mapping']!=expected or len(expected)!=256:raise ValueError('trace adapted differently')
  if online['assignments']!=2048 or online['completed_tokens']!=256 or validation['status']!='PASS':raise ValueError('incomplete execution')
  if online['sender_completions']!=online['remote_WQEs'] or online['target_segments']!=online['TA_count']:raise ValueError('completion conservation')
  decision=sha(json.dumps(stable(plan),sort_keys=True,separators=(',',':')).encode())
  if strategy=='direct':plans[layer]=decision
  if strategy=='chunk-streaming' and decision!=plans[layer]:raise ValueError('Direct/Chunk Planner differs')
  rows.append(dict(layer=layer,strategy=strategy,status='PASS',source_routing_sha256=sha(source),stable_plan_sha256=decision,archive_sha256=sha(blob),assignments=2048,completed_tokens=256))
 a.out.write_text(json.dumps(dict(status='PASS',checks=['archive and selected file hashes','all256 input source/topk positions','source token_id%64','all2048 assignments and256 completed tokens','exact sender/target completion count','Direct/Chunk full Planner equality excluding cpu_wall_ns'],cases=rows),indent=2)+'\n');print('PASS finalized archives',len(rows))
if __name__=='__main__':main()
