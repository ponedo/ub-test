#!/usr/bin/env python3
"""Reproduce the delivered bounded cases; never silently lift executor caps."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;raw=os.environ['CAPACITY_RAW']
def ledger():return json.loads((ROOT/'evidence/run-ledger.json').read_text())
for count in [50000,100000]:
 subprocess.run([sys.executable,str(ROOT/'execute.py'),'--assignments',str(count),'--raw',raw],check=True)
 row=next(x for x in ledger() if x['case_id']==f'no-balancing-{count}')
 if row['status']!='success':break
subprocess.run([sys.executable,str(ROOT/'finish_ledger.py')],check=True)
rows=ledger();success=[x['assignments'] for x in rows if x['mode']=='no-balancing' and x['status']=='success']
for count in sorted(set([min(success),max(success)] if success else [])):
 subprocess.run([sys.executable,str(ROOT/'execute.py'),'--assignments',str(count),'--mode','ultraep','--raw',raw],check=True)
 if next(x for x in ledger() if x['case_id']==f'ultraep-{count}')['status']!='success':break
rows=ledger()
for row in rows:
 if row['status']=='pending':row.update(status='not_attempted',reason='Outside delivered measured envelope or prerequisite treatment stopped; executor caps remain unchanged. A faster reproduction host requires a separately audited extension, not automatic cap removal.')
(ROOT/'evidence/run-ledger.json').write_text(json.dumps(rows,indent=2)+'\n');subprocess.run([sys.executable,str(ROOT/'finish_ledger.py')],check=True)
