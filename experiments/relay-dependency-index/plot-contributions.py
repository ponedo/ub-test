#!/usr/bin/env python3
"""Render measured completed-stage CPU comparisons, never censored ratios."""
import json,math,html
from pathlib import Path
H=Path(__file__).resolve().parent
rows=json.loads((H/'four-contributions.json').read_text())['contributions']
assert all(x['complete_scope'] for x in rows)
width,height=1040,150+len(rows)*100
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="#fff"/>','<g font-family="sans-serif" fill="#18212b">','<text x="24" y="34" font-size="22">Four independent indexed lookups: measured CPU</text>','<text x="24" y="58" font-size="13">Completed TARGET scopes only; scan simulator process is incomplete. Each panel has its own linear scale.</text>']
for i,r in enumerate(rows):
 y=92+i*100;scan=r['scan_cpu_seconds'];idx=r['index_cpu_seconds'];scale=650/max(scan,idx)
 parts.append(f'<text x="24" y="{y}" font-size="15">{html.escape(r["name"])}</text>')
 for j,(label,value,color) in enumerate([('scan',scan,'#64748b'),('index',idx,'#0284c7')]):
  yy=y+12+j*24;parts += [f'<text x="35" y="{yy+13}" font-size="12">{label}</text>',f'<rect x="90" y="{yy}" width="{max(1,value*scale):.2f}" height="17" fill="{color}"/>',f'<text x="755" y="{yy+13}" font-size="13">{value:.6f} s</text>']
 parts.append(f'<text x="900" y="{y+40}" font-size="15">{scan/idx:.2f}×</text>')
parts += [f'<text x="24" y="{height-24}" font-size="12">See four-contributions.json and REPORT.md for scope/build-cost and observer limitations.</text>','</g></svg>']
(H/'dependency-index-cpu.svg').write_text('\n'.join(parts)+'\n')
