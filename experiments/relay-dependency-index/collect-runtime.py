#!/usr/bin/env python3
"""Compact measured resources/phases; distinguish complete runs from cutoffs."""
import csv,json
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw';rows=[];phases=[];proofs=[]
for root in sorted((R/'runtime').glob('*')):
 if not (root/'host/resource.json').exists():continue
 r=json.loads((root/'host/resource.json').read_text());p=json.loads((root/'provenance.json').read_text());summary=root/'run/online-summary.json';complete=summary.exists();t=json.loads((root/'timing.json').read_text()) if (root/'timing.json').exists() else None
 row=dict(name=root.name,dependency_mode=p['dependency_mode'],online_mode=p['online_mode'],timed=p['timed'],sampled=p['sampled'],status=r['status'],guard=r['guard'],complete=complete,wall_s=r['wall_seconds'],user_cpu_s=r['user_cpu_seconds'],system_cpu_s=r['system_cpu_seconds'],peak_rss_kib=r['peak_rss_kib'],layer_latency_ps=None,simulator_events=None,completed_tokens=None,graph_hash=None)
 if complete:
  s=json.loads(summary.read_text());row.update(layer_latency_ps=s['layer_latency_ps'],simulator_events=s['simulator_events'],completed_tokens=s['completed_tokens'],graph_hash=s['executed_graph_fnv1a64']);assert s['executed_graph_fnv1a64']=='6ada88bf8945a70f'
  assert s['completed_tokens']==256
 if t:
  row.update(partial_simulator_events=t['simulator_events'],partial_simulated_time_ps=t['simulated_time_ps'],partial_progress=t['progress'],profile_complete=t['complete'],snapshot_overhead_cpu_ns=t['snapshot_overhead_cpu_ns_before_this_snapshot'])
  for name,data in t['phases'].items():phases.append(dict(run=root.name,phase=name,complete=complete,**data))
 evidence=H/'runtime-evidence';evidence.mkdir(exist_ok=True)
 detail=dict(provenance=p,resource={key:r[key] for key in ['start','command','wall_seconds','returncode','status','guard','peak_rss_kib','sampled_peak_tree_rss_bytes','max_observed_threads_per_process','user_cpu_seconds','system_cpu_seconds','limits']},timing=t)
 if complete:detail.update(summary=json.loads(summary.read_text()),validation=json.loads((root/'run/validation.json').read_text()))
 (evidence/(root.name+'.json')).write_text(json.dumps(detail,indent=2)+'\n')
 rows.append(row)
# Full-run stable output equivalence is checked only when both runs complete.
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k!='verification_wall_ns'}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
completed=[x for x in rows if x['complete']]
if completed:
 reference=completed[0]['name']
 for row in completed[1:]:
  for name in ['online-summary.json','validation.json','simulator-metrics.json']:
   same=stable(json.loads((R/'runtime'/reference/'run'/name).read_text()))==stable(json.loads((R/'runtime'/row['name']/'run'/name).read_text()));assert same,(reference,row['name'],name);proofs.append(dict(reference=reference,candidate=row['name'],file=name,stable_equal=same))
(H/'runtime-results.json').write_text(json.dumps(dict(runs=rows,completed_output_parity=proofs,excluded_json_fields=['verification_wall_ns']),indent=2)+'\n')
keys=['name','dependency_mode','online_mode','timed','sampled','status','guard','complete','wall_s','user_cpu_s','system_cpu_s','peak_rss_kib','layer_latency_ps','simulator_events','completed_tokens','graph_hash']
with (H/'runtime-results.csv').open('w') as f:
 w=csv.DictWriter(f,keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
if phases:
 with (H/'runtime-phases.csv').open('w') as f:
  w=csv.DictWriter(f,list(phases[0]));w.writeheader();w.writerows(phases)
print(json.dumps(rows,indent=2))
