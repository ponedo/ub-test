"""Accepted resource guard, with harness-only interruption ownership cleanup.

Numerical limits and sampling logic remain in unchanged accepted guard.py.
The wrapper ensures its start_new_session child is not orphaned on exceptions
or direct SIGINT/SIGTERM. Only process groups created by this invocation stop.
"""
import importlib.util,json,os,signal,subprocess,time,types
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'qwen-roofline-compute/guard.py'
s=importlib.util.spec_from_file_location('accepted_roofline_guard',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
snapshot=m.snapshot

def run(cmd,out,wall=600,cwd=None,case=None,env=None):
    owned=[]
    def start(*args,**kwargs):
        child=subprocess.Popen(*args,**kwargs);owned.append(child);return child
    original=m.subprocess
    m.subprocess=types.SimpleNamespace(Popen=start,STDOUT=subprocess.STDOUT)
    previous={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
    def interrupted(signum,frame):
        raise InterruptedError('guard received signal '+str(signum))
    for sig in previous:signal.signal(sig,interrupted)
    try:
        return m.run(cmd,out,wall,cwd,case,env)
    except BaseException as exc:
        directory=Path(out);directory.mkdir(parents=True,exist_ok=True)
        (directory/'interruption-resource.json').write_text(json.dumps(dict(status='STOPPED',reason=repr(exc),owned_process_groups=[x.pid for x in owned],limits=dict(wall_seconds=wall,tree_rss_bytes=6*1024**3,min_host_available_bytes=1024**3,address_space_bytes=7*1024**3,min_disk_free_bytes=8*1024**3,min_tmp_disk_free_bytes=2*1024**3)),indent=2)+'\n')
        raise
    finally:
        # The root may exit while descendants remain, including on a normal
        # guard timeout or nominal success. Always clean our session groups.
        for sig in previous:signal.signal(sig,signal.SIG_IGN)
        for child in owned:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            if child.returncode is None:
                try:child.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            if child.returncode is None:child.wait(timeout=5)
        m.subprocess=original
        for sig,handler in previous.items():signal.signal(sig,handler)
