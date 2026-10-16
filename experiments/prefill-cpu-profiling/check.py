#!/usr/bin/env python3
"""Validate measured evidence, not a mirror of profiling implementation."""
import hashlib,json,re
from pathlib import Path
H=Path(__file__).resolve().parent;E=H/'evidence';RAW=Path('/workspace/prefill-cpu-raw')
rows=json.loads((E/'run-ledger.json').read_text());assert len(rows)==12
for a in [5000,10000,20000,50000]:
 selected=[r for r in rows if r['assignments']==a];assert len(selected)==3
 for r in selected:
  assert r['status']=='success'
  assert all(s['status']=='PASS' and s['returncode']==0 and s['guard'] is None for s in r['stages'].values())
  assert r['file_hashes']==selected[0]['file_hashes']
 assert all(json.loads((E/f'parity-{a}.json').read_text()).values())
 s=json.loads((E/str(a)/'sample-summary.json').read_text());report=(E/str(a)/'perf-report.txt').read_text();assert sum(int(m[1]) for m in re.finditer(r'^\s*[\d.]+%\s+(\d+)\s+\d+', (E/str(a)/'perf-symbols.txt').read_text(),re.M))==s['samples'];assert 'Total Lost Samples: 0' in report;assert abs(sum(r['percent'] for r in s['all_self'])-100)<1e-8
 times=json.loads((E/str(a)/'timing.json').read_text());assert all(x['calls']>=0 and x['inclusive_seconds']>=x['exclusive_seconds']>=0 for x in times)
 for r in selected:
  metrics=json.loads((RAW/r['id']/'run/simulator-metrics.json').read_text());assert metrics['assignments']==a and metrics['completed_tokens']==a//8
 print(a,'full output parity, strict verification, resource guards, sampled count/loss and nested timings PASS')
# Prefix comparison directly from generated mappings; no regenerated input.
configs=[json.loads((RAW/f'common-{a}/planner-input.json').read_text()) for a in [5000,10000,20000,50000]]
for x,y in zip(configs,configs[1:]):assert x['mapping']==y['mapping'][:len(x['mapping'])]
print('trace-prefix equality PASS')

configs=[json.loads((RAW/f"{a}-baseline/run/config.json").read_text()) for a in [5000,10000,20000,50000]]
fixed={k:configs[0][k] for k in ["parameters","runtime","mode","weight_strategy","relay_parameters","readiness"]}
for c in configs:assert {k:c[k] for k in fixed}==fixed
(E/"fixed-runtime-config.json").write_text(json.dumps(fixed,indent=2)+"\n")
print("fixed runtime parameters across all scales PASS; trace RNG20261016, payload seed20261015 inherited")
