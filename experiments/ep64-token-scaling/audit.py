#!/usr/bin/env python3
"""Independent cross-strategy/prefix/measurement accounting checks on saved evidence."""
import argparse,csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);a=p.parse_args();runs=json.loads((a.raw/'runs.json').read_text());records=[];previous=[]
for point in sorted(a.raw.glob('tokens-*'),key=lambda p:int(p.name.split('-')[1])):
 if not (point/'routing.csv').exists():continue
 tokens=int(point.name.split('-')[1]);rows=list(csv.DictReader((point/'routing.csv').open()));assert len(rows)==tokens*8
 assert rows[:len(previous)]==previous;previous=rows
 groups=defaultdict(list);counts=Counter()
 for r in rows:
  t,s,k,e=[int(r[x]) for x in ['token','source_npu','topk_index','expert']];assert 0<=t<tokens and s==t%64 and 0<=e<128;groups[t].append((k,e));counts[e]+=1
 assert len(groups)==tokens and all(sorted(k for k,e in v)==list(range(8)) and len({e for k,e in v})==8 for v in groups.values())
 load=json.loads((point/'expert-load.json').read_text());assert load['loads']==[counts[e] for e in range(128)]
 h=hashlib.sha256((point/'routing.csv').read_bytes()).hexdigest();arms=[r for r in runs if r['tokens']==tokens];plans=[]
 for r in arms:
  assert r['routing_sha256']==h and r['assignments']==tokens*8
  if r.get('status')!='PASS':continue
  s,m,v=r['summary'],r['metrics'],r['validation'];assert sum(s['per_npu_load'])==tokens*8 and max(s['per_npu_load'])==s['max_npu_load']
  assert v['status']=='PASS' and v['checked_sender_completions']==m['sender_completions']==m['remote_WQEs'] and v['checked_TAs']==m['TA_count']
  assert s['timeline']['layer_end']-s['timeline']['layer_start']==s['layer_latency_ps']
  assert s['timeline']['dispatch_gate']==max(s['timeline']['reroute_end'],s['timeline']['weights_end'])
  if r['strategy']!='no-balancing':plans.append((r['input_hashes']['plan.json'],r['input_hashes']['assignments.csv'],s['per_npu_load'],s['replicas'],s['weight_bytes']))
 assert not plans or all(p==plans[0] for p in plans)
 records.append({'tokens':tokens,'routing_rows':len(rows),'prefix_equal':True,'unique_topk':True,'passed_arms':sum(r.get('status')=='PASS' for r in arms),'status':'PASS'})
result={'status':'PASS','points':records,'passed_simulations':sum(r.get('status')=='PASS' for r in runs),'failed_simulations':sum(r.get('status')=='FAIL' for r in runs)}
(a.raw/'analysis/cross-strategy-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
