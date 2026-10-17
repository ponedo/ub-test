#!/usr/bin/env python3
"""Validate real candidate counts and included index-build phases after timed parity."""
import argparse,csv,json
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2]
p=argparse.ArgumentParser();p.add_argument('--name',default='parity-instrumented');a=p.parse_args();root=W/'relay-dependency-index-raw'/a.name
rows=[]
for timing_path in sorted(root.glob('*/*/timing.json')):
 d=json.loads(timing_path.read_text());c=d['counters'];ph=d['phases'];variant=timing_path.parent.name
 with (timing_path.parent/'run/executed-transfers.csv').open() as f:tasks=list(csv.DictReader(f))
 weights=[x for x in tasks if x['stage']=='2'];edges=sum(len(x['dependencies'].split(';')) if x['dependencies'] else 0 for x in weights)
 dep=d['dependency_mode'];online=d['online_membership_mode'];w=len(weights)
 assert d['complete'] and d['terminal'] and not d['failed']
 assert c['read_dependency_edges']==edges
 assert c['read_dependency_candidates']==(edges if dep=='index' else w*c['read_dependency_replica_tasks'])
 assert c['read_dependency_index_build_candidates']==(w if dep=='index' else 0)
 assert c['read_dependency_replica_index_entries']==(w if dep=='index' else 0)
 assert c['online_index_build_candidates']==(w if online=='index' else 0)
 assert c['online_replica_index_entries']==(w if online=='index' else 0)
 for kind in ['group','weight']:
  assert c[f'audit_{kind}_scan_candidates']==(c[f'audit_{kind}_scan_matches'] if online=='index' else w*c[f'audit_{kind}_events'])
  assert c[f'audit_{kind}_index_lookups']==(c[f'audit_{kind}_events'] if online=='index' else 0)
 for parent,child in [('Read','Read.dependencies'),('Read.dependencies','Read.dependencies.index_build'),('InitAudit','InitAudit.online_index_build')]:
  assert ph[parent]['inclusive_cpu_ns']>=ph[child]['inclusive_cpu_ns']
 assert not any(x['active_calls'] for x in ph.values())
 rows.append(dict(case=timing_path.parent.parent.name,variant=variant,status='PASS',weight_tasks=w,dependency_edges=edges,counters=c))
assert len(rows)==20,len(rows)
(H/'instrumented-counter-checks.json').write_text(json.dumps(dict(status='PASS',tests=rows),indent=2)+'\n')
print('PASS',len(rows),'instrumented mode/candidate/index-build checks')
