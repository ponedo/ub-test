#!/usr/bin/env python3
"""Export full/Top20 tables and compact callpath SVGs; no sum of nested cumtime."""
import argparse,csv,hashlib,html,json,pstats
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
def write(name,rows):
 if not rows:return
 with (a.out/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def label(key):
 file,line,name=key
 return (('/'.join(Path(file).parts[-3:])+':'+str(line)) if file!='~' else '~')+' '+name
for stage in ['preparation','preflight']:
 path=a.raw/stage/'profile.pstats'
 if not path.exists():continue
 stats=pstats.Stats(str(path));rows=[];edges=[]
 for key,(cc,nc,tt,ct,callers) in stats.stats.items():
  rows.append(dict(function=label(key),primitive_calls=cc,total_calls=nc,self_seconds=tt,cumulative_seconds=ct,self_percent=100*tt/stats.total_tt))
  for caller,value in callers.items():
   if isinstance(value,tuple):edges.append(dict(caller=label(caller),callee=label(key),primitive_calls=value[0],total_calls=value[1],self_seconds=value[2],cumulative_seconds=value[3]))
 rows.sort(key=lambda r:r['self_seconds'],reverse=True);write(stage+'-all-functions.csv',rows);write(stage+'-top20-self.csv',rows[:20]);write(stage+'-top20-cumulative.csv',sorted(rows,key=lambda r:r['cumulative_seconds'],reverse=True)[:20]);write(stage+'-top20-calls.csv',sorted(rows,key=lambda r:r['total_calls'],reverse=True)[:20]);edges.sort(key=lambda r:r['cumulative_seconds'],reverse=True);write(stage+'-call-edges.csv',edges)
 # Edge list graphic deliberately shows overlapping cumulative values, not a summed flame area.
 selected=[e for e in edges if ('adapter.py' in e['callee'] or 'preflight.py' in e['callee'] or 'json/' in e['callee'] or 'subprocess.py' in e['callee'] or 'planner.py' in e['callee'])][:16]
 svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="'+str(100+len(selected)*44)+'"><rect width="100%" height="100%" fill="#fafafa"/><g font-family="monospace" font-size="12" fill="#16283c"><text x="20" y="25" font-size="18">'+stage+': measured call edges (inclusive; overlapping)</text><text x="20" y="48">Arrow labels = callee cumulative seconds attributed to caller. Never add ancestor and descendant values.</text>']
 for i,e in enumerate(selected):
  y=80+i*44;svg.extend([f'<text x="20" y="{y}">{html.escape(e["caller"])}</text>',f'<text x="45" y="{y+18}" fill="#176a92">→ {html.escape(e["callee"])} | {e["cumulative_seconds"]:.3f} s | {e["total_calls"]} calls</text>'])
 svg.append('</g></svg>');(a.out/(stage+'-callpaths.svg')).write_text('\n'.join(svg))
 coverage=json.loads((a.raw/stage/'coverage.json').read_text());(a.out/(stage+'-coverage.json')).write_text(json.dumps(coverage,indent=2)+'\n')
 (a.out/(stage+'-stages.csv')).write_bytes((a.raw/stage/'stages.csv').read_bytes())
manifest={str(x.relative_to(a.raw)):dict(bytes=x.stat().st_size,sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in a.raw.glob('*/*') if x.is_file() and x.suffix in ('.pstats','.csv','.json') and x.parent.name!='prepared'}
(a.out/'raw-profile-manifest.json').write_text(json.dumps(dict(raw_root=str(a.raw.resolve()),note='Raw evidence remains local at raw_root; each relative path below resolves under that directory. Binary pstats are intentionally excluded from repository publication.',files=manifest),indent=2)+'\n')
