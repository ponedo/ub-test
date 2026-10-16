#!/usr/bin/env python3
"""Apply preregistered stop/representative rules, never infer unrun success."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;p=ROOT/'evidence/run-ledger.json';rows=json.loads(p.read_text());controls=[x for x in rows if x['mode']=='no-balancing'];done=[x['assignments'] for x in controls if x['status']=='success'];failure=next((x for x in controls if x['status']=='failed'),None)
for x in rows:
 if x['assignments']==1000000 and x['status']=='pending':x.update(status='not_attempted',reason='20-bit wire Jetty ID preflight rejects approximately 2M global task IDs; original T cap also exceeded; no remapping or protocol change authorized')
 elif x['mode']=='no-balancing' and x['status']=='pending' and failure:x.update(status='not_attempted',reason='Sequential expansion stopped after '+failure['case_id']+' '+failure.get('failed_stage','')+': '+failure.get('reason',''))
 elif x['mode']=='ultraep' and x['status']=='pending' and done and x['assignments'] not in [min(done),max(done)]:x.update(status='not_selected',reason='Representative treatment rule selects first/largest fully verified NoBalance scale only; no full strategy matrix')
p.write_text(json.dumps(rows,indent=2)+'\n')
(ROOT/'run-ledger.md').write_text('# Capacity run ledger\n\nDurable exact commands/resources: [evidence/run-ledger.json](evidence/run-ledger.json).\n\n| Case | Status | Reason |\n|---|---|---|\n'+'\n'.join('| '+x['case_id']+' | '+x['status']+' | '+x.get('reason','')+' |' for x in rows)+'\n')
print('ledger updated; fully verified NoBalance scales:',done)
