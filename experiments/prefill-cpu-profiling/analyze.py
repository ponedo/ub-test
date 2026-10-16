#!/usr/bin/env python3
import argparse,collections,csv,json,os,re,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent; RAW=Path('/workspace/prefill-cpu-raw');TOOLS=Path('/workspace/prefill-cpu-tools');PERF=TOOLS/'root/usr/bin/perf';ENV=os.environ|{'LD_LIBRARY_PATH':str(TOOLS/'root/usr/lib/x86_64-linux-gnu')}
def perf(args,path):
 with path.open('w') as f:subprocess.run([str(PERF)]+args,env=ENV,stdout=f,stderr=subprocess.STDOUT,check=True)
def analyze(A):
 case=RAW/f'{A}-perf';out=H/'evidence'/str(A);out.mkdir(exist_ok=True)
 perf(['report','--stdio','--header','--no-children','--call-graph','none','--percent-limit','0','-i',str(case/'perf.data')],out/'perf-report.txt')
 perf(['report','--stdio','--no-children','--call-graph','none','--show-nr-samples','--show-total-period','--sort','symbol,dso','--percent-limit','0','-i',str(case/'perf.data')],out/'perf-symbols.txt')
 perf(['script','-i',str(case/'perf.data')],case/'perf-script.txt')
 perf(['report','--stdio','--header-only','-i',str(case/'perf.data')],out/'perf-header.txt')
 frames=[];self_counts=collections.Counter();inclusive=collections.Counter();n=0;unknown=0;depth=[]
 for block in (case/'perf-script.txt').read_text().split('\n\n'):
  if 'cpu-clock:u:' not in block:continue
  stack=[]
  for line in block.splitlines()[1:]:
   m=re.match(r'\s+[0-9a-f]+ (.+) \((.+)\)$',line)
   if m:stack.append(re.sub(r'\+0x[0-9a-f]+$','',m[1]))
  if not stack:continue
  n+=1;self_counts[stack[0]]+=1;inclusive.update(set(stack));depth.append(len(stack));unknown+=stack[0]=='[unknown]'
 rows=[dict(symbol=s,samples=c,percent=100*c/n) for s,c in self_counts.most_common()]
 (out/'sample-summary.json').write_text(json.dumps(dict(samples=n,unknown_leaf=unknown,mean_depth=sum(depth)/n,top20=rows[:20],all_self=rows,inclusive_stack_samples=dict(inclusive)),indent=2)+'\n')
 with (out/'top20.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['symbol','samples','percent'],lineterminator='\n');w.writeheader();w.writerows(rows[:20])
 with (case/'perf-script.txt').open() as inp,(out/'stacks.folded').open('w') as f:subprocess.run(['perl',str(TOOLS/'FlameGraph/stackcollapse-perf.pl')],stdin=inp,stdout=f,check=True)
 with (out/'stacks.folded').open() as inp,(out/'flame.svg').open('w') as f:subprocess.run(['perl',str(TOOLS/'FlameGraph/flamegraph.pl'),'--title',f'NoBalance A={A}, original O3, cpu-clock:u 99Hz','--countname','samples'],stdin=inp,stdout=f,check=True)
 names=json.loads((H/'evidence/scopes.json').read_text());timing=[]
 for r in csv.DictReader((RAW/f'{A}-timed/scopes.csv').open()):timing.append(dict(name=names[r['id']],calls=int(r['calls']),inclusive_seconds=int(r['inclusive_ns'])/1e9,exclusive_seconds=int(r['exclusive_ns'])/1e9,cpu_inclusive_seconds=int(r['cpu_inclusive_ns'])/1e9 if int(r['id']) in [0,1,2,8,9,10,11] else None,cpu_exclusive_seconds=int(r['cpu_exclusive_ns'])/1e9 if int(r['id']) in [0,1,2,8,9,10,11] else None,rss_highwater_kib=int(r['rss_highwater_kib']) if int(r['id']) in [0,1,2,8,9,10,11] else None))
 present={r['name'] for r in timing}
 for name in names.values():
  if name not in present:timing.append(dict(name=name,calls=0,inclusive_seconds=0.0,exclusive_seconds=0.0,cpu_inclusive_seconds=None,cpu_exclusive_seconds=None,rss_highwater_kib=None))
 (out/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
 print(A,'samples',n,'Top5',rows[:5],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('assignments',type=int);a=p.parse_args();analyze(a.assignments)
