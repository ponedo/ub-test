#!/usr/bin/env python3
"""Render disjoint measured CPU scopes, not overlapping inclusive totals."""
import csv,html,json
from pathlib import Path
H=Path(__file__).resolve().parent;E=H/'evidence';rows=list(csv.DictReader((E/'runtime-phases.csv').open()));runs=['chunk-streaming-timed','direct-timed','no-balancing-timed'];colors=['#2563eb','#f59e0b','#10b981','#ec4899','#8b5cf6','#64748b'];labels=['Read/init/topology','Run residual self','Audit self + scans','Send/Validate/Ready self','FinalAudit','Other measured self'];data=[]
for run in runs:
 r={x['phase']:float(x['self_cpu_ns'])/1e9 for x in rows if x['run']==run};v=[0]*6
 for name,value in r.items():
  i=0 if name.startswith('Read') or name in ('InitAudit','Topology') else 1 if name=='Simulator::Run' else 2 if name.startswith('Audit') else 3 if name in ('Send','Validate','Ready') else 4 if name=='FinalAudit' else 5
  v[i]+=value
 data.append((run,v))
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="360" viewBox="0 0 1100 360">','<rect width="1100" height="360" fill="white"/>','<g font-family="sans-serif" fill="#172033">','<text x="25" y="28" font-size="20">Disjoint process-CPU scopes (diagnostic build)</text>','<text x="25" y="52" font-size="12">Chunk is a partial 300-second window; Direct and No Balancing complete. Run residual includes uninstrumented work.</text>'];scale=760/300
for j,(run,vs) in enumerate(data):
 y=85+j*55;svg.append(f'<text x="25" y="{y+20}" font-size="13">{html.escape(run)}</text>');x=220
 for v,c in zip(vs,colors):svg.append(f'<rect x="{x:.2f}" y="{y}" width="{v*scale:.2f}" height="28" fill="{c}"/>');x+=v*scale
 svg.append(f'<text x="{x+6:.2f}" y="{y+20}" font-size="12">{sum(vs):.3f}s</text>')
for j,(label,c) in enumerate(zip(labels,colors)):
 x=25+(j%3)*355;y=275+(j//3)*27;svg.extend([f'<rect x="{x}" y="{y}" width="14" height="14" fill="{c}"/>',f'<text x="{x+20}" y="{y+12}" font-size="12">{label}</text>'])
svg+=['<text x="25" y="345" font-size="11">Snapshot serialization CPU excluded; observer/code-layout perturbation remains. These are not sampled percentages.</text>','</g></svg>'];(E/'runtime-phase-cpu.svg').write_text('\n'.join(svg))
