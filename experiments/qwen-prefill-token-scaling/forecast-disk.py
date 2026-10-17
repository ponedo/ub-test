#!/usr/bin/env python3
"""Timestamped external disk forecast; observation only, never changes guards."""
import argparse,datetime,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--reference-tokens',type=int,default=512);p.add_argument('--tokens',type=int,nargs='+',default=[2048,4096]);p.add_argument('--out',type=Path,required=True);p.add_argument('--reserve-intervening',action='store_true');a=p.parse_args()
ref=a.raw/f'tokens-{a.reference_tokens}';m=json.loads((ref/'prepared-evidence/manifest.json').read_text());logical=sum(x['bytes'] for x in m['files'].values());archive=m['archive_bytes'];retained=sum(x.stat().st_size for x in ref.rglob('*') if x.is_file());free=shutil.disk_usage(a.raw).free
rows=[]
for n in a.tokens:
 assert not (a.raw/f'tokens-{n}').exists(), 'Cannot label already-started level as pre-run forecast'
 scale=n/a.reference_tokens
 # Preparation tree + temporary xz/part duplication + retained point output allowance.
 working=int(1.25*logical*scale+3*archive*scale+2*retained*scale)
 rows.append(dict(tokens=n,not_started_at_observation=True,estimated_peak_incremental_disk_bytes=working,estimated_retained_point_bytes=int(retained*scale),free_disk_bytes_at_observation=free,headroom_above_hard_guard_bytes=free-8*1024**3,estimate_fits_observed_headroom=working<=free-8*1024**3))
if a.reserve_intervening:
 for r in rows:
  reserve=sum(int(retained*n/a.reference_tokens) for n in (1024,2048) if a.reference_tokens<n<r['tokens'])
  r.update(intervening_retention_reserve_bytes=reserve,reserved_headroom_bytes=free-8*1024**3-reserve,estimate_fits_reserved_headroom=r['estimated_peak_incremental_disk_bytes']<=free-8*1024**3-reserve)
d=dict(observed_host_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reference_tokens=a.reference_tokens,reference_prepared_logical_input_bytes=logical,reference_archive_bytes=archive,reference_retained_point_bytes=retained,method='Linear token ratio applied to completed summary-mode reference footprint: 1.25*prepared input bytes + 3*compressed archive bytes + 2*retained point bytes. Allowances model temporary archival copies and summary/ledger output; uncertainty unknown, not a proven upper bound.',guard='Actual free workspace disk must remain >=8589934592 bytes; forecast does not relax or replace hard guard.',limitations='512 and 1024 had exact input size/free-disk checks and live guards, but no separately recorded output-growth forecast before execution.',forecasts=rows)
a.out.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))
