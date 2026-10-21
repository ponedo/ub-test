"""Durable host-only liveness sample; never touches simulator/native state."""
import datetime
import os
from pathlib import Path
import time
import psutil
from common import write


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def process_identity(process):
    pid = process.pid
    try:
        namespace = os.readlink('/proc/' + str(pid) + '/ns/pid')
    except OSError:
        namespace = None
    return dict(pid=pid, ppid=process.ppid(), start_time_unix=process.create_time(),
                pid_namespace=namespace, session_id=os.getsid(pid),
                command=process.cmdline())


class Heartbeat:
    def __init__(self, out, command):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.driver = psutil.Process(os.getpid())
        self.driver_identity = process_identity(self.driver)
        self.command = list(map(str, command))
        self.started = now()
        self.monotonic_start = time.monotonic()
        self.observed = {}
        self.error = None
        self.last_sample = 0

    def sample(self, status):
        current, tree_rss = [], 0
        # The accepted guard creates one direct child as a new session leader.
        # No PID/name search outside this driver's own descendant tree is used.
        for process in self.driver.children(recursive=True):
            try:
                identity = process_identity(process)
                identity['rss_bytes'] = process.memory_info().rss
                identity['last_seen_utc'] = now()
                identity['direct_owned_stage'] = identity['ppid'] == self.driver.pid and identity['session_id'] == process.pid
                self.observed[(process.pid, identity['start_time_unix'])] = identity
                current.append(identity)
                tree_rss += identity['rss_bytes']
            except (psutil.Error, ProcessLookupError, PermissionError):
                pass
        write(self.out / 'host-heartbeat.json', dict(
            status=status, started_utc=self.started, last_sample_utc=now(),
            elapsed_seconds=time.monotonic() - self.monotonic_start,
            driver=self.driver_identity, requested_command=self.command,
            current_owned_processes=current, observed_owned_processes=list(self.observed.values()),
            current_tree_rss_bytes=tree_rss,
            note='A stale RUNNING sample is uncertain execution, never permission to rerun.'))

    def tick(self):
        if time.monotonic() - self.last_sample < 1:
            return
        try:
            self.sample('RUNNING')
            self.last_sample = time.monotonic()
        except Exception as exc:
            self.error = repr(exc)

    def start(self):
        self.sample('STARTING')

    def stop(self, status):
        self.sample(status)
