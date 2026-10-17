#!/usr/bin/env python3
"""Collect measured results without substituting analytical estimates."""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
rows=[]
for root in sorted(a.raw.glob('gate-d-*')):
 if not root.is_dir() or not (root/'results.json').exists():continue
 for r in json.loads((root/'results.json').read_text()):
  h=r.get('host',{});m=r.get('metrics',{});s=r.get('summary',{});v=r.get('verifier_host',{})
  case=root/r['case']/r['mode']/'run'
  with (case/'input.txt').open() as f: header=list(map(int,f.readline().split()))
  rows.append(dict(case=r['case'],mode=r['mode'],input_assignments=header[2]*header[3],input_tokens=header[3],counts_finalized=bool(m),assignments=m.get('assignments'),host_status=h.get('status'),guard=h.get('guard'),verification=r.get('verification'),wall_seconds=h.get('wall_seconds'),cpu_seconds=h.get('user_cpu_seconds',0)+h.get('system_cpu_seconds',0),peak_rss_kib=h.get('peak_rss_kib'),jettys=m.get('jettys'),remote_WQEs=m.get('remote_WQEs'),TAs=m.get('TA_count'),events=m.get('simulator_events'),sender_completions=m.get('sender_completions'),tokens=m.get('completed_tokens'),layer_latency_ps=s.get('layer_latency_ps'),verifier_wall_seconds=v.get('wall_seconds'),verifier_peak_rss_kib=v.get('peak_rss_kib')))
(a.out/'performance.json').write_text(json.dumps(rows,indent=2)+'\n')
with (a.out/'performance.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['case']);w.writeheader();w.writerows(rows)
gates={}
for gate in ['gate-b','gate-c']:
 path=a.raw/gate/'results.json'
 if path.exists():
  data=json.loads(path.read_text());gates[gate]={'runs':len(data),'verified':sum(x.get('verification')=='PASS' for x in data),'logical_failures':[x['case'] for x in data if x.get('logical_differences')],'case_latency':[{'case':x['case'],'mode':x['mode'],'latency_ps':x.get('summary',{}).get('layer_latency_ps'),'jettys':x.get('metrics',{}).get('jettys')} for x in data]}
(a.out/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
lines=['| Assignments | Mode | Status | Wall s | CPU s | RSS KiB | Jetty | WQE / TA | Layer ps |','|---:|---|---|---:|---:|---:|---:|---|---:|']
for r in sorted(rows,key=lambda r:(r['input_assignments'],r['mode'])):
 def val(k):return str(r[k]) if r[k] is not None else '未完成'
 lines.append(f"| {r['input_assignments']} | {r['mode']} | {r['guard'] or r['verification'] or r['host_status']} | {r['wall_seconds']:.2f} | {r['cpu_seconds']:.2f} | {r['peak_rss_kib']} | {val('jettys')} | {val('remote_WQEs')} / {val('TAs')} | {val('layer_latency_ps')} |")
(a.out/'performance-table.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(rows,indent=2))
