#!/usr/bin/env python3
"""Read-only host observations and bounded, sequential process-group execution."""
import csv,datetime,json,os,resource,signal,subprocess,time,shutil
from pathlib import Path
import psutil
G=1024**3

def snapshot():
 def read(p):
  try:return Path(p).read_text()
  except OSError:return None
 return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),uname=list(os.uname()),cpu_affinity=os.sched_getaffinity(0) and sorted(os.sched_getaffinity(0)),cpuinfo=read('/proc/cpuinfo'),meminfo=read('/proc/meminfo'),cgroup_memory_max=read('/sys/fs/cgroup/memory.max'),cgroup_cpu_max=read('/sys/fs/cgroup/cpu.max'),perf_event_paranoid=read('/proc/sys/kernel/perf_event_paranoid'),disk_free=shutil.disk_usage(Path.cwd()).free)

def run(cmd,out,wall=600,cwd=None,case=None,env=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);case=Path(case or out);before=snapshot();start=time.monotonic();reason=None;peak=0;samples=[];max_threads=0
 def limits():resource.setrlimit(resource.RLIMIT_AS,(7*G,7*G))
 with (out/'console.txt').open('w') as f:
  child=subprocess.Popen([str(x) for x in cmd],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
  while True:
   pid,status,usage=os.wait4(child.pid,os.WNOHANG)
   if pid:child.returncode=os.waitstatus_to_exitcode(status);break
   elapsed=time.monotonic()-start
   procs=[]
   try:
    root=psutil.Process(child.pid);procs=[root]+root.children(recursive=True);rss=sum(p.memory_info().rss for p in procs if p.is_running())
   except psutil.Error:rss=0
   for process in procs:
    try:max_threads=max(max_threads,process.num_threads())
    except psutil.Error:pass # A child can exit between enumeration and observation.
   peak=max(peak,rss);mem=psutil.virtual_memory();free=shutil.disk_usage(case).free;samples.append([round(elapsed,3),rss,mem.available,free])
   if not reason:
    if elapsed>wall:reason='wall_guard'
    elif rss>6*G:reason='tree_rss_guard'
    elif mem.available<1536*1024**2:reason='host_available_memory_guard'
    elif free<8*G:reason='disk_free_guard'
    elif shutil.disk_usage('/tmp').free<2*G:reason='tmp_disk_free_guard'
    if reason:
     try:os.killpg(child.pid,signal.SIGTERM)
     except ProcessLookupError:pass
     stop=time.monotonic()
   elif time.monotonic()-stop>2:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   time.sleep(.25)
 result=dict(command=[str(x) for x in cmd],cwd=str(cwd or Path.cwd()),start=before['utc'],wall_seconds=time.monotonic()-start,returncode=child.returncode,status='PASS' if child.returncode==0 and not reason else 'FAIL',guard=reason,peak_rss_kib=usage.ru_maxrss,sampled_peak_tree_rss_bytes=peak,max_observed_threads_per_process=max_threads,user_cpu_seconds=usage.ru_utime,system_cpu_seconds=usage.ru_stime,limits=dict(wall_seconds=wall,tree_rss_bytes=6*G,min_host_available_bytes=1536*1024**2,address_space_bytes=7*G,min_disk_free_bytes=8*G,min_tmp_disk_free_bytes=2*G),host_before=before,host_after=snapshot())
 (out/'resource.json').write_text(json.dumps(result,indent=2)+'\n')
 with (out/'resource-samples.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['elapsed_seconds','tree_rss_bytes','host_available_bytes','disk_free_bytes']);w.writerows(samples)
 print(out, result['status'],round(result['wall_seconds'],2),result['peak_rss_kib'],reason,flush=True);return result
