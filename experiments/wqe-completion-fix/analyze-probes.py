#!/usr/bin/env python3
import argparse,csv,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--frontier',type=Path);a=p.parse_args();rows=json.loads((a.root/'results.json').read_text());summary=[]
for r in rows:
 stem=a.root/f"{r['arm']}-{r['kind']}-{r['case']}"
 if r['kind'] in ('cancel','wake'):continue
 events=list(csv.DictReader(Path(str(stem)+'-events.csv').open()));tasks=sorted({int(e['wqe_id']) for e in events if e['event']=='submit'})
 for task in tasks:
  es=[e for e in events if int(e['wqe_id'])==task];sent=[int(e['ssn']) for e in es if e['event']=='segment_sent'];done=[e for e in es if e['event']=='target_complete'];callbacks=[e for e in es if e['event']=='sender_callback'];final_target=max([int(e['time_ns']) for e in done],default=-1)
  entry=dict(arm=r['arm'],kind=r['kind'],case=r['case'],wqe=task,actual_ssns=sent,ta_count=len(done),callbacks=len(callbacks),target_last_ns=final_target,callback_ns=int(callbacks[0]['time_ns']) if callbacks else None,completion_order=[int(e['ssn']) for e in done]);entry['causal_pass']=len(callbacks)==1 and entry['callback_ns']>=final_target and len(done)==len(sent);summary.append(entry)
  if r['arm']=='C':assert entry['causal_pass'],entry
assert all(r['rc']==0 for r in rows if r['arm']=='C')
assert all(r['rc']==1 for r in rows if r['arm'] in 'AB' and r['kind']=='wake')
if any(r['kind']=='wake' for r in rows):
 assert 'hole_observed=0,errors=0' in (a.root/'C-cancel-cancel-hole.stdout').read_text()
# The original source and all original evidence stay untouched.
if a.frontier:
 matched=[]
 for f in sorted(a.frontier.glob('C-*-events.csv')):
  assert f.read_bytes()==(a.root/f.name).read_bytes(), f.name
  matched.append(f.name)
 (a.root/'frontier-parity.json').write_text(json.dumps({'pass':bool(matched),'identical_event_files':matched},indent=2)+'\n')
for suffix in ('-events.csv','-summary.txt'):
 assert (a.root/('A-original-original'+suffix)).read_bytes()==(a.root/('B-original-original'+suffix)).read_bytes()
(a.root/'causality.json').write_text(json.dumps(summary,indent=2)+'\n')
with (a.root/'causality.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=summary[0].keys());w.writeheader();w.writerows(summary)
pressure=list(csv.DictReader((a.root/'C-expanded-pressure-events.csv').open()))
peak=max(int(e['snd_nxt'])-int(e['snd_una']) for e in pressure)
assert peak == 512, peak
(a.root/'pressure.json').write_text(json.dumps({'peak_observed_inflight_ta':peak,'expected_limit':512,'total_segment_sent':sum(e['event']=='segment_sent' for e in pressure)},indent=2)+'\n')
manifest={str(f.relative_to(a.root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.root.iterdir()) if f.is_file() and f.name != 'sha256.json' and f.suffix not in ('',)}
(a.root/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('C causal validation passed for',sum(s['arm']=='C' for s in summary),'WQE observations; A/B original bytes equal')
