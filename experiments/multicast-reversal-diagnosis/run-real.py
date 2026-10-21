"""Single coordinator, independent per-case files, bounded peak-aware two-process admission."""
import argparse,datetime,json,os,psutil,subprocess,sys,time,signal,shutil
from pathlib import Path
import os
if not __debug__ or os.environ.get('PYTHONOPTIMIZE'):
 raise RuntimeError('Python optimization is forbidden: all validation assertions must execute')
H=Path(__file__).resolve().parent;G=1024**3
def interrupted(signum,frame):raise RuntimeError('coordinator signal '+str(signum))
signal.signal(signal.SIGTERM,interrupted)
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);a=p.parse_args();r=a.root.resolve();b=a.build.resolve();ledger=json.loads((r/'ledger.json').read_text());assert ledger['status']=='PREPARED';assert [x['strategy'] for x in ledger['runs']]==['chunk-streaming','multicast-v2']
peaks={'chunk-streaming':3710516*1024,'multicast-v2':3832716*1024};diagnostic_extra=128*1024**2;pending=list(peaks);active={};events=[];observations=[];failed=False;start=time.monotonic();idle_since=None;reserve=G
for process in psutil.process_iter(['pid','name','cmdline']):
 if process.pid!=os.getpid() and process.info['name'] in ['layer','parent-layer','pair-layer']:raise RuntimeError('Existing simulator visible; require resource review before admission')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def rss(p):
 try:return sum(q.memory_info().rss for q in [psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True) if q.is_running())
 except psutil.Error:return 0
def save():
 (r/'parallel-resource-record.json').write_text(json.dumps(dict(status='FAIL' if failed else 'RUNNING',reserve_bytes=reserve,max_parallel=2,peak_margin_factor=1.05,admission_extra_bytes=128*1024**2,historical_peak_bytes=peaks,diagnostic_extra_per_process_bytes=diagnostic_extra,events=events),indent=2)+'\n')
ledger['status']='RUNNING';(r/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');save()
def stop_owned(reason):
 global failed
 failed=True
 for mode,(proc,log) in list(active.items()):
  try:owned=[psutil.Process(proc.pid)]+psutil.Process(proc.pid).children(recursive=True)
  except psutil.Error:owned=[]
  for q in reversed(owned):
   try:q.terminate()
   except psutil.Error:pass
  _,alive=psutil.wait_procs(owned,timeout=3)
  for q in alive:
   try:q.kill()
   except psutil.Error:pass
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
  log.close()
  path=r/mode/'run-result.json'
  try:result=json.loads(path.read_text()) if path.exists() else dict(strategy=mode)
  except (OSError,ValueError):result=dict(strategy=mode)
  if result.get('status')!='PASS':result.update(status='CANCELLED',failure=reason);path.write_text(json.dumps(result,indent=2)+'\n')
  ledger['runs'][list(peaks).index(mode)]=result
  events.append(dict(event='cancelled',mode=mode,utc=now(),reason=reason))
 active.clear()
 ledger.update(status='STOPPED',failure=reason);(r/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');save()
try:
 while pending or active:
  if time.monotonic()-start>10400:raise RuntimeError("coordinator bounded runtime exceeded")
  for mode,item in list(active.items()):
   proc,log=item;ret=proc.poll()
   if ret is None:continue
   log.close();result=json.loads((r/mode/'run-result.json').read_text());events.append(dict(event='finished',mode=mode,utc=now(),returncode=ret,status=result['status']));ledger['runs'][list(peaks).index(mode)]=result;del active[mode]
   if ret or result['status']!='PASS':failed=True;pending=[];raise RuntimeError('case failed: '+mode)
   (r/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');save()
  mem=psutil.virtual_memory();current={m:rss(p) for m,(p,f) in active.items()};future=sum(max(0,int(peaks[m]*1.05)+diagnostic_extra-current[m]) for m in active);cpu=psutil.cpu_percent(interval=None);load=os.getloadavg()[0];cores=len(os.sched_getaffinity(0))
  observations.append([time.monotonic()-start,mem.available,cpu,load,dict(current)])
  if pending and not failed and len(active)<2:
   mode=pending[0];need=int(peaks[mode]*1.05)+diagnostic_extra+reserve+128*1024**2+future
   if mem.available>=need and shutil.disk_usage(r).free>=8*G and shutil.disk_usage('/tmp').free>=2*G and load<=cores and cpu<90:
    f=(r/(mode+'-driver.log')).open('w');proc=subprocess.Popen([sys.executable,H/'run-case.py',r,mode,'--build',b],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);events.append(dict(event='admitted',mode=mode,utc=now(),host_available=mem.available,required_available=need,concurrent=list(active),host_cpu_percent=cpu,load1=load));active[mode]=(proc,f);pending.pop(0);save()
  if pending and not active:
   if idle_since is None:idle_since=time.monotonic()
   if time.monotonic()-idle_since>600:raise RuntimeError('resource admission unavailable; stop instead of indefinite waiting')
  else:idle_since=None
  if len(observations)%60==0:(r/'parallel-resource-samples.json').write_text(json.dumps(observations)+'\n')
  if active:time.sleep(1)
  elif pending:time.sleep(5)
 assert not failed,'A case failed; no further admissions'
 assert all(x['status']=='PASS' for x in ledger['runs']) and len({x['summary']['combine_fnv1a64'] for x in ledger['runs']})==1
 ledger['status']='PASS';(r/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');save();pr=json.loads((r/'parallel-resource-record.json').read_text());pr['status']='PASS';(r/'parallel-resource-record.json').write_text(json.dumps(pr,indent=2)+'\n')
 # Host resource samples contain no routing or payload.
 (r/'parallel-resource-samples.json').write_text(json.dumps(observations)+'\n');print('PASS two private diagnostic 3136 Gbps roofline strategies')
except BaseException as exc:
 stop_owned(str(exc))
 raise
finally:
 (r/'parallel-resource-samples.json').write_text(json.dumps(observations)+'\n')

