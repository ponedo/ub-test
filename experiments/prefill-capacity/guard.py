#!/usr/bin/env python3
"""Bounded sequential process-group execution; no simulated-time changes."""
import argparse,csv,datetime,json,os,resource,signal,subprocess,time,shutil
from pathlib import Path
G=1024**3

def snapshot():
 c=Path('/sys/fs/cgroup')
 return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),memory_max=(c/'memory.max').read_text().strip(),memory_current=int((c/'memory.current').read_text()),memory_events=(c/'memory.events').read_text(),cpu_max=(c/'cpu.max').read_text().strip(),pids_max=(c/'pids.max').read_text().strip(),disk_free=shutil.disk_usage('/workspace').free,tmp_disk_free=shutil.disk_usage('/tmp').free,proc_meminfo=Path('/proc/meminfo').read_text())
def tree(pid):
 members={pid};stats={}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   lines=(p/'status').read_text().splitlines();d={x.split(':',1)[0]:x.split(':',1)[1].strip() for x in lines if ':' in x};stats[int(p.name)]=(int(d['PPid']),int(d.get('VmRSS','0 kB').split()[0])*1024)
  except (OSError,ValueError,KeyError):continue
 changed=True
 while changed:
  old=len(members);members.update(p for p,(parent,_) in stats.items() if parent in members);changed=len(members)!=old
 return sum(stats.get(p,(0,0))[1] for p in members),len(members)
def disk_bytes(root):return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())
def run(cmd,out,wall=300,cwd=None,case=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);case=Path(case or out);before=snapshot();start=time.monotonic();reason=None;peak=0;peakcg=0;samples=[];lastdisk=-10;size=0
 def limits():resource.setrlimit(resource.RLIMIT_AS,(12*G,12*G))
 with (out/'console.txt').open('w') as f:
  child=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
  while True:
   pid,status,usage=os.wait4(child.pid,os.WNOHANG)
   if pid:child.returncode=os.waitstatus_to_exitcode(status);break
   elapsed=time.monotonic()-start;rss,n=tree(child.pid);cg=int(Path('/sys/fs/cgroup/memory.current').read_text());peak=max(peak,rss);peakcg=max(peakcg,cg)
   if elapsed-lastdisk>=5:size=disk_bytes(case);lastdisk=elapsed
   free=shutil.disk_usage('/workspace').free;samples.append([round(elapsed,3),rss,cg,n,size,free])
   if not reason:
    if elapsed>wall:reason='wall_guard'
    elif rss>8*G:reason='process_tree_rss_guard'
    elif cg>12*G:reason='cgroup_memory_guard'
    elif free<8*G:reason='disk_free_guard'
    elif shutil.disk_usage('/tmp').free<2*G:reason='tmp_disk_free_guard'
    elif size>6*G:reason='case_disk_guard'
    if reason:os.killpg(child.pid,signal.SIGTERM);stop=time.monotonic()
   elif time.monotonic()-stop>2:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   time.sleep(.5)
 result=dict(command=cmd,cwd=str(cwd or Path.cwd()),start=before['utc'],wall_seconds=time.monotonic()-start,returncode=child.returncode,status='PASS' if child.returncode==0 and not reason else 'FAIL',guard=reason,peak_rss_kib=usage.ru_maxrss,sampled_peak_tree_rss_bytes=peak,sampled_peak_cgroup_bytes=peakcg,user_cpu_seconds=usage.ru_utime,system_cpu_seconds=usage.ru_stime,final_case_bytes=disk_bytes(case),limits=dict(wall_seconds=wall,tree_rss_bytes=8*G,cgroup_bytes=12*G,address_space_bytes=12*G,case_disk_bytes=6*G,min_disk_free_bytes=8*G,min_tmp_disk_free_bytes=2*G),host_before=before,host_after=snapshot())
 (out/'resource.json').write_text(json.dumps(result,indent=2)+'\n')
 with (out/'resource-samples.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['elapsed_seconds','tree_rss_bytes','cgroup_memory_bytes','process_count','case_bytes_last_scan','disk_free_bytes']);w.writerows(samples)
 print(out.name,result['status'],round(result['wall_seconds'],2),result['peak_rss_kib'],reason,flush=True);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--wall',type=int,default=300);p.add_argument('--cwd');p.add_argument('--case');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();r=run(a.command[1:] if a.command[:1]==['--'] else a.command,a.out,a.wall,a.cwd,a.case);raise SystemExit(r['status']!='PASS')
