#!/usr/bin/env python3
"""Private real-routing input adapter. Never publishes token data."""
import argparse,csv,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
H=Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def unique_json(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate JSON field')
  result[key]=value
 return result

def load_routing(path,npus=64,tokens=256):
 data=json.loads(Path(path).read_text(),object_pairs_hook=unique_json)
 if set(data)!={'serialized_layer','tokens','source_manifest_sha256'}:raise ValueError('unsupported routing fields')
 rows=data['tokens']
 if type(tokens)!=int or not 1<=tokens<=4275 or len(rows)!=tokens:raise ValueError('requested source token count mismatch')
 seen=set();mapping=[]
 for t,row in enumerate(rows):
  if set(row)!={'request_id','token_ordinal','experts'}:raise ValueError('unsupported token fields')
  if not isinstance(row.get('request_id'),str) or not row['request_id'] or type(row.get('token_ordinal')) is not int or row['token_ordinal']<0:raise ValueError('invalid request/token identity')
  identity=(row['request_id'],row['token_ordinal']);experts=row['experts']
  if identity in seen:raise ValueError('duplicate source token')
  seen.add(identity)
  if len(experts)!=8 or len(set(experts))!=8 or any(type(e)!=int or not 0<=e<128 for e in experts):raise ValueError('invalid top-k')
  mapping.append(dict(source=t%npus,experts=experts))
 return data,mapping

def verify_source(data,layer,manifest,counts,out):
 audit=module('source_audit',H/'source_audit.py')
 summary,rows=audit.audit(manifest,counts,out)
 if type(data['serialized_layer']) is not int or data['serialized_layer']!=layer or type(layer)!=int or not 0<=layer<94:raise ValueError('requested serialized layer mismatch')
 requests=json.loads(Path(manifest).read_text())['requests'];identity=[]
 for b in summary['batch_boundaries']:
  identity.extend((requests[b['manifest_request_index']]['request_id'],i) for i in range(b['selected_tokens']))
 expected=[dict(request_id=r,token_ordinal=i,experts=es) for (r,i),es in zip(identity,rows[layer])]
 if len(data['tokens'])!=256:
  # Independently rebuild requested prefix directly from audited raw records.
  expected=[];remaining=len(data['tokens'])
  for req in requests:
   path=Path(req['file_path']);path=path if path.is_absolute() else Path(manifest).parent/path
   original=json.loads(path.read_text(),object_pairs_hook=audit.unique)[0][str(layer)]
   take=min(remaining,len(original));expected.extend(dict(request_id=req['request_id'],token_ordinal=i,experts=original[i]) for i in range(take));remaining-=take
   if not remaining:break
  if remaining:raise ValueError('insufficient real source tokens')
 if data['tokens']!=expected:raise ValueError('routing differs from raw source in layer/order/request/expert')
 if data['source_manifest_sha256']!=hashlib.sha256(Path(manifest).read_bytes()).hexdigest():raise ValueError('manifest hash mismatch')
 return summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--routing',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--graph-tool',type=Path,required=True);ap.add_argument('--tokens',type=int,default=256);ap.add_argument('--layer',type=int,required=True);ap.add_argument('--source-manifest',type=Path,required=True);ap.add_argument('--frozen-counts',type=Path,required=True);ap.add_argument('--budget-only',action='store_true');ap.add_argument('--strategy',choices=['no-balancing','direct','chunk-streaming'],required=True);a=ap.parse_args()
 if not __debug__:raise RuntimeError('validation requires Python assertions enabled')
 a.out.mkdir(parents=True,exist_ok=False);os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve())
 data,mapping=load_routing(a.routing,tokens=a.tokens)
 verify_source(data,a.layer,a.source_manifest,a.frozen_counts,a.out/'source-audit')
 b=module('direct_adapter',H.parent/'direct-weight-forward/adapter.py');r=module('relay_adapter',H.parent/'multi-npu-relay/adapter.py')
 fixed=json.loads((H.parent/'qwen-prefill-token-scaling/fixed-config.json').read_text())
 c=b.normalize(dict(schema_version=1,npus=64,experts=128,top_k=8,main_placement=fixed['main_placement'],slots=fixed['slots'],mapping=mapping,beta='1.01',min_replica_quota=1024))
 b.validate(c);start=time.perf_counter();cpu=time.process_time();plan=b.baseline(c) if a.strategy=='no-balancing' else b.solve(c)
 timing=dict(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
 if a.strategy!='no-balancing':b.check(c,plan)
 params=dict(fixed['application_parameters'],model_dim=4096,ff_dim=1536,dtype_bytes=2,weight_dtype_bytes=1)
 p=dict(fixed['relay_parameters']);replicas=len(plan['weight_dependencies']);weight=3*4096*1536
 cap=module('cap',H.parent/'multi-npu-relay/capacity.py')
 strategy='direct' if a.strategy=='no-balancing' else a.strategy
 count=cap.weight_task_count(plan['physical'],strategy,weight,p,2*4096*1536)
 assignments=len(mapping)*8
 budget=dict(assignments=assignments,replicas=replicas,weight_bytes_per_expert=weight,weight_wqes=count,weight_tas=replicas*weight//1024,logical_payload_bytes=assignments*8192*2+replicas*weight,weight_buffer_lower_bound_bytes=2*replicas*weight,planned_tasks=2*assignments+count,activation_dtype='BF16',weight_dtype='idealized FP8 without scale metadata')
 (a.out/'capacity.json').write_text(json.dumps(budget,indent=2)+'\n')
 if budget['logical_payload_bytes']>8*1024**3 or count>1000000 or 2*assignments+count>=2**31 or budget['weight_tas']+2*assignments*8>=2**32:raise ValueError('capacity bounds')
 if a.budget_only:
  print(json.dumps(budget),flush=True);return
 b.solve=lambda _:plan;b.baseline=lambda _:plan
 b.emit(c,params,'no-balancing' if a.strategy=='no-balancing' else 'ultraep',a.out/'direct-input')
 r.emit(a.out/'direct-input',p,strategy,a.out/'run')
 source=dict(serialized_layer=data['serialized_layer'],routing_sha256=hashlib.sha256(a.routing.read_bytes()).hexdigest(),source_npu='token_id % 64; simulator assumption',tokens=len(mapping),assignments=assignments,planner_time=timing,capacity=budget)
 (a.out/'preparation-summary.json').write_text(json.dumps(source,indent=2)+'\n')
 print(json.dumps(source),flush=True)
if __name__=='__main__':main()
