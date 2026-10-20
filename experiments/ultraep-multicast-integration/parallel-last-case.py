#!/usr/bin/env python3
"""Explicit two-process continuation: preserve running Chunk, admit only v2."""
import argparse,datetime,hashlib,json,shutil,sys,time
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();b=a.build.resolve();x=json.loads((r/'ledger.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert [z['status'] for z in x['runs']]==['PASS','PASS','RUNNING','PREPARED'],'Only supported live handoff: Chunk running, v2 not started'
for path,digest in x['binary_identity'].items():assert sha(path)==digest
row=dict(x['runs'][3]);d=r/'multicast-v2'
for key,name in [('input_sha256','input.txt'),('config_sha256','config.json'),('plan_sha256','plan.json'),('assignments_sha256','assignments.csv')]:assert sha(d/name)==row[key],name
assert not (d/'simulator-host').exists()
# Stop the old sequential driver at its next binary identity gate. Renaming an
# executable preserves its inode/content and the running process's mappings.
held=b/'layer.parallel-admission-held';copy=b/'layer.parallel-identical';assert not held.exists() and not copy.exists();shutil.copy2(b/'layer',copy);assert sha(copy)==x['binary_identity'][str(b/'layer')]
(b/'layer').rename(held)
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='WAITING_MEMORY',max_parallel_simulators=2,per_process_tree_rss_bytes=6*1024**3,min_host_available_bytes=1536*1024**2,estimated_new_peak_bytes=3900248*1024,admission_margin_bytes=128*1024**2,binary_sha256=sha(copy),held_binary=str(held),identical_execution_binary=str(copy),reason='User requested parallel cases; avoid automatic third/duplicate launch while preserving running Chunk.')
receipt_path=r/'parallel-admission.json';receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
threshold=receipt['min_host_available_bytes']+receipt['estimated_new_peak_bytes']+receipt['admission_margin_bytes'];deadline=time.monotonic()+3600
while psutil.virtual_memory().available<threshold:
 if time.monotonic()>deadline:raise RuntimeError('Parallel admission memory wait protected stop')
 time.sleep(1)
receipt.update(status='ADMITTED',available_bytes_at_admission=psutil.virtual_memory().available,admitted_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
record=r/'multicast-parallel-result.json'
def save():record.write_text(json.dumps(row,indent=2)+'\n')
def stage(cmd,out):
 z=run(cmd,out,3600,case=r)
 if z['status']!='PASS':raise RuntimeError('Guard/nonzero stop: '+str(out))
 return z
row.update(status='RUNNING',execution_mode='overlaps_chunk_streaming',binary_identity=x['binary_identity']);save();print('START multicast-v2 parallel',flush=True)
try:
 row['simulator_host']=stage([copy,'--input='+str(d/'input.txt'),'--out='+str(d),'--capacityMetrics='+str(d/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],d/'simulator-host')
 row['postflight_host']=stage([sys.executable,H/'preflight.py',d,'--graph-tool',b/'graph-tool','--out',d/'postflight.json','--execution-summary',d/'online-summary.json'],d/'postflight-host')
 row['independent_host']=stage([sys.executable,H/'verify.py',d],d/'independent-host');row.update(status='PASS',summary=json.loads((d/'online-summary.json').read_text()),metrics=json.loads((d/'simulator-metrics.json').read_text()));save();print('VERIFIED multicast-v2 parallel',flush=True)
except Exception as e:row.update(status='STOPPED',failure=str(e));save();raise
# Root must wait for the sequential driver to exit before restoring the held
# executable and merging receipts. This script never restores it itself.
