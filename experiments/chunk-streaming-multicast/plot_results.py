#!/usr/bin/env python3
"""Rebuild three aggregate SVGs using only the two delivered CSV files beside this script."""
import csv, html
from pathlib import Path
D=Path(__file__).resolve().parent
with (D/'five-strategy-results.csv').open() as f:
    cases=list(csv.DictReader(f))
for row in cases:
    for key in ('layer_latency_ps','weight_duration_ps','source_weight_payload_bytes','source_weight_wire_bytes'):
        row[key]=int(row[key])
with (D/'hybrid-stage-summary.csv').open() as f:
    stages=list(csv.DictReader(f))
for row in stages:
    for key in ('branch_payload_bytes','original_first_send_bytes','envelopes','multicast_groups','groups'):
        row[key]=int(row[key])
h={'hybrid':{'by_role':{row['graph_role']:row for row in stages}}}
labels={'no-balancing':'NoBal','direct':'Direct','chunk-streaming':'CS','multicast-v2':'MC','chunk-streaming-multicast':'CS+MC'}
def svg_start(title,sub,height):return [f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}"><rect width="960" height="{height}" fill="#fff"/><style>text{{font-family:Arial,sans-serif;fill:#172b4d}}.small{{font-size:13px}}.label{{font-size:15px}}.title{{font-size:23px;font-weight:bold}}</style>',f'<text x="34" y="38" class="title">{html.escape(title)}</text>',f'<text x="34" y="63" class="small">{html.escape(sub)}</text>']
def bars(name,title,fields,colors,scale,unit,sub):
 o=svg_start(title,sub,435);x0=155;maxv=max(a[k]/scale for a in cases for k,_ in fields);width=635
 for i,a in enumerate(cases):
  y=112+i*57;o.append(f'<text x="32" y="{y+15}" class="label">{labels[a["strategy"]]}</text>')
  for j,(k,label) in enumerate(fields):
   v=a[k]/scale;yy=y+j*19;o.append(f'<rect x="{x0}" y="{yy}" width="{v/maxv*width:.3f}" height="15" rx="2" fill="{colors[j]}"/><text x="{x0+v/maxv*width+7:.3f}" y="{yy+12}" class="small">{v:.3f}</text>')
 for j,(_,label) in enumerate(fields):o.append(f'<rect x="{155+j*270}" y="405" width="15" height="15" fill="{colors[j]}"/><text x="{177+j*270}" y="417" class="small">{label} ({unit})</text>')
 o.append('</svg>');(D/name).write_text('\n'.join(o)+'\n')
bars('latency.svg','N256: full-layer and weight-stage latency',[('layer_latency_ps','Full layer'),('weight_duration_ps','Weight stage')],['#2458a6','#7ba7e1'],1e6,'µs','One deterministic case. CS and MC reused; NoBal, Direct and CS+MC newly run. Lower is better.')
bars('source-weight-traffic.svg','N256: actual source-side weight traffic',[('source_weight_payload_bytes','Source payload'),('source_weight_wire_bytes','Source wire')],['#15836d','#85c5b2'],1048576,'MiB','All source weight egress, including chunk stages and whole-expert groups. NoBal has no weight transfers.')
o=svg_start('CS+MC: actual envelope coverage by graph role','Member payload carried in envelopes, not fraction of source packets or theoretical group eligibility.',345)
for i,role in enumerate(['stage1','stage2','direct-fallback']):
 x=h['hybrid']['by_role'][role];p=100*x['branch_payload_bytes']/x['original_first_send_bytes'];y=110+i*65;label={'stage1':'Stage I chunks','stage2':'Stage II chunks','direct-fallback':'Whole-expert groups'}[role]
 o.append(f'<text x="30" y="{y+17}" class="label">{label}</text><rect x="210" y="{y}" width="580" height="27" fill="#e7edf4"/><rect x="210" y="{y}" width="{5.8*p:.3f}" height="27" fill="#6c4fb3"/><text x="805" y="{y+19}" class="label">{p:.3f}%</text><text x="210" y="{y+45}" class="small">{x["envelopes"]:,} envelopes; {x["multicast_groups"]:,}/{x["groups"]:,} groups merged at least once</text>')
o.append('<text x="30" y="330" class="small">The remaining member payload used immediate original native unicast. No synchronization was added.</text></svg>');(D/'hybrid-envelope-coverage.svg').write_text('\n'.join(o)+'\n')
# Explicit SVG text attributes support lightweight renderers that omit CSS classes.
for p in D.glob('*.svg'):
 text=p.read_text().replace('class="title"','font-family="Arial,sans-serif" font-size="23" font-weight="bold"').replace('class="label"','font-family="Arial,sans-serif" font-size="15"').replace('class="small"','font-family="Arial,sans-serif" font-size="13"')
 p.write_text(text)
