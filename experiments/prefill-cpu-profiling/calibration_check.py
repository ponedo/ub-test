#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
from analyze import analyze_perf
from execute import H,RAW
p=argparse.ArgumentParser();p.add_argument('--perf',type=Path,required=True);a=p.parse_args()
data=H/'evidence/calibration2.data'
if not data.exists():data=RAW/'calibration/calibration2.data'
s=analyze_perf(data,H/'evidence/calibration-analysis',a.perf)
text=(H/'evidence/calibration2-console.txt').read_text();line=next(x for x in text.splitlines() if x.startswith('CPU samples='));r={k:float(v) if '.' in v else int(v) for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}
hot=sum(x['samples'] for x in s['self_top20'] if 'hot_loop' in x['symbol']);ratio=r['period_sum_ns']/1e9/r['child_user_seconds']
checks=dict(counts_agree=s['sample_count']==r['samples'],enough_samples=s['sample_count']>=50,known_hot_loop_fraction=hot/s['sample_count']>=.95,period_user_ratio=.8<=ratio<=1.2,one_thread=len(s['pid_tid_scope'])==1,clean_single_hotloop_chain=True,no_loss_or_throttle=all(s['records'].get(x,0)==0 for x in ['LOST','LOST_SAMPLES','THROTTLE','UNTHROTTLE']))
# Calibration folded stacks must not repeat the known hot function.
for stack in (H/'evidence/calibration-analysis/stacks-count.folded').read_text().splitlines():
 if stack.count('hot_loop')>1:checks['clean_single_hotloop_chain']=False
result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,samples=r['samples'],period_sum_ns=r['period_sum_ns'],child_user_seconds=r['child_user_seconds'],child_system_seconds=r['child_system_seconds'],period_user_ratio=ratio,known_hot_loop_samples=hot)
(H/'evidence/calibration-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert all(checks.values())
