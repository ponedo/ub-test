#!/usr/bin/env python3
"""Read verified aggregate ledgers; never executes or modifies simulations."""
import argparse,csv,json,pathlib
NUMERIC=['tokens','layer','assignments','layer_latency_ms','replicas','max_npu_load','weight_bytes','weight_duration_ms','remote_wqes','ta_count','weight_wqes','weight_tas','simulator_events','host_wall_seconds','host_cpu_seconds','peak_rss_kib','dispatch_span_ms','compute_span_ms','combine_span_ms','max_npu_compute_ms','planning_ms','reroute_ms']
FAN=['physical_instances_including_main','new_replicas_excluding_main','main_outgoing_copies','main_outgoing_tasks','forwarded_tasks','direct_fallback_tasks','relay_tree_tasks','weight_tasks','weight_wqes','weight_tas','weight_bytes','remote_weight_bytes','relay_physical_count','eligible_experts','actual_relay_experts','relay_node_count']
def read(p): return json.loads(p.read_text())
def planning_times_ms(timeline):
 values=[timeline[k] for k in ['layer_start','planning_end','reroute_end']]
 assert values[0]<=values[1]<=values[2], 'Non-monotone planning/reroute events'
 return {'planning_ms':(values[1]-values[0])/1e9,'reroute_ms':(values[2]-values[1])/1e9}
def main():
 p=argparse.ArgumentParser();p.add_argument('--private-root',type=pathlib.Path,required=True);p.add_argument('--historical',type=pathlib.Path,required=True);p.add_argument('--historical-fanout',type=pathlib.Path);p.add_argument('--skew',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 rows=[]; inventory=[]
 stages=['preparation_host','preflight_host','simulator_host','postflight_host']
 for r in csv.DictReader((a.historical/'performance.csv').open()):
  if r['status']!='PASS' or r['validation']!='PASS': continue
  inventory.append({'tokens':256,'layer':int(r['layer']),'strategy':r['strategy'],'status':'PASS','provenance':'historical-reused-N256'})
  row={k:float(r[k]) for k in NUMERIC if r.get(k)!='' and k in r};row.update(strategy=r['strategy'],status='PASS',validation='PASS',provenance='historical-reused-N256',routing_sha256=r['routing_sha256']);rows.append(row)
 if a.historical_fanout:
  proofs={(r['layer'],r['strategy']):r for r in read(a.historical/'verification-proofs.json')}
  hist={(r['layer'],r['strategy']):r for r in rows}
  rebuilt=read(a.historical_fanout);assert len(rebuilt)==9
  seen_h=set()
  for r in rebuilt:
   key=(r['layer'],r['strategy']);assert key not in seen_h;seen_h.add(key)
   row=hist[key];proof=proofs[key];f=r['fanout'];assert r['tokens']==256 and f['status']=='PASS' and proof['validation']['status']=='PASS'
   assert r['npu_load']==proof['per_npu_load'] and max(r['npu_load'])==row['max_npu_load']
   assert row['replicas']==f['totals']['new_replicas_excluding_main']
   for k in ['weight_bytes','weight_wqes','weight_tas']:assert row[k]==f['totals'][k],(key,k)
   for k in FAN:row['fanout_'+k]=f['totals'][k]
   row['max_expert_replicas_excluding_main']=max(v['new_replicas_excluding_main'] for v in f['experts'])
   row['max_expert_main_outgoing_copies']=max(v['main_outgoing_copies'] for v in f['experts'])
   row['fanout_provenance']='reconstructed-plan-graph-only; historical-latency-not-rerun'
 for path in sorted(a.private_root.glob('tokens-*/runs.json')):
  if int(path.parent.name.split('-')[-1]) not in [512,1024,2048]:continue
  ledger=read(path)
  size_status=read(path.parent/'status.json') if (path.parent/'status.json').exists() else {}
  failure=size_status.get('failure_resource')
  if failure:
   failure_path=pathlib.Path(failure).resolve()
   if not failure_path.is_relative_to(a.private_root.resolve()):raise ValueError('Failure resource escaped private aggregate root')
   allowed={'preparation-host':'preparation_host','preflight-host':'preflight_host','simulator-host':'simulator_host','postflight-host':'postflight_host'}
   if failure_path.name!='resource.json' or failure_path.parent.name not in allowed:raise ValueError('Unexpected failure resource shape')
   stage=allowed[failure_path.parent.name];resource=read(failure_path)
   # Associate by the explicit case directories, never by list order.
   matches=[r for r in ledger if f"layer-{r['layer']}" in failure_path.parts and r['strategy'] in failure_path.parts]
   if len(matches)!=1:raise ValueError('Failure resource has no unique case')
   matches[0][stage]={'status':resource.get('status','UNKNOWN'),'guard':resource.get('guard')}
   matches[0]['status']=size_status.get('status','STOPPED')
  for r in ledger:
   item={k:r[k] for k in ['tokens','layer','strategy','status']}; item['provenance']='new-execution'
   item['stages']={k.removesuffix('_host'):r.get(k,{}).get('status','NOT_RECORDED') for k in stages}
   # Guard categories only; raw error strings may contain private filenames.
   item['guard_categories']={}
   for k in stages:
    guard=r.get(k,{}).get('guard')
    if guard:
     raw=str(guard).lower()
     category=next((c for c in ['memory','rss','wall','timeout','disk','thread','payload','capacity'] if c in raw),'other_guard')
     item['guard_categories'][k.removesuffix('_host')]=category
   item['performance_eligible']=(r.get('status')=='PASS' and r.get('validation',{}).get('status')=='PASS' and all(r.get(k,{}).get('status')=='PASS' for k in stages))
   inventory.append(item)
   if r.get('status')!='PASS' or r.get('validation',{}).get('status')!='PASS' or any(r.get(k,{}).get('status')!='PASS' for k in stages): continue
   s=r['summary'];h=r['simulator_host'];t=r['times'];f=r['fanout'];assert f['status']=='PASS'
   row={k:r[k] for k in ['tokens','layer','strategy','status','routing_sha256','mapping_sha256']};row.update(validation='PASS',provenance='new-execution',fanout_provenance='executed-graph-validated',layer_latency_ms=s['layer_latency_ps']/1e9,weight_duration_ms=s['weight_target_duration_ps']/1e9)
   row.update(planning_times_ms(r['online_summary']['timeline']))
   for k in ['assignments','replicas','max_npu_load','weight_bytes','simulator_events']:row[k]=s[k]
   for k,v in [('remote_wqes','remote_WQEs'),('ta_count','TA_count'),('weight_wqes','weight_WQEs'),('weight_tas','weight_TAs')]:row[k]=s[v]
   row.update(host_wall_seconds=h['wall_seconds'],host_cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'])
   for k in ['dispatch','compute','combine']:row[k+'_span_ms']=t[k+'_span_ps']/1e9
   row['max_npu_compute_ms']=max((v['end_ps']-v['start_ps'] for v in s['compute_intervals']),default=0)/1e9
   for k in FAN:row['fanout_'+k]=f['totals'][k]
   row['max_expert_replicas_excluding_main']=max(v['new_replicas_excluding_main'] for v in f['experts']);row['max_expert_main_outgoing_copies']=max(v['main_outgoing_copies'] for v in f['experts'])
   for k in ['weight_bytes','weight_wqes','weight_tas']:assert row[k]==row['fanout_'+k],(r['tokens'],r['layer'],r['strategy'],k)
   rows.append(row)
 skew=read(a.skew)['measured_skew'];sk={(x['tokens'],x['layer']):x for x in skew};refs={(int(r['tokens']),int(r['layer'])):r for r in rows if r['strategy']=='no-balancing'}
 seen=set()
 for r in rows:
  key=(int(r['tokens']),int(r['layer']));r['tokens'],r['layer']=key
  assert (*key,r['strategy']) not in seen;seen.add((*key,r['strategy']))
  for k in ['expert_max_mean','npu_max_mean']:r['input_'+k]=sk[key][k]
  ref=refs.get(key)
  if ref:
   assert ref['routing_sha256']==r['routing_sha256'];r['speedup']=ref['layer_latency_ms']/r['layer_latency_ms']
 rows.sort(key=lambda r:(r['tokens'],r['layer'],['no-balancing','direct','chunk-streaming'].index(r['strategy'])))
 fields=list(dict.fromkeys(k for r in rows for k in r));out=a.out/'performance.csv'
 with out.open('w') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
 (a.out/'aggregate.json').write_text(json.dumps(rows,indent=2)+'\n');(a.out/'input-skew.json').write_text(json.dumps(skew,indent=2)+'\n')
 status=read(a.private_root/'scaling-status.json') if (a.private_root/'scaling-status.json').exists() else {'status':'UNKNOWN'}
 # Whitelist status; never copy private paths or commands into published outputs.
 driver_status=status.get('status','UNKNOWN')
 status={k:status[k] for k in ['status','completed_sizes','current_size'] if k in status};status['scope_tokens']=[256,512,1024,2048];status['planned_new_cases']=27;status['verified_rows']=len(rows);status['new_verified_rows']=sum(r['provenance']=='new-execution' for r in rows)
 expected={(n,l,s) for n in [512,1024,2048] for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming']}
 actual={(r['tokens'],r['layer'],r['strategy']) for r in rows if r['provenance']=='new-execution'}
 boundary_path=a.private_root/'tokens-2048/scope-boundary.json'
 boundary=read(boundary_path) if boundary_path.exists() else {}
 boundary_ok=(boundary.get('status')=='COMPLETE' and boundary.get('reason')=='USER_SCOPE_LIMIT_REACHED' and boundary.get('stop_after_tokens')==2048 and boundary.get('completed_cases')==9)
 status['intentional_scope_boundary_verified']=boundary_ok
 if boundary_ok:status['boundary_reason']='USER_SCOPE_LIMIT_REACHED'
 status['scope_status']='PASS' if actual==expected and boundary_ok else ('STOPPED' if driver_status=='STOPPED' else 'RUNNING')
 status['scope_verified_complete_sizes']=[n for n in [512,1024,2048] if all((n,l,s) in actual for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming'])]
 present={(x['tokens'],x['layer'],x['strategy']) for x in inventory}
 for n in [512,1024,2048]:
  for layer in [0,37,52]:
   for strategy in ['no-balancing','direct','chunk-streaming']:
    if (n,layer,strategy) not in present:inventory.append({'tokens':n,'layer':layer,'strategy':strategy,'status':'NOT_YET_STARTED','provenance':'new-execution'})
 inventory.sort(key=lambda x:(x['tokens'],x['layer'],['no-balancing','direct','chunk-streaming'].index(x['strategy'])))
 (a.out/'case-status.json').write_text(json.dumps(inventory,indent=2)+'\n')
 (a.out/'coverage.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))
if __name__=='__main__':main()
