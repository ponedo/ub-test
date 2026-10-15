"""Reconstruct summaries from preserved raw evidence without rerunning simulations."""
import argparse,json,subprocess,sys
from pathlib import Path
from verify import verify
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out).resolve()
ledger=json.loads((out/'run-ledger.json').read_text());comparison={}
for row in ledger:
 name,mode=row['case_id'].split('/');case=out/name/mode;s=verify(case)
 with (case/'summary-optimized.json').open('w') as f:subprocess.run([sys.executable,'-O',str(Path(__file__).with_name('verify.py')),str(case)],stdout=f,check=True)
 if json.loads((case/'summary-optimized.json').read_text())!=s:raise ValueError('normal/-O drift')
 (case/'summary.json').write_text(json.dumps(s,indent=2)+'\n');row['summary']=s;comparison.setdefault(name,{})[mode]=s
(out/'run-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');(out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
print('PASS: reverified',len(ledger),'preserved runs; native TA-admission overlap witnesses included')
