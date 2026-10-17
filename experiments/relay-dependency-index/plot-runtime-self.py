#!/usr/bin/env python3
"""Disjoint self CPU stacks and a separate nested-build callout, no double count."""
import csv,html,json
from pathlib import Path
H=Path(__file__).resolve().parent
with (H/'runtime-self-cpu.csv').open() as f:rows=list(csv.DictReader(f))
assert rows
by={}
for r in rows:by.setdefault(r['run'],{})[r['phase']]=r
assert len(by)==2
colors=['#0f766e','#0891b2','#1d4ed8','#8b5cf6','#c026d3','#e11d48','#d97706','#65a30d','#64748b']
labels=['Read (all self subphases)','InitAudit (incl. build self)','Simulator self','Audit self / weights-end','Audit group self','Audit weight self','Send / Validate / Ready','FinalAudit self','Other setup / teardown']
def group(ph):
 if ph=='Read' or ph.startswith('Read.'):return 0
 if ph=='InitAudit' or ph.startswith('InitAudit.'):return 1
 if ph=='Simulator::Run':return 2
 if ph in ('Audit','Audit.weights_end_scan'):return 3
 if ph=='Audit.group_scan':return 4
 if ph=='Audit.weight_scan':return 5
 if ph in ('Send','Validate','Ready'):return 6
 if ph=='FinalAudit':return 7
 return 8
values={}
for run,ph in by.items():
 v=[0.0]*len(labels)
 for name,r in ph.items():v[group(name)]+=float(r['self_cpu_seconds'])
 values[run]=v
scale=820/max(sum(v) for v in values.values());parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="510" viewBox="0 0 1120 510">','<rect width="100%" height="100%" fill="white"/>','<g font-family="sans-serif" fill="#18212b">','<text x="25" y="35" font-size="23">Qwen256 runtime snapshots: disjoint process CPU</text>','<text x="25" y="60" font-size="14">Self scopes partition program CPU. Nested inclusive values below are callouts, not extra stacked time.</text>']
for idx,(run,v) in enumerate(values.items()):
 y=100+idx*86;parts.append(f'<text x="25" y="{y}" font-size="15">{html.escape(run + (' [INCOMPLETE: FinalAudit cutoff]' if any(r['complete']!='True' for r in by[run].values()) else ' [complete]'))}</text>');x=25
 for k,val in enumerate(v):
  w=val*scale;parts.append(f'<rect x="{x:.3f}" y="{y+12}" width="{w:.3f}" height="28" fill="{colors[k]}"><title>{html.escape(labels[k])}: {val:.6f} CPU s</title></rect>');x+=w
 parts.append(f'<text x="{x+12:.2f}" y="{y+33}" font-size="14">{sum(v):.3f} s</text>')
for i,label in enumerate(labels):
 x=25+(i%3)*360;y=290+(i//3)*27
 parts.extend([f'<rect x="{x}" y="{y}" width="13" height="13" fill="{colors[i]}"/>',f'<text x="{x+20}" y="{y+12}" font-size="12">{html.escape(label)}</text>'])
for idx,(run,ph) in enumerate(by.items()):
 read=float(ph['Read.dependencies.index_build']['inclusive_cpu_seconds']);online=float(ph['InitAudit.online_index_build']['inclusive_cpu_seconds']);y=400+idx*24
 parts.append(f'<text x="25" y="{y}" font-size="12">{html.escape(run)}: nested Read index build {read:.6f} s; online index build {online:.6f} s (already included above).</text>')
parts.extend(['<text x="25" y="466" font-size="12">Scan snapshot ends during FinalAudit; totals are different scopes, NOT a full-run speedup comparison.</text>','<text x="25" y="488" font-size="12">Simulator self includes uninstrumented application and native work. See runtime-self-cpu.csv for exact phase values.</text>','</g></svg>'])
(H/'runtime-self-cpu.svg').write_text('\n'.join(parts)+'\n')
