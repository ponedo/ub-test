"""One coordinator; peak-aware admission, maximum two cases, no blind four-way run."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import psutil
from common import WINDOWS, REAL_STRATEGIES, check, sha, write

G = 1024 ** 3
H = Path(__file__).resolve().parent
HISTORICAL_PEAK = {'chunk-streaming': 3754704 * 1024, 'multicast-v2': 3869304 * 1024}


def estimate(row):
    # Unknown larger-window high-water memory is not assumed equal to 512.
    # Reserve the entire retained 6 GiB RSS allowance for an unmeasured treatment.
    if row['window'] != 512:
        return 6 * G
    return int(HISTORICAL_PEAK[row['strategy']] * 1.05) + 128 * 1024 ** 2


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def rss(process):
    try:
        parent = psutil.Process(process.pid)
        return sum(child.memory_info().rss for child in [parent] + parent.children(recursive=True) if child.is_running())
    except psutil.Error:
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    root, build = args.root.resolve(), args.build.resolve()
    ledger = json.loads((root / 'ledger.json').read_text())
    assert ledger['status'] == 'PREPARED'
    assert [(row['window'], row['strategy']) for row in ledger['runs']] == [(window, strategy) for window in WINDOWS for strategy in REAL_STRATEGIES]
    assert all(row['allocator'] == 'original' for row in ledger['runs'])
    for process in psutil.process_iter(['pid', 'name']):
        if process.pid != os.getpid() and process.info['name'] in ['layer', 'parent-layer', 'pair-layer']:
            raise RuntimeError('Existing simulator visible; require resource review before admission')
    pending = list(ledger['runs'])
    active = {}
    events, observations = [], []
    started = time.monotonic()
    idle_since = None
    failed = False

    def interrupted(signum, frame):
        raise RuntimeError('Coordinator signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)

    def save(status='RUNNING'):
        write(root / 'ledger.json', ledger)
        write(root / 'parallel-resource-record.json', dict(status=status, reserve_bytes=G, max_parallel=2, admission_margin_bytes=128 * 1024 ** 2, historical_peak_bytes=HISTORICAL_PEAK, treatment_estimate_bytes=6 * G, treatment_estimate_reason='Full retained RSS allowance until a larger-window peak is measured; no optimistic extrapolation', events=events))

    def stop_owned(reason):
        nonlocal failed
        failed = True
        for case_id, (row, process, log) in list(active.items()):
            try:
                parent = psutil.Process(process.pid)
                owned = [parent] + parent.children(recursive=True)
            except psutil.Error:
                owned = []
            for child in reversed(owned):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            _, alive = psutil.wait_procs(owned, timeout=3)
            for child in alive:
                try:
                    child.kill()
                except psutil.Error:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            log.close()
            result_path = root / case_id / 'run-result.json'
            try:
                result = json.loads(result_path.read_text()) if result_path.exists() else dict(row)
            except (OSError, ValueError):
                result = dict(row)
            if result.get('status') != 'PASS':
                result.update(status='CANCELLED', failure=reason)
                write(result_path, result)
            ledger['runs'][next(i for i, candidate in enumerate(ledger['runs']) if candidate['case_id'] == case_id)] = result
            events.append(dict(event='cancelled', case_id=case_id, utc=now(), reason=reason))
        active.clear()
        for row in pending:
            row.update(status='NOT_RUN', reason='Admission stopped after: ' + reason)
        ledger.update(status='STOPPED', failure=reason)
        save('STOPPED')

    ledger['status'] = 'RUNNING'
    save()
    try:
        while pending or active:
            if time.monotonic() - started > len(ledger['runs']) * (4800 + 600):
                raise RuntimeError('Coordinator bounded runtime exceeded')
            for case_id, (row, process, log) in list(active.items()):
                result_code = process.poll()
                if result_code is None:
                    continue
                log.close()
                result_path = root / case_id / 'run-result.json'
                result = json.loads(result_path.read_text()) if result_path.exists() else dict(row, status='FAIL', failure='Driver exited without run-result.json')
                events.append(dict(event='finished', case_id=case_id, utc=now(), returncode=result_code, status=result['status']))
                index = next(i for i, candidate in enumerate(ledger['runs']) if candidate['case_id'] == case_id)
                ledger['runs'][index] = result
                del active[case_id]
                if result_code or result['status'] != 'PASS':
                    raise RuntimeError('Case failed: ' + case_id)
                save()
            memory = psutil.virtual_memory()
            current = {case_id: rss(process) for case_id, (row, process, log) in active.items()}
            future = sum(max(0, estimate(row) - current[case_id]) for case_id, (row, process, log) in active.items())
            cpu, load, cores = psutil.cpu_percent(interval=None), os.getloadavg()[0], len(os.sched_getaffinity(0))
            observations.append([time.monotonic() - started, memory.available, cpu, load, dict(current)])
            if pending and len(active) < 2:
                row = pending[0]
                # Both baseline reruns must pass before any treatment begins.
                baseline_complete = all(item['status'] == 'PASS' for item in ledger['runs'] if item['window'] == 512)
                gate = row['window'] == 512 or baseline_complete
                required = estimate(row) + G + 128 * 1024 ** 2 + future
                if gate and memory.available >= required and shutil.disk_usage(root).free >= 8 * G and shutil.disk_usage('/tmp').free >= 2 * G and load <= cores and cpu < 90:
                    case_id = row['case_id']
                    log = (root / (case_id + '-driver.log')).open('w')
                    process = subprocess.Popen([sys.executable, H / 'run-case.py', root, case_id, '--build', build], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    events.append(dict(event='admitted', case_id=case_id, utc=now(), host_available=memory.available, required_available=required, predicted_peak_bytes=estimate(row), concurrent=list(active), host_cpu_percent=cpu, load1=load))
                    active[case_id] = (row, process, log)
                    pending.pop(0)
                    save()
            if pending and not active:
                if idle_since is None:
                    idle_since = time.monotonic()
                if time.monotonic() - idle_since > 600:
                    raise RuntimeError('Resource admission unavailable; stopped without weakening any guard')
            else:
                idle_since = None
            if len(observations) % 60 == 0:
                write(root / 'parallel-resource-samples.json', observations)
            if active:
                time.sleep(1)
            elif pending:
                time.sleep(5)
        assert not failed
        assert all(row['status'] == 'PASS' for row in ledger['runs'])
        assert len({row['summary']['combine_fnv1a64'] for row in ledger['runs']}) == 1
        for identity in ledger['identities'].values():
            check(identity)
        for row in ledger['runs']:
            check(row['immutable_files'])
            check(row['baseline_identity'])
        assert sha(ledger['stage_a_path']) == ledger['stage_a_sha256']
        assert sha(ledger['a_decision_path']) == ledger['a_decision_sha256']
        write(root / 'identity-after.json', json.loads((root / 'identity-before.json').read_text()))
        ledger['status'] = 'PASS'
        save('PASS')
        print('PASS six private independent 3136 Gbps ablation cases; A remains stopped', flush=True)
    except BaseException as exc:
        stop_owned(str(exc))
        raise
    finally:
        write(root / 'parallel-resource-samples.json', observations)


if __name__ == '__main__':
    main()
