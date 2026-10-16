#!/usr/bin/env python3
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
from guard import run
H=Path(__file__).resolve().parent;REPO=H.parents[1];WORK=REPO.parent;RAW=WORK/'prefill-cpu-raw';STAGE=H.parent/'prefill-capacity/stage.py';SCALES=[5000,10000,20000,50000]
def env():
 return {'PATH':os.path.dirname(sys.executable)+':/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','HOME':str(RAW/'home'),'RELAY_GRAPH_TOOL':str(RAW/'aux/graph-tool'),'LD_LIBRARY_PATH':str(RAW/'baseline-binaries/lib')}
def hashes(root):
 d={}
 for p in sorted(root.rglob('*')):
  if p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    while b:=f.read(1024*1024):h.update(b)
   d[str(p.relative_to(root))]=h.hexdigest()
 return d
def execute(A,variant):
 ledger=H/'evidence/run-ledger.json';rows=json.loads(ledger.read_text()) if ledger.exists() else [];common=RAW/f'common-{A}';case=RAW/f'{A}-{variant}'
 def save():ledger.write_text(json.dumps(rows,indent=2)+'\n')
 if any(x['assignments']==A and x['variant']==variant for x in rows):raise RuntimeError('Existing ledger row; use fresh evidence and raw directories')
 if case.exists():raise RuntimeError('Refuse overwriting '+str(case))
 if not common.exists():
  common.mkdir(parents=True)
  for stage in ['generate','planner','adapter']:
   r=run([sys.executable,STAGE,stage,'--case',common,'--assignments',str(A),'--mode','no-balancing'],common/'stages'/stage,300,cwd=REPO,case=common,env=env())
   if r['status']!='PASS':raise RuntimeError('preparation failure')
 case.mkdir();shutil.copytree(common/'run',case/'run');row=dict(assignments=A,variant=variant,status='running',input_hashes=hashes(case/'run'),stages={});rows.append(row);save()
 binary=RAW/'baseline-binaries/ns3.44-multi-npu-relay' if variant!='timed' else WORK/'prefill-cpu-native/build/scratch/ns3.44-multi-npu-relay'
 cmd=[binary,'--input='+str(case/'run/input.txt'),'--out='+str(case/'run'),'--capacityMetrics='+str(case/'run/simulator-metrics.json')];en=env()
 if variant=='sampled':cmd=[H/'record',case/'perf.data','99','--']+cmd
 if variant=='timed':en.update(LD_LIBRARY_PATH=str(WORK/'prefill-cpu-native/build/lib'),NATIVE_CPU_PROFILE='1',NATIVE_CPU_PROFILE_OUT=str(case/'timing.tsv'))
 for stage,command in [('ns3',cmd),('verify',[sys.executable,STAGE,'verify','--case',case])]:
  r=run(command,case/'stages'/stage,600,cwd=REPO,case=case,env=en);row['stages'][stage]=r;save()
  if r['status']!='PASS':row.update(status='failed',failed_stage=stage);save();raise RuntimeError(f'{A} {variant} {stage} failure')
 row.update(status='success',file_hashes=hashes(case/'run'));save()
 baseline=next((x for x in rows if x['assignments']==A and x['variant']=='baseline'),None)
 if baseline and variant!='baseline':
  row['all_output_files_byte_identical']=baseline['file_hashes']==row['file_hashes'];save()
  if not row['all_output_files_byte_identical']:raise RuntimeError('output parity failure')
 print('COMPLETE',A,variant,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--assignments',type=int,choices=SCALES,required=True);p.add_argument('--variant',choices=['baseline','sampled','timed'],required=True);a=p.parse_args();execute(a.assignments,a.variant)
