import argparse,csv,json,subprocess
from pathlib import Path
from oracle import estimate,FIELDS
p=argparse.ArgumentParser();p.add_argument('probe',type=Path);p.add_argument('out',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
rows=[]
for m in [0,1,8,19,20,32,64,128,256]:
 expected=estimate(m);actual=list(map(int,subprocess.check_output([a.probe,*map(str,[m,4096,1536,2,1,100,2692])],text=True).strip().split(',')));assert actual==list(expected.values())
 rows.append(dict(tokens=m,**expected))
for params in [(7,64,128,2,2,13,101),(256,4096,1536,2,1,100,2692),(1,4096,1536,2,1,1,1)]:
 assert list(map(int,subprocess.check_output([a.probe,*map(str,params)],text=True).strip().split(',')))==list(estimate(*params).values())
for m,override in [(0,12288),(1,12288),(32,18874368),(8,0)]:
 params=[m,4096,1536,2,1,100,2692];actual=list(map(int,subprocess.check_output([a.probe,*map(str,params),str(override)],text=True).strip().split(",")));assert actual==list(estimate(*params,configured_weight_bytes=override).values())
invalid=[[-1,4096,1536,2,1,100,2692],[1,0,1536,2,1,100,2692],[1,4096,1536,2,1,0,2692],[1,4096,1536,2,1,100,0],[2**32,4096,1536,2,1,100,2692],[2**32-1,2**32-1,2**32-1,8,8,1,1]]
for args in invalid:assert subprocess.run([a.probe,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode==2
assert all(a['roofline_ps']<=b['roofline_ps'] for a,b in zip(rows,rows[1:]));assert rows[3]['memory_ps']>rows[3]['compute_ps'] and rows[4]['memory_ps']<rows[4]['compute_ps']
with (a.out/'token-latency.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(a.out/'status.json').write_text(json.dumps(dict(status='PASS',positive_cases=len(rows)+7,negative_cases=len(invalid),integer_boundary=[19,20]),indent=2)+'\n')
print('PASS independent model oracle, monotonicity, zero, units, invalid and overflow')
