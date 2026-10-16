#!/usr/bin/env python3
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
H=Path(__file__).resolve().parent;REPO=H.parents[1];sys.path.insert(0,str(H.parent/'prefill-capacity'))
from guard import run
S=H.parent/'prefill-capacity/stage.py';RAW=Path('/workspace/prefill-cpu-raw');PERF=Path('/workspace/prefill-cpu-tools/root/usr/bin/perf');LIB=PERF.parents[1]/'lib/x86_64-linux-gnu'
VARIANTS=['baseline','perf','timed'];SCALES=[5000,10000,20000,50000]
def commands(A,v):
 case=RAW/f'{A}-{v}';native='/workspace/prefill-cpu-native' if v=='timed' else '/workspace/ns-3-ub'
 cmd=[native+'/build/scratch/ns3.44-multi-npu-relay','--input='+str(case/'run/input.txt'),'--out='+str(case/'run'),'--capacityMetrics='+str(case/'run/simulator-metrics.json')]
 if v=='perf':cmd=['env','LD_LIBRARY_PATH='+str(LIB),str(PERF),'record','-o',str(case/'perf.data'),'-e','cpu-clock:u','-F','99','--call-graph','dwarf,8192','--']+cmd
 if v=='timed':cmd=['env','CPU_SCOPE_OUTPUT='+str(case/'scopes.csv')]+cmd
 return cmd
def init():
 if any((RAW/f'common-{a}').exists() for a in SCALES):raise RuntimeError('preserve existing raw evidence; use a fresh workspace for reproduction')
 rows=[]
 for A in SCALES:
  for v in VARIANTS:
   cid=f'{A}-{v}';rows.append(dict(id=cid,assignments=A,variant=v,status='pending',command=commands(A,v)))
   p=H/'cases'/cid;p.mkdir(parents=True,exist_ok=True);(p/'experiment-spec.md').write_text(f'# {cid}\n\nSee ../../experiment-plan.md for fixed configuration and checkpoint. A={A}; T={A//8}; variant={v}. Raw directory {RAW/cid}. NoBalance only.\n')
 (H/'matrix.yaml').write_text(json.dumps(rows,indent=2)+'\n')
 (H/'command-manifest.yaml').write_text(json.dumps({'driver':'python3 experiments/prefill-cpu-profiling/execute.py --assignments A','preparation':['generate','planner','adapter'],'cases':rows,'verification':'accepted stage.py verify --case CASE','guards':'experiment-plan.md'},indent=2)+'\n')
 (H/'evidence/run-ledger.json').write_text(json.dumps(rows,indent=2)+'\n');(H/'run-ledger.md').write_text('# Run ledger\n\nMachine-readable commands, timestamps, stage costs and status: evidence/run-ledger.json. Initialized before first simulation.\n')
def hashes(root):
 result={}
 for p in sorted(root.rglob('*')):
  if p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    while b:=f.read(1024*1024):h.update(b)
   result[str(p.relative_to(root))]=h.hexdigest()
 return result
def execute(A):
 ledgerpath=H/'evidence/run-ledger.json';rows=json.loads(ledgerpath.read_text());common=RAW/f'common-{A}'
 def save():ledgerpath.write_text(json.dumps(rows,indent=2)+'\n')
 if common.exists():raise RuntimeError('preserve existing common case')
 common.mkdir(parents=True)
 for stage in ['generate','planner','adapter']:
  r=run([sys.executable,str(S),stage,'--case',str(common),'--assignments',str(A),'--mode','no-balancing'],common/'stages'/stage,180,cwd=REPO,case=common)
  if r['status']!='PASS':raise RuntimeError(r)
 for v in VARIANTS:
  row=next(x for x in rows if x['id']==f'{A}-{v}');assert row['status']=='pending';case=RAW/row['id'];assert not case.exists();case.mkdir();shutil.copytree(common/'run',case/'run');row.update(status='running',stages={});save()
  for stage,cmd,wall in [('ns3',commands(A,v),600 if v=='baseline' else 900),('verify',[sys.executable,str(S),'verify','--case',str(case)],300)]:
   r=run(cmd,case/'stages'/stage,wall,cwd=REPO,case=case);row['stages'][stage]=r;save()
   if r['status']!='PASS':row.update(status='failed',failed_stage=stage);save();raise RuntimeError(row['id']+' '+stage+' failed')
  row['file_hashes']=hashes(case/'run');row['status']='success';save()
 ref=next(x for x in rows if x['id']==f'{A}-baseline')['file_hashes'];parity={v:next(x for x in rows if x['id']==f'{A}-{v}')['file_hashes']==ref for v in VARIANTS};(H/'evidence'/f'parity-{A}.json').write_text(json.dumps(parity,indent=2)+'\n');assert all(parity.values()),parity
 print('FULL FILE PARITY',A,parity,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--assignments',type=int,choices=SCALES);a=p.parse_args()
 if a.init:init()
 if a.assignments:execute(a.assignments)
