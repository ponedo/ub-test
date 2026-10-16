#!/usr/bin/env python3
import argparse,csv,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for f in sorted(a.root.glob('*/attempt.json')):
 d=json.loads(f.read_text());s=d['stages']['ns3'];v=d['stages'].get('verify',{});summary=json.loads((f.parent/'run/summary.json').read_text()) if (f.parent/'run/summary.json').exists() else {}
 rows.append(dict(attempt=d['attempt'],native='B-index' if d['arm']=='A' else 'C-fixed',assignments=d['assignments'],status=d['status'],wall_s=s['wall_seconds'],cpu_s=s['user_cpu_seconds']+s['system_cpu_seconds'],peak_rss_kib=s['peak_rss_kib'],verify_wall_s=v.get('wall_seconds'),layer_latency_ps=summary.get('layer_latency_ps'),remote_WQEs=summary.get('remote_WQEs'),target_segments=summary.get('target_segments'),parity=d.get('parity',{}).get('pass','reference'),file_count=len(d.get('file_hashes',{}))))
with (a.out/'runs.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
groups=[]
for scale in sorted({r['assignments'] for r in rows}):
 g={'assignments':scale}
 for arm in ('B-index','C-fixed'):
  rs=[r for r in rows if r['assignments']==scale and r['native']==arm];assert len(rs)==3 and all(r['status']=='success' for r in rs)
  g[arm]={'runs':len(rs),'median_wall_s':statistics.median(r['wall_s'] for r in rs),'min_wall_s':min(r['wall_s'] for r in rs),'max_wall_s':max(r['wall_s'] for r in rs),'median_peak_rss_kib':statistics.median(r['peak_rss_kib'] for r in rs),'median_cpu_s':statistics.median(r['cpu_s'] for r in rs)}
 g['wall_ratio_fixed_over_index']=g['C-fixed']['median_wall_s']/g['B-index']['median_wall_s'];groups.append(g)
assert all(r['file_count']==398 and r['parity'] in ('reference',True) for r in rows)
(a.out/'summary.json').write_text(json.dumps(groups,indent=2)+'\n');print(json.dumps(groups,indent=2))
