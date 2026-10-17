#!/usr/bin/env python3
"""Sequential PairJetty adversarial checks using accepted chunk-streaming fixtures.

Run after Gate C. No compilation, source edits, or new fault behavior. The live
faults and early-group oracle are taken from multi-npu-relay/tests.py;
early-compute's expected guard is also covered by direct-weight-forward/tests.py.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = ('input.txt', 'config.json', 'plan.json', 'assignments.csv',
          'transfers.csv', 'graph-input.txt', 'weight-edges.csv')
FAULTS = {
    'weight-byte': 'payload byte mismatch',
    'premature-ready': 'ready before target completion coverage',
    'duplicate-weight': 'duplicate forwarding',
    'early-compute': 'compute token/gate dependency',
    'early-group': 'relay before target chunk ready',
    'relay-byte': 'payload byte mismatch',
    'relay-buffer-byte': 'payload byte mismatch',
    'early-relay': 'relay before target chunk ready',
    'early-final-ready': 'final ready before full weight coverage',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--lib', type=Path, required=True)
    p.add_argument('--gate-c', type=Path, required=True,
                   help='Completed run-cases.py --group weights output directory')
    p.add_argument('--out', type=Path, required=True, help='Fresh output directory')
    p.add_argument('--jetty-mode', choices=('pair', 'per-wqe'), default='pair')
    a = p.parse_args()
    binary, lib, gate, out = (x.resolve() for x in (a.binary, a.lib, a.gate_c, a.out))
    require(binary.is_file(), 'Missing compiled pair-layer binary')
    require(lib.is_dir(), 'Missing native library directory')
    require(not out.exists(), 'Output exists; choose a fresh directory to retain evidence')
    # Exact accepted live-fault fixtures from the original relay suite.
    canary = gate / 'multi4_force-chunk-streaming' / a.jetty_mode / 'run'
    slow = gate / 'slow_relay8-chunk-streaming' / a.jetty_mode / 'run'
    for source in (canary, slow):
        for name in ('input.txt', 'config.json', 'plan.json', 'summary.json', 'pair-validation.json'):
            require((source / name).is_file(), 'Gate C fixture not complete: ' + str(source / name))
        require(json.loads((source / 'pair-validation.json').read_text())['status'] == 'PASS',
                'Gate C fixture did not pass strict PairJetty verification')
        require(json.loads((source / 'config.json').read_text())['weight_strategy'] == 'chunk-streaming',
                'Expected accepted chunk-streaming fixture')
    spec = importlib.util.spec_from_file_location('negative_guard', HERE.parent / 'wqe-completion-fix/guard.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    out.mkdir(parents=True)
    report = {'status': 'INCOMPLETE', 'jetty_mode': a.jetty_mode,
              'binary': str(binary), 'binary_sha256': sha(binary),
              'fixtures': {str(s): {n: sha(s / n) for n in INPUTS if (s / n).exists()}
                           for s in (canary, slow)},
              'live_faults': [], 'duplicate_notify': None, 'verifier_tampering': []}

    def save():
        (out / 'negative-tests.json').write_text(json.dumps(report, indent=2) + '\n')

    def case_inputs(source, dest):
        dest.mkdir(parents=True)
        for name in INPUTS:
            if (source / name).exists():
                shutil.copy2(source / name, dest / name)

    def execute(source, fault):
        case = out / fault
        dest = case / 'run'
        case_inputs(source, dest)
        command = [str(binary), '--input=' + str(dest / 'input.txt'), '--out=' + str(dest),
                   '--capacityMetrics=' + str(dest / 'simulator-metrics.json'),
                   '--jettyMode=' + a.jetty_mode, '--logLevel=debug', '--fault=' + fault]
        result = guard.run(command, case / 'host', 300, case=case,
                           env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LD_LIBRARY_PATH':str(lib)})
        return dest, result, (case / 'host/console.txt').read_text()

    def verify_copy(dest, host):
        result = guard.run([sys.executable, str(HERE / 'verify.py'), str(dest), a.jetty_mode],
                           host, 300, case=dest)
        return result, (host / 'console.txt').read_text()

    save()
    try:
        for fault, expected in FAULTS.items():
            source = slow if fault == 'early-group' else canary
            dest, result, console = execute(source, fault)
            record = {'fault': fault, 'fixture': str(source), 'expected_error': expected,
                      'execution': result, 'status': 'FAIL'}
            report['live_faults'].append(record)
            save()
            # A resource kill, signal, or unrelated nonzero result is not proof of rejection.
            require(result['guard'] is None and result['returncode'] > 0 and
                    ('ERROR: ' + expected) in console, 'Fault not rejected by expected guard: ' + fault)
            if fault == 'early-group':
                config = json.loads((source / 'config.json').read_text())
                rows = read_rows(dest / 'events.csv')
                attempts = [r for r in rows if r['event'] == 'early_group_attempt']
                require(len(attempts) == 1, 'Missing unique fast-relay group fault')
                child = config['transfers'][int(attempts[0]['task'])]
                completed = {int(r['task']) for r in rows if r['event'] == 'edge_ready'}
                own = [j for j in child['dependencies']
                       if config['transfers'][j]['physical'] == child['source_physical']]
                require(own and all(j in completed for j in own) and
                        any(j not in completed for j in child['dependencies']),
                        'Early-group fault must distinguish own-ready from group-ready')
                record['own_ready_group_not_ready'] = True
            record['status'] = 'PASS'
            save()
            print('PASS expected rejection:', fault, flush=True)

        dest, result, console = execute(canary, 'duplicate-notify')
        report['duplicate_notify'] = {'execution': result, 'status': 'FAIL'}
        save()
        require(result['status'] == 'PASS', 'Duplicate-notify execution failed')
        verification, _ = verify_copy(dest, out / 'duplicate-notify/verifier-host')
        report['duplicate_notify']['verification'] = verification
        require(verification['status'] == 'PASS', 'Duplicate-notify strict verification failed')
        require(json.loads((dest / 'summary.json').read_text()) ==
                json.loads((canary / 'summary.json').read_text()),
                'Duplicate notifications changed accepted timing, payloads, or execution summary')
        require(any(r['event'] == 'duplicate_ignored' for r in read_rows(dest / 'events.csv')),
                'Duplicate notifications were not exercised')
        for name in ('received-payloads.bin', 'payload-index.csv', 'executed-transfers.csv'):
            require(sha(dest / name) == sha(canary / name), 'Duplicate-notify artifact changed: ' + name)
        report['duplicate_notify']['status'] = 'PASS'
        save()

        # Only copies are mutated; preserve evidence and leave the Gate C runs intact.
        for name in ('payload-byte', 'premature-final-ready'):
            case = out / 'verifier-tamper' / name
            dest = case / 'run'
            dest.mkdir(parents=True)
            for source in canary.iterdir():
                if source.is_file():
                    shutil.copy2(source, dest / source.name)
            if name == 'payload-byte':
                payload = bytearray((dest / 'received-payloads.bin').read_bytes())
                require(payload, 'Empty payload fixture')
                payload[-1] ^= 1
                (dest / 'received-payloads.bin').write_bytes(payload)
                expected = 'raw weight payload'
            else:
                rows = read_rows(dest / 'events.csv')
                target = next((r for r in rows if r['event'] == 'weight_ready'), None)
                require(target is not None, 'No final weight-ready event in fixture')
                target['time_ps'] = '1000'
                # Preserve clock order, so this tests semantic readiness rather than CSV order.
                rows.sort(key=lambda r: int(r['time_ps']))
                with (dest / 'events.csv').open('w') as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                expected = 'final ready requires all chunks'
            result, console = verify_copy(dest, case / 'verifier-host')
            record = {'tamper': name, 'expected_error': expected, 'verification': result, 'status': 'FAIL'}
            report['verifier_tampering'].append(record)
            save()
            require(result['guard'] is None and result['returncode'] > 0 and
                    ('ValueError: ' + expected) in console, 'Strict verifier missed tampering: ' + name)
            record['status'] = 'PASS'
            save()
        report['status'] = 'PASS'
        print('PASS: 9 live fault rejections, strict duplicate-notify parity, 2 verifier tamper rejections')
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
