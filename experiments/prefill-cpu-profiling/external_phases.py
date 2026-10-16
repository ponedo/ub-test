#!/usr/bin/env python3
import csv,json
from execute import H,RAW
rows=[]
for a in [5000,10000,20000,50000]:
 for variant,phase,folder in [('shared-input',p,RAW/f'common-{a}') for p in ['generate','planner','adapter']]+[(v,p,RAW/f'{a}-{v}') for v in ['baseline','sampled','timed'] for p in ['ns3','verify']]:
  d=json.loads((folder/'stages'/phase/'resource.json').read_text());rows.append(dict(assignments=a,variant=variant,phase=phase,status=d['status'],wall_seconds=d['wall_seconds'],user_cpu_seconds=d['user_cpu_seconds'],system_cpu_seconds=d['system_cpu_seconds'],peak_rss_kib=d['peak_rss_kib']))
with (H/'evidence/analysis/external-phases.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Wrote generation/planner/adapter/ns3/strict-verifier phase resources')
