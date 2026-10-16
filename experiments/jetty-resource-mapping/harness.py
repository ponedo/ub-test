#!/usr/bin/env python3
"""Explicit, sequential A/B/C runner. Does nothing until invoked with --execute."""
import argparse
import csv
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PROFILING = HERE.parent / 'prefill-cpu-profiling'
SCALES = (5000, 10000, 20000, 50000, 100000)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(Path(root).rglob('*')) if p.is_file()}

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def append(raw, event):
    event = dict(utc=utc(), **event)
    with (raw / 'run-ledger.jsonl').open('a') as f:
        f.write(json.dumps(event, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    with (raw / 'run-ledger.md').open('a') as f:
        f.write('- ' + json.dumps(event, sort_keys=True) + '\n')

def read_attempt(path):
    return json.loads((Path(path) / 'attempt.json').read_text())

def logical(root):
    root = Path(root)
    summary = json.loads((root / 'summary.json').read_text())
    keys = ['npus','tokens','assignments','weight_WQEs','weight_TAs','weight_send_bytes_per_npu',
            'combine_sha256','replicas','max_npu_load','per_npu_load','weight_bytes','verified_bytes',
            'remote_bytes','local_bytes','target_segments','remote_WQEs']
    invariants = {k: summary[k] for k in keys}
    # Ordering and timestamps can change with Jetty reuse; multiplicities and identities cannot.
    # Bounded-memory commutative digest: SHA256-derived sum and squared sum plus
    # cardinality preserve order independence and duplicate multiplicity. This is
    # supporting parity evidence; the independent strict verifier is the oracle.
    count = total = squares = 0
    modulus = 2**521 - 1
    with (root / 'events.csv').open() as f:
        for row in csv.DictReader(f):
            item = tuple(sorted((k,v) for k,v in row.items() if k != 'time_ps'))
            value = int.from_bytes(hashlib.sha256(json.dumps(item).encode()).digest(),'big')
            count += 1
            total = (total + value) % modulus
            squares = (squares + value * value) % modulus
    invariants['event_multiset_digest'] = dict(count=count,sha256_sum=hex(total),sha256_squared_sum=hex(squares))
    for name in ('executed-transfers.csv','received-payloads.bin','payload-index.csv'):
        invariants[name] = sha(root / name)
    metrics = json.loads((root / 'simulator-metrics.json').read_text())
    invariants['simulator_counts'] = {k: metrics[k] for k in ('assignments','tasks','remote_WQEs','sender_completions','completed_tokens')}
    return invariants

def parity(a, b, mode):
    ar, br = Path(a) / 'run', Path(b) / 'run'
    ah, bh = hashes(ar), hashes(br)
    changed = sorted(k for k in ah.keys() | bh.keys() if ah.get(k) != bh.get(k))
    result = dict(mode=mode, a=str(a), b=str(b), a_files=len(ah), b_files=len(bh), differing_files=changed)
    if mode == 'bytewise':
        result['pass'] = len(ah) == len(bh) == 398 and not changed
    else:
        av, bv = logical(ar), logical(br)
        result['differing_invariants'] = [k for k in av.keys() | bv.keys() if av.get(k) != bv.get(k)]
        result['pass'] = not result['differing_invariants']
        result['latency_ps'] = [json.loads((p / 'summary.json').read_text())['layer_latency_ps'] for p in (ar,br)]
    return result

def freeze(binary, lib, raw, arm):
    source = {'binary': sha(binary), 'libraries': hashes(lib)}
    dest = raw / 'frozen' / arm
    manifest = dest / 'manifest.json'
    if dest.exists():
        old = json.loads(manifest.read_text())
        if old['source_hashes'] != source:
            raise ValueError('Binary/library identity changed; use a fresh raw root')
        if sha(dest / binary.name) != source['binary'] or hashes(dest / 'lib') != source['libraries']:
            raise ValueError('Frozen ELF files changed')
        return dest / binary.name, dest / 'lib', old
    dest.mkdir(parents=True)
    shutil.copy2(binary, dest / binary.name)
    shutil.copytree(lib, dest / 'lib', symlinks=False)
    result = dict(binary_source=str(binary), lib_source=str(lib), source_hashes=source)
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    return dest / binary.name, dest / 'lib', result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', required=True)
    p.add_argument('--arm', choices=['A','B','C'], required=True)
    p.add_argument('--assignments', type=int, choices=SCALES, required=True)
    p.add_argument('--phase', choices=['timing','sampled','instrumented'], required=True)
    p.add_argument('--attempt', required=True, help='Unique identifier, never reused')
    for name in ('raw','inputs-raw','binary','lib','tools','graph-tool'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--stage', type=Path, default=HERE.parent / 'prefill-capacity/stage.py')
    p.add_argument('--collector', type=Path)
    p.add_argument('--sim-arg', action='append', default=[])
    p.add_argument('--reference', type=Path, help='Successful fresh A attempt for B/C; same-arm timing attempt for sampled')
    p.add_argument('--approve-pair-jetty', action='store_true', help='Lead confirms native concurrent multi-segment capability gate passed')
    p.add_argument('--approve-100k', action='store_true', help='Only after lead explicitly approves 50K guard/parity gate')
    p.add_argument('--common', type=Path, help='Explicit common-100000 directory, generated separately by original stage.py')
    a = p.parse_args()
    for name in ('raw','inputs_raw','binary','lib','tools','graph_tool','stage'):
        setattr(a, name, getattr(a,name).resolve())
    if '/' in a.attempt or a.attempt in ('.','..'):
        p.error('attempt must be a single directory name')
    if a.assignments == 100000 and (not a.approve_100k or not a.common):
        p.error('100K requires lead approval flag and explicitly prepared --common')
    if a.phase == 'sampled' and (a.assignments != 50000 or not a.collector or not a.reference):
        p.error('Sampling is limited to representative 50K after successful same-arm timing; collector/reference required')
    if (a.arm in ('B','C') or a.phase == 'instrumented') and not a.reference:
        p.error('B/C and instrumented runs require a fresh reference timing attempt')
    if a.arm == 'C' and (not a.approve_pair_jetty or '--jettyMapping=pairJetty' not in a.sim_arg):
        p.error('C requires approved native capability gate and --sim-arg=--jettyMapping=pairJetty')
    if not a.stage.is_file() or not a.binary.is_file() or not a.lib.is_dir():
        p.error('Missing stage, binary, or library directory')
    # Set both import roots BEFORE importing the unchanged guard (psutil dependency).
    sys.path[:0] = [str(a.tools), str(PROFILING)]
    from guard import run
    a.raw.mkdir(parents=True, exist_ok=True)
    with (a.raw / '.sequential.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        case = a.raw / a.attempt
        if case.exists():
            raise ValueError('Refusing to overwrite any attempt, including failed attempts')
        case.mkdir()
        row = dict(attempt=a.attempt, arm=a.arm, assignments=a.assignments, phase=a.phase,
                   status='running', started=utc(), invocation=sys.argv, stages={})
        def save():
            (case / 'attempt.json').write_text(json.dumps(row, indent=2) + '\n')
        append(a.raw, dict(attempt=a.attempt, status='running', invocation=sys.argv)); save()
        try:
            common = a.common.resolve() if a.common else a.inputs_raw / f'common-{a.assignments}'
            row['input_source'] = str(common / 'run')
            row['input_hashes'] = hashes(common / 'run')
            if len(row['input_hashes']) != 7:
                raise ValueError('Expected exact seven original common run input files')
            shutil.copytree(common / 'run', case / 'run')
            if hashes(case / 'run') != row['input_hashes']:
                raise ValueError('Copied input hashes differ')
            ref = read_attempt(a.reference) if a.reference else None
            if ref:
                expected_arm = a.arm if a.phase in ('sampled','instrumented') else 'A'
                if ref['status'] != 'success' or ref['arm'] != expected_arm or ref['phase'] != 'timing' or ref['assignments'] != a.assignments:
                    raise ValueError('Reference must be matching successful fresh timing attempt')
                if ref['input_hashes'] != row['input_hashes']:
                    raise ValueError('Reference input mismatch')
                row['reference'] = str(a.reference.resolve())
            freeze_key = a.arm + ('-instrumented' if a.phase == 'instrumented' else '')
            binary, lib, row['elf_manifest'] = freeze(a.binary, a.lib, a.raw, freeze_key)
            if a.arm == 'C':
                b_key = 'B-instrumented' if a.phase == 'instrumented' else 'B'
                b_manifest = json.loads((a.raw / 'frozen' / b_key / 'manifest.json').read_text())
                if row['elf_manifest']['source_hashes']['libraries'] != b_manifest['source_hashes']['libraries']:
                    raise ValueError('C must use the exact same indexed native libraries as B')
            en = {'PATH':str(Path(sys.executable).parent)+':/usr/bin:/bin','LANG':'C.UTF-8',
                  'LC_ALL':'C.UTF-8','HOME':str(case / 'home'), 'RELAY_GRAPH_TOOL':str(a.graph_tool),
                  'LD_LIBRARY_PATH':str(lib)}
            (case / 'home').mkdir()
            if a.phase == 'instrumented':
                en.update(NATIVE_CPU_PROFILE='1', NATIVE_CPU_PROFILE_OUT=str(case / 'timing.tsv'))
            row['environment'] = en
            cmd = [str(binary), '--input='+str(case / 'run/input.txt'), '--out='+str(case / 'run'),
                   '--capacityMetrics='+str(case / 'run/simulator-metrics.json')] + a.sim_arg
            if a.phase == 'sampled':
                cmd = [str(a.collector.resolve()),str(case / 'perf.data'),'99','--'] + cmd
            commands = [('ns3', cmd), ('verify', [sys.executable, str(a.stage), 'verify','--case',str(case)])]
            for stage, command in commands:
                row['stages'][stage] = run(command,case / 'stages' / stage,600,cwd=HERE.parents[1],case=case,env=en)
                save()
                if row['stages'][stage]['status'] != 'PASS':
                    raise ValueError('Failed stage: '+stage)
            if hashes(common / 'run') != row['input_hashes']:
                raise ValueError('Original inputs mutated')
            freeze(a.binary,a.lib,a.raw,freeze_key)  # Check source/frozen ELF stability after execution.
            if a.phase == 'instrumented' and not (case / 'timing.tsv').is_file():
                raise ValueError('Instrumented binary did not emit timing.tsv')
            row['file_hashes'] = hashes(case / 'run')
            if len(row['file_hashes']) != 398:
                raise ValueError('Expected all 398 run files')
            row['logical_invariants'] = logical(case / 'run')
            if ref:
                row['parity'] = parity(a.reference,case,'logical' if a.arm == 'C' and a.phase == 'timing' else 'bytewise')
                if not row['parity']['pass']:
                    raise ValueError('Parity gate failed')
            row['status'] = 'success'
        except BaseException as exc:
            row.update(status='failed', error=repr(exc))
            raise
        finally:
            row['ended'] = utc(); save()
            append(a.raw, dict(attempt=a.attempt,status=row['status'],record=str(case / 'attempt.json'),error=row.get('error')))
    print(json.dumps({'attempt':str(case),'status':row['status']}))

if __name__ == '__main__':
    main()
