#!/usr/bin/env python3
import argparse,hashlib,json,shutil,os
from pathlib import Path
from guard import run
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
p=argparse.ArgumentParser();p.add_argument('--label',default='instrumented');p.add_argument('--before',default='/workspace/prefill-capacity-raw/original-executor');p.add_argument('--after',default='/workspace/ns-3-ub/build/scratch/ns3.44-multi-npu-relay');a=p.parse_args();result=[]
for mode in ['no-balancing','chunk-streaming']:
 source=REPO/'experiments/multi-npu-relay/evidence/fixed64'/mode;dirs={}
 for tag,binary in [('before',a.before),('after',a.after)]:
  out=Path(os.environ.get('CAPACITY_RAW','/workspace/prefill-capacity-raw'))/'parity'/a.label/mode/tag;out.mkdir(parents=True,exist_ok=True);dirs[tag]=out
  cmd=[binary,'--input='+str(source/'input.txt'),'--out='+str(out)]
  if tag=='after':cmd+=['--capacityMetrics='+str(out/'simulator-metrics.json')]
  status=run(cmd,out.parent/(tag+'-host'),60,case=out)
  if status['status']!='PASS':raise SystemExit('small parity run failed')
 before={str(p.relative_to(dirs['before'])):hashlib.sha256(p.read_bytes()).hexdigest() for p in dirs['before'].rglob('*') if p.is_file()};after={str(p.relative_to(dirs['after'])):hashlib.sha256(p.read_bytes()).hexdigest() for p in dirs['after'].rglob('*') if p.is_file() and p.name!='simulator-metrics.json'}
 assert before==after,[(k,before.get(k),after.get(k)) for k in set(before)|set(after) if before.get(k)!=after.get(k)]
 result.append(dict(mode=mode,all_generated_files_byte_identical=True,files=before,metrics=json.loads((dirs['after']/'simulator-metrics.json').read_text())))
(ROOT/'evidence'/('parity-'+a.label+'.json')).write_text(json.dumps(result,indent=2)+'\n');print('byte-exact small control/relay parity PASS')
