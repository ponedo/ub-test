#!/usr/bin/env python3
"""Sequential, resource-guarded same-input comparison and fault-injection suite.

Creates fresh output only. Inputs and original evidence are never modified.
"""
import argparse
import csv
import importlib.util
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'wqe-completion-fix'))
from guard import run as guarded_run
from common import (INPUTS, JSON_OUTPUTS, MODES, differences, event_evidence,
                    host_compact, read_json, require, sha, size_breakdown,
                    stable, write_json)

FAULTS = {
    'payload-byte': ('payload byte mismatch',),
    'duplicate-completion': ('duplicate',),
    'early-wqe': ('before', 'early'),
    'missing-wqe': ('unfinished layer', 'missing', 'sender'),
    'weight-byte': ('payload byte mismatch',),
    'premature-ready': ('ready before target completion coverage',),
    'duplicate-weight': ('duplicate forwarding',),
    'early-compute': ('compute token/gate dependency',),
    'early-group': ('relay before target chunk ready',),
    'relay-byte': ('payload byte mismatch',),
    'relay-buffer-byte': ('payload byte mismatch',),
    'early-relay': ('relay before target chunk ready',),
    'early-final-ready': ('final ready before full weight coverage',),
}


def copy_inputs(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for name in INPUTS:
        if (source / name).is_file():
            shutil.copy2(source / name, destination / name)
    for name in ('input.txt', 'config.json', 'plan.json'):
        require((destination / name).is_file(), 'Missing fixture ' + str(source / name))
    return {name: sha(destination / name) for name in INPUTS if (destination / name).exists()}


def restore_ep64(package, destination, strategy):
    sys.path.insert(0, str(HERE.parent / 'ep64-token-scaling'))
    from restore import restore
    # This is a prepared-input archive, not a multi-GB raw simulator archive.
    manifest = read_json(package / 'manifest.json')
    require(manifest['source_name'] == 'prepared', 'Expected prepared-input package')
    require(manifest['archive_bytes'] < 16 * 1024**2, 'Prepared fixture archive exceeds 16 MiB')
    result = restore(package, destination, prefix=strategy)
    require(result['status'] == 'PASS', 'Input package integrity')
    return result


def prepare(root, package, out):
    cases = []
    specs = [
        ('nb-small', 'single4', 'no-balancing'),
        ('direct-small', 'multi4_force', 'direct'),
        ('chunk-small', 'multi8', 'chunk-streaming'),
        ('multichunk-multita', 'multi4_force', 'chunk-streaming'),
    ]
    for name, fixture, strategy in specs:
        source, target = root / fixture / strategy, out / name
        hashes = copy_inputs(source, target)
        cases.append({'name': name, 'source': str(source), 'path': str(target), 'input_sha256': hashes})
    target = out / 'ep64-n256'
    integrity = restore_ep64(package, target, 'chunk-streaming')
    config = read_json(target / 'config.json')
    require(config['planner_input']['npus'] == 64, 'EP64 fixture is not 64 NPUs')
    tokens = len(config['planner_input']['mapping'])
    require(tokens in (256, 1024), 'Use representative N256 or N1024 EP64 inputs')
    cases.append({'name': 'ep64-n' + str(tokens), 'source': str(package), 'path': str(target),
                  'input_sha256': {n: sha(target / n) for n in INPUTS if (target / n).exists()},
                  'restoration': integrity})
    copy_inputs(root / 'slow_relay8' / 'chunk-streaming', out / 'slow-relay-fault')
    for row in cases:
        config = read_json(Path(row['path']) / 'config.json')
        transfers, segment = config['transfers'], config['parameters']['segment_bytes']
        row['dimensions'] = {'npus': config['planner_input']['npus'],
                             'tokens': len(config['planner_input']['mapping']),
                             'assignments': len(config['assignments']),
                             'tasks': len(transfers),
                             'weight_tasks': sum(x['stage'] == 2 for x in transfers),
                             'max_TAs_per_WQE': max((x['bytes'] + segment - 1) // segment for x in transfers),
                             'strategy': config['weight_strategy']}
    return cases


def compare_debug_to_online(online, strict, debug_path):
    required = ('layer_latency_ps', 'remote_WQEs')
    for name in required:
        require(name in online and online[name] == strict[name], 'Online/strict mismatch: ' + name)
    for name in ('verified_bytes', 'remote_bytes', 'local_bytes', 'target_segments'):
        require(name in online, 'Online summary is missing byte/completion field ' + name)
        require(online[name] == strict[name], 'Online/strict mismatch: ' + name)
    require(online['completed_tokens'] == strict['tokens'], 'Completed tokens differ from strict oracle')
    require(online['sender_completions'] == strict['remote_WQEs'], 'Sender count differs from strict oracle')
    require(online['verified_bytes'][2] == strict['weight_bytes'], 'Online weight bytes differ from strict oracle')
    require(online['timeline'] == strict['timeline'], 'Online timeline differs from strict oracle')
    require(online['compute_intervals'] == strict['compute_intervals'], 'Online compute intervals differ from strict oracle')
    observed = event_evidence(debug_path / 'events.csv')
    require(online['event_spans'] == observed['timeline'], 'Online event spans differ from full debug events')
    for i, name in enumerate(('dispatch', 'combine')):
        require(online['stage_intervals'][i] == observed['stage_spans'][name][:2], 'Online stage interval differs: ' + name)
    return observed


def verify_modes(records):
    by_mode = {row['mode']: row for row in records}
    reference = by_mode['debug']
    for mode in MODES:
        row = by_mode[mode]
        for key in ('online_summary', 'metrics', 'validation'):
            diff = differences(stable(reference[key]), stable(row[key]))
            require(not diff, mode + ' differs from debug in ' + key + ': ' + str(diff))
        require(row['input_sha256'] == reference['input_sha256'], 'Input hash drift between modes')
    strict = reference['strict_summary']
    evidence = compare_debug_to_online(reference['online_summary'], strict, Path(reference['run_path']))
    events_path = Path(by_mode['events']['run_path']) / 'events.csv'
    with events_path.open() as stream:
        key_events = list(csv.DictReader(stream))
    with (Path(reference['run_path']) / 'events.csv').open() as stream:
        debug_events = list(csv.DictReader(stream))
    config = read_json(Path(reference['run_path']) / 'config.json')
    expected_events = []
    retained = {'layer_start', 'layer_end', 'planning_start', 'planning_end',
                'reroute_start', 'reroute_end', 'weights_start', 'weights_end',
                'dispatch_gate', 'compute_start', 'compute_end', 'compute_idle',
                'expert_start', 'expert_end', 'weight_ready', 'group_chunk_ready'}
    ready = [0, 0]
    combine_started = False
    for row in debug_events:
        event, stage, task = row['event'], int(row['stage']), int(row['task'])
        aliases = []
        relay = event == 'send' and stage == 2 and task >= 0 and bool(config['transfers'][task]['dependencies'])
        if event == 'dispatch_gate':
            aliases.append('dispatch_start')
            if not config['assignments']:
                aliases += ['dispatch_end', 'combine_start', 'combine_end']
        if event == 'data_ready' and stage in (0, 1):
            ready[stage] += 1
            if ready[stage] == len(config['assignments']):
                aliases.append('dispatch_end' if stage == 0 else 'combine_end')
        if event == 'send' and stage == 1 and not combine_started:
            aliases.append('combine_start')
            combine_started = True
        if event == 'edge_ready':
            aliases.append('chunk_ready')
        if event == 'weight_ready':
            aliases.append('replica_weight_ready')
        if relay:
            aliases.append('relay_forward_start')
        expected_events.extend(dict(row, event=name) for name in aliases)
        if event in retained or event == 'edge_ready' or relay:
            expected_events.append(row)
    require(key_events == expected_events, 'Events mode differs from exact independently filtered/aliased debug stream')
    require(0 < len(key_events) < len(debug_events), 'Events mode did not filter debug events')
    return {'status': 'PASS', 'debug_event_rows': len(debug_events),
            'key_event_rows': len(key_events), 'independent_event_evidence': evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--old-binary', type=Path, required=True)
    parser.add_argument('--lib', type=Path, required=True)
    parser.add_argument('--graph-tool', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', help='Optional named case subset for development smoke tests')
    parser.add_argument('--fixtures-root', type=Path, required=True)
    parser.add_argument('--ep64-package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--wall-limit', type=int, default=300)
    parser.add_argument('--skip-faults', action='store_true')
    args = parser.parse_args()
    args.out = args.out.resolve()
    for name in ('binary', 'old_binary', 'lib', 'graph_tool', 'fixtures_root', 'ep64_package'):
        setattr(args, name, getattr(args, name).resolve())
    require(args.binary.is_file() and args.old_binary.is_file(), 'Compiled executables are required')
    require(args.lib.is_dir(), 'Native library directory is required')
    args.out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, LANG='C.UTF-8', LD_LIBRARY_PATH=str(args.lib))
    report = {'status': 'RUNNING', 'binary': str(args.binary), 'binary_sha256': sha(args.binary),
              'old_binary': str(args.old_binary), 'old_binary_sha256': sha(args.old_binary),
              'graph_tool': str(args.graph_tool), 'graph_tool_sha256': sha(args.graph_tool),
              'baseline_config': read_json(HERE.parent / 'ep64-token-scaling/fixed-config.json'),
              'executor_source_sha256': {name: sha(HERE.parent / 'pair-jetty' / name) for name in ('pair-layer.cc', 'online-validation.inc', 'pair-jetty-manager.h')},
              'native_libraries_sha256': {item.name: sha(item) for item in sorted(args.lib.glob('libns3*.so'))},
              'runs': [], 'cases': [], 'faults': [], 'comparisons': {}}

    def save():
        write_json(args.out / 'results.json', report)

    def execute(command, host, case):
        result = guarded_run(command, host, args.wall_limit, case=case, env=env)
        return host_compact(result, host / 'resource.json')

    def simulate(source, path, mode, binary, old=False, fault=None):
        dest = path / 'run'
        hashes = copy_inputs(source, dest)
        command = [str(binary), '--input=' + str(dest / 'input.txt'), '--out=' + str(dest),
                   '--capacityMetrics=' + str(dest / 'simulator-metrics.json'), '--jettyMode=pair']
        # Omit the flag for summary to test the public default.
        if not old and mode != 'summary':
            command.append('--logLevel=' + mode)
        if fault:
            command.append('--fault=' + fault)
        preflight_command = [sys.executable, str(HERE / 'preflight.py'), str(dest),
                             '--graph-tool', str(args.graph_tool), '--out', str(path / 'preflight.json'),
                             '--input-summary', str(dest / 'input-summary.json')]
        before = execute(preflight_command, path / 'preflight-host', path)
        require(before['status'] == 'PASS', 'Independent preflight failed: ' + str(path))
        host = execute(command, path / 'host', path)
        after = None
        if host['status'] == 'PASS':
            postflight_command = preflight_command + ([] if old else ['--execution-summary', str(dest / 'online-summary.json')])
            after = execute(postflight_command, path / 'postflight-host', path)
            require(after['status'] == 'PASS', 'Independent postflight failed: ' + str(path))
        return {'preflight_host': before, 'postflight_host': after, 'mode': mode, 'command': command, 'host': host, 'run_path': str(dest),
                'input_sha256': hashes, 'output': size_breakdown(dest)}

    def strict_verify(row, path):
        dest = Path(row['run_path'])
        row['strict_verifier_host'] = execute(
            [sys.executable, str(HERE.parent / 'pair-jetty/verify.py'), str(dest), 'pair'],
            path / 'verifier-host', path)
        require(row['strict_verifier_host']['status'] == 'PASS', 'Original strict verifier rejected ' + str(path))
        row['strict_summary'] = read_json(dest / 'summary.json')
        row['strict_validation'] = read_json(dest / 'pair-validation.json')

    save()
    try:
        report['cases'] = prepare(args.fixtures_root, args.ep64_package, args.out / 'inputs')
        if args.cases:
            available = {row['name'] for row in report['cases']}
            require(set(args.cases) <= available, 'Unknown case subset')
            report['cases'] = [row for row in report['cases'] if row['name'] in args.cases]
        save()
        for case in report['cases']:
            source, rows = Path(case['path']), []
            for mode in MODES:
                path = args.out / case['name'] / mode
                row = simulate(source, path, mode, args.binary)
                row['case'] = case['name']
                report['runs'].append(row)
                save()
                require(row['host']['status'] == 'PASS', 'Simulation failed: ' + str(path))
                dest = Path(row['run_path'])
                for filename in JSON_OUTPUTS:
                    require((dest / filename).is_file(), 'Missing output ' + str(dest / filename))
                row['online_summary'] = read_json(dest / 'online-summary.json')
                row['validation'] = read_json(dest / 'validation.json')
                row['metrics'] = read_json(dest / 'simulator-metrics.json')
                require(row['validation']['status'] == 'PASS', 'Online validation failed')
                generated = set(row['output']['files']) - set(INPUTS)
                if mode == 'summary':
                    require(generated == JSON_OUTPUTS, 'Unexpected summary files: ' + str(generated))
                elif mode == 'events':
                    require(generated == JSON_OUTPUTS | {'events.csv'}, 'Unexpected events files: ' + str(generated))
                else:
                    for filename in ('events.csv', 'ta-identity.csv', 'received-payloads.bin', 'payload-index.csv', 'executed-transfers.csv'):
                        require((dest / filename).is_file(), 'Debug artifact absent: ' + filename)
                    strict_verify(row, path)
                rows.append(row)
                save()
            report['comparisons'][case['name']] = verify_modes(rows)
            if case['name'] == 'multichunk-multita':
                summary = rows[-1]['strict_summary']
                require(summary['group_chunk_count'] > 1, 'Multichunk fixture must contain multiple chunks')
                require(case['dimensions']['max_TAs_per_WQE'] > 1, 'Multi-TA fixture must split a WQE')
                require(summary['pipeline_overlaps'] and summary['native_pipeline_overlaps'], 'Fixture must exercise real application and native pipeline overlap')
                report['comparisons'][case['name']]['multichunk_multita_proof'] = {
                    'group_chunks': summary['group_chunk_count'],
                    'max_TAs_per_WQE': case['dimensions']['max_TAs_per_WQE'],
                    'application_pipeline_overlaps': len(summary['pipeline_overlaps']),
                    'native_pipeline_overlaps': len(summary['native_pipeline_overlaps'])}
            old_path = args.out / case['name'] / 'old-debug'
            old = simulate(source, old_path, 'old-debug', args.old_binary, old=True)
            old['case'] = case['name']
            report['runs'].append(old)
            save()
            require(old['host']['status'] == 'PASS', 'Old debug reference execution failed')
            old['metrics'] = read_json(Path(old['run_path']) / 'simulator-metrics.json')
            strict_verify(old, old_path)
            new = rows[-1]
            require(old['strict_summary'] == new['strict_summary'], 'Old/new strict summary changed')
            require(old['metrics'] == new['metrics'], 'Old/new simulator metrics changed')
            old_files = set(old['output']['files']) - set(INPUTS)
            checks = {}
            for name in sorted(old_files - {'simulator-metrics.json', 'input-summary.json'}):
                previous, current = Path(old['run_path']) / name, Path(new['run_path']) / name
                require(current.is_file(), 'Debug compatibility file missing: ' + name)
                checks[name] = sha(previous) == sha(current)
            require(all(checks.values()), 'Debug artifact bytes changed: ' + str([k for k, v in checks.items() if not v]))
            report['comparisons'][case['name']]['old_debug_artifact_byte_parity'] = checks
            report['comparisons'][case['name']]['old_debug_strict_parity'] = 'PASS'
            save()
            print('PASS same-input modes and old-debug:', case['name'], flush=True)
        if not args.skip_faults:
            canary = args.out / 'inputs' / 'multichunk-multita'
            slow = args.out / 'inputs' / 'slow-relay-fault'
            for fault, messages in FAULTS.items():
                for mode in MODES:
                    path = args.out / 'faults' / fault / mode
                    row = simulate(slow if fault == 'early-group' else canary, path, mode, args.binary, fault=fault)
                    row['fault'] = fault
                    row['expected_error_substrings'] = list(messages)
                    report['faults'].append(row)
                    save()
                    console = (path / 'host' / 'console.txt').read_text()
                    require(row['host']['guard'] is None and row['host']['returncode'] > 0,
                            'Fault must fail by application guard: ' + fault + '/' + mode)
                    require('ERROR: ' in console and any(message in console for message in messages),
                            'Fault failed for unexpected reason: ' + fault + '/' + mode)
                    validation = read_json(path / 'run' / 'validation.json')
                    require(validation['status'] == 'FAIL', 'Fault did not produce FAIL validation')
                    row['validation'] = validation
                    row['status'] = 'PASS'
                    save()
                print('PASS rejected in all modes:', fault, flush=True)
        report['status'] = 'PASS'
    except Exception as error:
        report['status'] = 'FAIL'
        report['error'] = str(error)
        raise
    finally:
        save()
    return 0


if __name__ == '__main__':
    sys.exit(main())
