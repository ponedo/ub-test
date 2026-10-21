#!/usr/bin/env python3
"""Guarded prepare, independent-review latch, then exactly two sequential cases."""
import argparse
import os
import shutil
import sys
import types
import psutil
from common import *
from heartbeat import Heartbeat

def stage(command, out, identity, wall=4800):
    require(not out.exists(), 'No implicit restart: ' + str(out))
    check(identity)
    guard = load('accepted_screen_guard', E / 'cloudmatrix-bandwidth/guard.py')
    heartbeat = Heartbeat(out, command)
    heartbeat.start()
    original_time = guard.m.time
    def sampled_sleep(seconds):
        original_time.sleep(seconds)
        heartbeat.tick()
    # Same accepted guard timing/thresholds and child ownership. Piggyback the
    # existing sample loop, avoiding threads before its preexec_fn/fork.
    guard.m.time = types.SimpleNamespace(monotonic=original_time.monotonic, sleep=sampled_sleep)
    result = None
    try:
        result = guard.run(command, out, wall=wall, case=out.parent,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    finally:
        guard.m.time = original_time
        heartbeat.stop(result['status'] if result else 'STOPPED_OR_UNCERTAIN')
    require(heartbeat.error is None, 'Durable host heartbeat failed: ' + str(heartbeat.error))
    require(result['status'] == 'PASS' and result['guard'] is None,
            'Guarded stage failed: ' + str(out))
    check(identity)
    return result

def preflight(directory, graph_tool, result, execution=False):
    command = [sys.executable, E / 'ultraep-multicast-integration/preflight.py', directory,
               '--graph-tool', graph_tool, '--out', result]
    if execution:
        command += ['--execution-summary', directory / 'online-summary.json']
    return command

def prepare_run(args):
    root = args.private.resolve()
    require(not root.exists(), 'Fresh campaign directory required')
    root.mkdir(parents=True)
    identity = read(args.identity)
    identity.update(freeze([args.binary, args.graph_tool, args.identity]))
    identity.update(freeze(p for p in H.rglob('*') if p.is_file() and '__pycache__' not in p.parts))
    check(identity)
    write(root / 'identity.json', identity)
    ledger = dict(status='PREPARING', requested_base=BASE, tokens=256, runs=[])
    write(root / 'ledger.json', ledger)
    try:
        command = [sys.executable, H / 'prepare.py', '--source', args.source.resolve(),
                   '--routing', args.routing.resolve(), '--manifest', args.manifest.resolve(),
                   '--counts', args.counts.resolve(), '--graph-tool', args.graph_tool.resolve(),
                   '--out', root / 'prepared']
        stage(command, root / 'preparation-host', identity)
        prep = read(root / 'prepared/preparation.json')
        for row in prep['cases']:
            directory = root / 'prepared' / row['strategy']
            stage(preflight(directory, args.graph_tool.resolve(), directory / 'preflight.json'),
                  directory / 'preflight-host', identity)
            require(read(directory / 'preflight.json')['status'] == 'PASS', 'Input preflight failed')
            row.update(status='PREPARED', preflight_sha256=sha(directory / 'preflight.json'))
            ledger['runs'].append(row)
        prepared = dict(requested_base=BASE, tokens=256, strategies=list(STRATEGIES),
                        binary=str(args.binary.resolve()), graph_tool=str(args.graph_tool.resolve()),
                        identity_sha256=sha(root / 'identity.json'),
                        preparation_sha256=sha(root / 'prepared/preparation.json'), runs=ledger['runs'])
        write(root / 'prepared-manifest.json', prepared)
        ledger.update(status='PREPARED', prepared_manifest_sha256=sha(root / 'prepared-manifest.json'))
    except BaseException as exc:
        ledger.update(status='STOPPED', failure=str(exc))
        raise
    finally:
        write(root / 'ledger.json', ledger)
    print('PREPARED. Independent read-only review and explicit approval are required; no simulator ran.')

def run_pair(args):
    root = args.private.resolve()
    ledger, prepared = read(root / 'ledger.json'), read(root / 'prepared-manifest.json')
    require(ledger['status'] == 'PREPARED', 'No implicit resume or rerun')
    approval = read(args.approval)
    require(approval.get('status') == 'PASS' and approval.get('approved_to_run') is True,
            'Explicit preflight approval missing')
    require(approval.get('independent_reviewer'), 'Independent read-only reviewer missing')
    require(approval.get('prepared_manifest_sha256') == sha(root / 'prepared-manifest.json') == ledger['prepared_manifest_sha256'],
            'Approval does not bind this exact prepared pair')
    for key in ('minimal_gates', 'independent_review'):
        reference = approval.get(key, {})
        require(reference.get('path') and reference.get('sha256'), 'Missing approval evidence: ' + key)
        require(sha(reference['path']) == reference['sha256'], 'Approval evidence changed: ' + key)
        evidence = read(reference['path'])
        require(evidence.get('status') == 'PASS', 'Approval evidence did not pass: ' + key)
        if key == 'independent_review':
            require(evidence.get('prepared_manifest_sha256') == approval['prepared_manifest_sha256'],
                    'Independent review does not bind the prepared pair')
    require(prepared['tokens'] == 256 and prepared['strategies'] == list(STRATEGIES), 'Scope drift')
    require([row['strategy'] for row in prepared['runs']] == list(STRATEGIES) ==
            [row['strategy'] for row in ledger['runs']], 'Exactly the authorized two cases are required')
    require(sha(root / 'identity.json') == prepared['identity_sha256'], 'Identity manifest drift')
    require(sha(root / 'prepared/preparation.json') == prepared['preparation_sha256'], 'Preparation drift')
    identity = read(root / 'identity.json')
    identity.update(freeze([args.approval, *(approval[key]['path'] for key in ('minimal_gates', 'independent_review'))]))
    check(identity)
    for row in prepared['runs']:
        check(row['immutable_files'])
        directory = root / 'prepared' / row['strategy']
        require(sha(directory / 'preflight.json') == row['preflight_sha256'], 'Preflight drift')
        config = read(directory / 'config.json')
        require(len(config['planner_input']['mapping']) == 256 and config['weight_strategy'] == row['strategy'],
                'Formal workload scope drift')
        require(all(config[key]['link_gbps'] == 3136 and config[key]['link_delay_ns'] == 20
                    for key in ('runtime', 'parameters')), 'Formal link/propagation drift')
    for process in psutil.process_iter(['pid', 'name']):
        require(process.pid == os.getpid() or process.info['name'] not in ('layer', 'parent-layer', 'pair-layer'),
                'Another simulator is visible; review resources before admission')
    require(psutil.virtual_memory().available >= 7 * 1024**3, 'Need 6 GiB peak allowance plus 1 GiB host reserve')
    require(shutil.disk_usage(root).free >= 8 * 1024**3 and shutil.disk_usage('/tmp').free >= 2 * 1024**3,
            'Disk reserve unavailable')
    ledger.update(status='RUNNING', approval_sha256=sha(args.approval))
    write(root / 'ledger.json', ledger)
    try:
        for row in ledger['runs']:
            directory = root / 'prepared' / row['strategy']
            row['status'] = 'RUNNING'
            write(root / 'ledger.json', ledger)
            check(row['immutable_files'])
            stage(simulator(prepared['binary'], directory), directory / 'simulator-host', identity)
            require(read(directory / 'validation.json')['status'] == 'PASS', 'Online validation failed')
            stage(preflight(directory, prepared['graph_tool'], directory / 'postflight.json', True),
                  directory / 'postflight-host', identity)
            stage([sys.executable, E / 'ultraep-multicast-integration/verify.py', directory],
                  directory / 'independent-host', identity)
            stage([sys.executable, E / 'qwen-roofline-compute/verify-compute.py', directory, '--expected-model=roofline'],
                  directory / 'compute-host', identity)
            stage([sys.executable, H / 'analyze.py', directory, '--out', directory / 'aggregate.json'],
                  directory / 'aggregate-host', identity)
            check(row['immutable_files'])
            row.update(status='PASS', aggregate=read(directory / 'aggregate.json'))
            write(root / 'ledger.json', ledger)
            print('VERIFIED N256 ' + row['strategy'], flush=True)
        summaries = [read(root / 'prepared' / strategy / 'online-summary.json') for strategy in STRATEGIES]
        require(summaries[0]['combine_fnv1a64'] == summaries[1]['combine_fnv1a64'], 'Paired output mismatch')
        check(identity)
        ledger['status'] = 'PASS'
        write(root / 'pair-aggregate.json', dict(status='PASS', tokens=256,
              cases=[dict(row['aggregate'], strategy=row['strategy']) for row in ledger['runs']],
              limitations=['One deterministic formal case per strategy: pairwise reproduction, not a repeated-run stability claim.',
                           'No 512/1024/2048-token runs in this screening.']))
    except BaseException as exc:
        ledger.update(status='STOPPED', failure=str(exc))
        for row in ledger['runs']:
            if row['status'] == 'RUNNING':
                row.update(status='STOPPED', failure=str(exc))
            elif row['status'] == 'PREPARED':
                row.update(status='NOT_RUN', reason='Stopped at first failure')
        raise
    finally:
        write(root / 'ledger.json', ledger)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='phase', required=True)
    prep = sub.add_parser('prepare')
    for name in ('private', 'source', 'routing', 'manifest', 'counts', 'graph-tool', 'binary', 'identity'):
        prep.add_argument('--' + name, type=Path, required=True)
    run = sub.add_parser('run')
    for name in ('private', 'approval'):
        run.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(__debug__ and os.environ.get('PYTHONOPTIMIZE', '') in ('', '0'), 'Assertions must execute')
    os.umask(0o077)
    prepare_run(args) if args.phase == 'prepare' else run_pair(args)

if __name__ == '__main__':
    main()
