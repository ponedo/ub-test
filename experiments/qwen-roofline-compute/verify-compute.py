import argparse,csv,json,collections
from pathlib import Path
from oracle import estimate,legacy
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-model',choices=['legacy','roofline'],required=True);p.add_argument('--compute-tflops',type=int,default=100);p.add_argument('--hbm-bandwidth-gbps',type=int,default=2692);a=p.parse_args();r=a.root
c=json.loads((r/'config.json').read_text());s=json.loads((r/'online-summary.json').read_text());model=json.loads((r/'compute-model.json').read_text());plan=json.loads((r/'plan.json').read_text());params=c['runtime'];rows=list(csv.DictReader((r/'expert-compute.csv').open()));assert len(rows)==len(plan['physical'])
assert model['model']==a.expected_model and model['compute_tflops']==a.compute_tflops and model['hbm_bandwidth_gbps']==a.hbm_bandwidth_gbps
assert model['roofline_launch_ns']==0 and model['activation_policy']=='separate-three-gemm-fused-silu-mul-no-cache-v1'
assert len(s['compute_intervals'])==len({x['node'] for x in s['compute_intervals']})
counts=collections.Counter()
with (r/'assignments.csv').open() as f:
 for x in csv.DictReader(f):counts[int(x['physical'])]+=1
by_node=collections.defaultdict(list)
for row,ph in zip(rows,plan['physical']):
 assert int(row['physical'])==ph['id'] and int(row['node'])==ph['rank'] and int(row['expert'])==ph['expert']
 m=int(row['tokens']);assert m==ph['quota']==counts[ph['id']]
 e=estimate(m,params['model_dim'],params['ff_dim'],params['dtype_bytes'],params.get('weight_dtype_bytes',params['dtype_bytes']),model['compute_tflops'],model['hbm_bandwidth_gbps'],params['weight_bytes'])
 for key,value in e.items():
  if key!='roofline_ps':assert int(row[key])==value,(key,row,value)
 want=0 if not m else legacy(m,params) if model['model']=='legacy' else e['roofline_ps']
 assert row['bottleneck']==('legacy' if model['model']=='legacy' else 'idle' if not m else 'compute' if e['compute_ps']>=e['memory_ps'] else 'memory')
 start,end=int(row['start_ps']),int(row['end_ps']);assert int(row['duration_ps'])==end-start==want
 if not m:assert start==end==int(row['total_hbm_bytes'])==0
 else:by_node[ph['rank']].append((start,end))
for node,intervals in by_node.items():
 expected=next(x for x in s['compute_intervals'] if x['node']==node)
 assert intervals[0][0]==expected['start_ps'] and intervals[-1][1]==expected['end_ps']
 assert all(x[1]==y[0] for x,y in zip(intervals,intervals[1:])), 'NPU serialization'
 assert sum(b-a for a,b in intervals)==expected['end_ps']-expected['start_ps']
assert set(by_node)=={x['node'] for x in s['compute_intervals']}
(r/'compute-validation.json').write_text(json.dumps(dict(status='PASS',model=model['model'],physical_experts=len(rows),active_experts=sum(int(x['tokens'])>0 for x in rows),serialized_npus=len(by_node),independent_integer_oracle=True),indent=2)+'\n')
print('PASS independent compute oracle, actual token quotas, per-NPU serialization')
