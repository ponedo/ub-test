#!/usr/bin/env python3
"""Completed-scope attribution only; never divide unequal-progress partial runs."""
import argparse,csv,json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw'
p=argparse.ArgumentParser();p.add_argument('--online-scan-name');p.add_argument('--online-index-name');a=p.parse_args()
def readcsv(path):
 with path.open() as f:return list(csv.DictReader(f))
def writecsv(name,rows):
 if rows:
  with (H/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!='verification_wall_ns'}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
py=readcsv(H/'python-timings.csv');read=readcsv(H/'cpp-read-timings.csv');contributions=[]
for stage,label in [('preparation','Python preparation: dependency construction'),('preflight','Python independent preflight: dependency validation')]:
 s=next(r for r in py if r['stage']==stage and r['mode']=='scan');i=next(r for r in py if r['stage']==stage and r['mode']=='indexed');assert s['status']==i['status']=='PASS';assert s['input_sha256']==i['input_sha256']
 contributions.append(dict(name=label,scan_cpu_seconds=float(s['dependency_cpu_seconds']),index_cpu_seconds=float(i['dependency_cpu_seconds']),complete_scope=True,index_build_included=True,scope='Dependency span; complete Python stage process/wall costs reported separately',scan_full_stage_process_cpu_seconds=float(s['cpu_seconds']),index_full_stage_process_cpu_seconds=float(i['cpu_seconds']),scan_full_stage_wall_seconds=float(s['wall_seconds']),index_full_stage_wall_seconds=float(i['wall_seconds'])))
s=next(r for r in read if r['mode']=='scan');i=next(r for r in read if r['mode']=='index');assert s['complete']==i['complete']=='True'
contributions.append(dict(name='C++ Read: full parsing/setup',scan_cpu_seconds=float(s['read_cpu_seconds']),index_cpu_seconds=float(i['read_cpu_seconds']),complete_scope=True,index_build_included=True,scan_index_build_cpu_seconds=float(s['index_build_cpu_seconds']),index_index_build_cpu_seconds=float(i['index_build_cpu_seconds']),scan_dependency_cpu_seconds=float(s['dependency_cpu_seconds']),index_dependency_cpu_seconds=float(i['dependency_cpu_seconds']),scope='Full Read inclusive CPU includes index construction and local index destruction; parsing/setup is included. Graph export is excluded.'))
runtime=json.loads((H/'runtime-results.json').read_text())['runs'];selected={};warnings=[]
for mode,explicit in [('scan',a.online_scan_name),('index',a.online_index_name)]:
 candidates=[r for r in runtime if r['dependency_mode']=='index' and r['online_mode']==mode and r['timed'] and not r['sampled'] and ((r['complete'] and r.get('profile_complete') and r['status']=='PASS') or (mode=='scan' and r['guard']=='wall_guard'))]
 if explicit:candidates=[r for r in candidates if r['name']==explicit]
 if len(candidates)==1:selected[mode]=candidates[0]
 elif not candidates:warnings.append('No unique completed timed index/'+mode+' run yet; partial scopes are not compared.')
 else:raise RuntimeError('Multiple completed candidates: specify --online-'+mode+'-name')
self_rows=[]
if len(selected)==2:
 scanroot=R/'runtime'/selected['scan']['name'];indexroot=R/'runtime'/selected['index']['name']
 full_pair=all(r['complete'] for r in selected.values())
 if full_pair:
  for name in ['online-summary.json','validation.json','simulator-metrics.json']:
   assert stable(json.loads((scanroot/'run'/name).read_text()))==stable(json.loads((indexroot/'run'/name).read_text())),name
 snapshots={m:json.loads((R/'runtime'/r['name']/'timing.json').read_text()) for m,r in selected.items()}
 reference=snapshots['index'];assert reference['complete'] and reference['terminal'] and not reference['failed']
 for m,d in snapshots.items():
  assert d['terminal'] and not d['failed']
  assert d['progress']==reference['progress'] and d['simulator_events']==reference['simulator_events'] and d['simulated_time_ps']==reference['simulated_time_ps']
  for phase in ['Simulator::Run','InitAudit.online_index_build','Audit.group_scan','Audit.weight_scan']:
   v=d['phases'][phase];assert v['active_calls']==0 and v['completed_calls']==v['calls'] and v['calls']>0
  if not d['complete']:assert d['active_phase']=='FinalAudit' and selected[m]['guard']=='wall_guard'
 if not full_pair:warnings.append('Online scan whole run is INCOMPLETE: stopped in FinalAudit. Only verified completed online scopes are compared; no full-run speedup or scan latency claim.')
 components={};counter_evidence={}
 for root in [scanroot,indexroot]:
  provenance=json.loads((root/'provenance.json').read_text());assert provenance['input_sha256']==py[0]['input_sha256']
 for mode,row in selected.items():
  d=snapshots[mode]
  ph=d['phases']
  c=d['counters'];counter_evidence[mode]={k:c[k] for k in ['audit_group_events','audit_weight_events','audit_group_scan_candidates','audit_group_scan_matches','audit_weight_scan_candidates','audit_weight_scan_matches','online_index_build_candidates']}
  assert ph['Audit.group_scan']['completed_calls']==c['audit_group_events']
  assert ph['Audit.weight_scan']['completed_calls']==c['audit_weight_events']
  components[mode]={k:ph[k]['inclusive_cpu_ns']/1e9 for k in ['Audit.group_scan','Audit.weight_scan','InitAudit.online_index_build']}
  for phase,v in ph.items():self_rows.append(dict(run=row['name'],online_mode=mode,phase=phase,complete=d['complete'],self_cpu_seconds=v['self_cpu_ns']/1e9,inclusive_cpu_seconds=v['inclusive_cpu_ns']/1e9,calls=v['calls'],completed_calls=v['completed_calls'],active_calls=v['active_calls']))
  # Self scopes partition program CPU; inclusive scopes must never be summed.
  assert abs(sum(v['self_cpu_ns'] for v in ph.values())-ph['program']['inclusive_cpu_ns'])<=1000
 for k in ['audit_group_events','audit_weight_events','audit_group_scan_matches','audit_weight_scan_matches']:assert counter_evidence['scan'][k]==counter_evidence['index'][k]
 contributions.append(dict(counter_evidence=counter_evidence,name='C++ online group/weight audit + index build',scan_cpu_seconds=sum(components['scan'].values()),index_cpu_seconds=sum(components['index'].values()),complete_scope=True,index_build_included=True,scope='Disjoint group/weight event scopes plus one InitAudit index-build scope. Persistent-index destruction remains in Layer destructor, separately reported.',scan_components_cpu_seconds=components['scan'],index_components_cpu_seconds=components['index'],scan_run=selected['scan']['name'],index_run=selected['index']['name'],completed_full_output_parity=full_pair,scan_process_complete=selected['scan']['complete'],index_process_complete=selected['index']['complete'],targeted_scope_completion_verified=True,common_progress=reference['progress'],common_simulator_events=selected['index']['simulator_events'],common_completed_tokens=selected['index']['completed_tokens'],common_layer_latency_ps=selected['index']['layer_latency_ps']))
for r in contributions:r['observed_cpu_ratio']=r['scan_cpu_seconds']/r['index_cpu_seconds']
report=dict(status='PASS' if len(contributions)==4 else 'PENDING_ONLINE_PAIR',contributions=contributions,warnings=warnings,limitations=['One observation per treatment, no confidence intervals.','Instrumented CPU includes timer/counter overhead; snapshot serialization is excluded and separately recorded.','Python, standalone Read and simulator measurements are separate experiments; do not sum ratios into end-to-end speedup.','Historical baseline timeouts are excluded. An incomplete FinalAudit run is used only when the specific online scopes and Simulator::Run are proven completed with identical event/progress counters; no whole-process ratio is inferred.','Index construction is included. Full Read includes local index destruction; persistent online-index destruction is included in whole-program CPU.'])
report['evidence_sha256']={name:hashlib.sha256((H/name).read_bytes()).hexdigest() for name in ['python-timings.csv','cpp-read-timings.csv','cpp-read-profile.json','runtime-results.json']}
(H/'four-contributions.json').write_text(json.dumps(report,indent=2)+'\n')
writecsv('four-contributions.csv',[{k:r[k] for k in ['name','scan_cpu_seconds','index_cpu_seconds','observed_cpu_ratio','complete_scope','index_build_included']} for r in contributions])
writecsv('runtime-self-cpu.csv',self_rows)
print(json.dumps(report,indent=2))
