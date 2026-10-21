#!/usr/bin/env python3
"""Exact five-row campaign, review latch, strict reuse or necessary baseline rerun."""
import argparse
import csv
import os
from collections import Counter
from common import *


def preflight_command(directory, graph_tool, out, execution=False):
    command = [sys.executable, H / 'preflight.py', directory, '--graph-tool', graph_tool, '--formal', '--out', out]
    if Path(directory).name == HYBRID:
        command += ['--cs-control', Path(directory).parent / 'chunk-streaming']
    if execution:
        command += ['--execution-summary', Path(directory) / 'online-summary.json']
    return command


def prepare_run(args):
    root = args.private.resolve()
    require(not root.exists(), 'Fresh campaign directory required')
    root.mkdir(parents=True)
    identity = read(args.identity)
    identity.update(freeze([args.identity, args.binary, args.graph_tool]))
    identity.update(freeze(path for path in H.rglob('*') if path.is_file() and '__pycache__' not in path.parts))
    check(identity)
    write(root / 'identity.json', identity)
    ledger = dict(status='PREPARING', base=BASE, tokens=256, runs=[])
    write(root / 'ledger.json', ledger)
    try:
        stage([sys.executable, H / 'prepare.py', '--accepted-campaign', args.accepted_campaign.resolve(),
               '--graph-tool', args.graph_tool.resolve(), '--out', root / 'prepared'], root / 'preparation-host', identity)
        prep = read(root / 'prepared/preparation.json')
        for row in prep['cases']:
            directory = root / 'prepared' / row['strategy']
            stage(preflight_command(directory, args.graph_tool.resolve(), directory / 'preflight.json'), directory / 'preflight-host', identity)
            require(read(directory / 'preflight.json')['status'] == 'PASS', 'Input preflight failed')
            row.update(status='PREPARED', preflight_sha256=sha(directory / 'preflight.json'), command=simulator(args.binary.resolve(), directory, row['strategy']))
            ledger['runs'].append(row)
        prepared = dict(base=BASE, tokens=256, strategies=list(STRATEGIES), binary=str(args.binary.resolve()),
                        graph_tool=str(args.graph_tool.resolve()), accepted_campaign=str(args.accepted_campaign.resolve()),
                        identity_sha256=sha(root / 'identity.json'), preparation_sha256=sha(root / 'prepared/preparation.json'), runs=ledger['runs'])
        write(root / 'prepared-manifest.json', prepared)
        write(root / 'command-manifest.json', dict(base=BASE, commands=[dict(strategy=row['strategy'], argv=row['command']) for row in ledger['runs']]))
        ledger.update(status='PREPARED', prepared_manifest_sha256=sha(root / 'prepared-manifest.json'))
    except BaseException as exc:
        ledger.update(status='STOPPED', failure=str(exc))
        raise
    finally:
        write(root / 'ledger.json', ledger)
    print('PREPARED. Phase B, old-mode regression, independent review and exact approval required. No simulator ran.')


def evidence(reference, label):
    require(reference.get('path') and reference.get('sha256'), 'Missing bound evidence: ' + label)
    require(sha(reference['path']) == reference['sha256'], 'Evidence changed: ' + label)
    result = read(reference['path'])
    require(result.get('status') == 'PASS', 'Evidence did not pass: ' + label)
    return result


def reuse_decisions(path, prepared, identity):
    result = read(path)
    require(result.get('status') == 'PASS', 'Reuse decision is not approved')
    require(result.get('prepared_manifest_sha256') == prepared['_sha256'], 'Reuse decision does not bind exact five prepared cases')
    decisions = result.get('decisions', [])
    require([row.get('strategy') for row in decisions] == ['chunk-streaming', 'multicast-v2'], 'Exactly CS/MC reuse decisions required')
    previous_root = Path(prepared['accepted_campaign'])
    previous = read(previous_root / 'prepared-manifest.json')
    old_identity = read(previous_root / 'identity.json')
    # Compare exact loaded native library closure, not merely commit labels.
    old_libs = {path: digest for path, digest in old_identity.items() if '/build/lib/' in path}
    new_libs = {path: digest for path, digest in identity.items() if '/build/lib/' in path}
    require(old_libs and old_libs == new_libs, 'Loaded native library closure differs')
    old_cases = {row['strategy']: row for row in previous['runs']}
    for row in decisions:
        require(type(row.get('reuse')) is bool and row.get('reasons'), 'Explicit reuse/rerun rationale required')
        if not row['reuse']:
            continue
        checks = row.get('checks', {})
        for key in ('accepted_all_gates_pass', 'same_runtime_options', 'old_paths_unchanged', 'old_mode_exact_parity', 'equivalent_passive_observers', 'all_artifacts_pinned'):
            require(checks.get(key) is True, 'Reuse proof incomplete: ' + key)
        require(row.get('evidence'), 'Reuse needs inspectable evidence')
        for index, item in enumerate(row['evidence']):
            evidence(item, row['strategy'] + ':' + str(index))
        check(old_cases[row['strategy']]['immutable_files'])
        source = previous_root / 'prepared' / row['strategy']
        target = Path(prepared['_root']) / 'prepared' / row['strategy']
        require(all((source / name).read_bytes() == (target / name).read_bytes() for name in INPUTS), 'Reused control input bytes changed')
        accepted_row = next(item for item in read(previous_root / 'ledger.json')['runs'] if item['strategy'] == row['strategy'])
        require(accepted_row['status'] == 'PASS', 'Reused accepted row did not pass')
        for name in ('validation.json', 'preflight.json', 'postflight.json', 'aggregate.json'):
            require(read(source / name)['status'] == 'PASS', 'Missing accepted successful gate: ' + name)
        artifacts = row.get('accepted_artifact_identity', {})
        required_artifacts = ['online-summary.json', 'validation.json', 'preflight.json', 'postflight.json', 'aggregate.json',
                              'packet-counts.csv', 'pair-state.csv', 'network-resources.csv', 'replica-ready.csv', 'simulator-host/resource.json']
        require(all(str((source / name).resolve()) in artifacts for name in required_artifacts), 'Reused result/host artifacts are not fully pinned')
        if row['strategy'] == 'multicast-v2':
            require(all(str((source / name).resolve()) in artifacts for name in ('multicast-stats.csv', 'multicast-lifecycle.json', 'multicast-groups.csv')), 'Reused MC output identity incomplete')
        check(artifacts)
    return {row['strategy']: row for row in decisions}


def collect(directory, strategy, provenance, verified):
    directory = Path(directory)
    summary, c = read(directory / 'online-summary.json'), read(directory / 'config.json')
    with (directory / 'packet-counts.csv').open() as stream:
        packets = list(csv.DictReader(stream))
    n, timeline = c['planner_input']['npus'], summary['timeline']
    packet_totals = Counter()
    for row in packets:
        packet_totals[row['kind']] += int(row['packets'])
    weights = [row for row in c['transfers'] if row['stage'] == 2]
    logical_payload = sum(row['bytes'] for row in weights)
    logical_packets = sum((row['bytes'] + c['runtime']['segment_bytes'] - 1) // c['runtime']['segment_bytes'] for row in weights)
    source_wire = sum(int(row['wire_bytes']) for row in packets if int(row['node']) < n and row['kind'] in ('weight_write', 'multicast_v2'))
    downstream_wire = sum(int(row['wire_bytes']) for row in packets if int(row['node']) == n and row['kind'] == 'weight_write')
    envelope_count = packet_totals['multicast_v2']
    source_payload, branches, singleton_packets, groups = logical_payload, 0, logical_packets, 0
    details = {}
    if strategy == HYBRID:
        details = read(directory / 'hybrid-summary.json')
        total = details['totals']
        source_payload = total['envelope_payload_bytes'] + total['native_fallback_payload_bytes']
        branches = (total['branch_wire_bytes'] - total['branch_payload_bytes']) // 78
        singleton_packets = sum((g['bytes'] + c['runtime']['segment_bytes'] - 1) // c['runtime']['segment_bytes'] for g in c['hybrid_groups'] if len(g['members']) == 1)
        groups = total['groups']
    elif strategy == 'multicast-v2':
        with (directory / 'multicast-stats.csv').open() as stream:
            stats = list(csv.DictReader(stream))
        source_payload = sum(int(row['payload_bytes']) for row in stats)
        branches = sum(int(row['envelopes']) * int(row['fanout']) for row in stats)
        singleton_packets = sum(int(row['native_singleton_packets']) for row in stats)
        groups = len(stats)
    resource = read(directory / 'simulator-host/resource.json')
    return dict(strategy=strategy, provenance=provenance, result_directory=str(directory), status='PASS',
                layer_latency_ps=summary['layer_latency_ps'], weight_duration_ps=timeline['weights_end'] - timeline['planning_end'],
                timeline=timeline, stage_intervals=summary['stage_intervals'], compute_intervals=summary['compute_intervals'],
                planning_duration_ps=timeline['planning_end'] - timeline['layer_start'], reroute_duration_ps=timeline['reroute_end'] - timeline['planning_end'],
                source_weight_payload_bytes=source_payload, source_weight_wire_bytes=source_wire,
                downstream_native_weight_wire_bytes=downstream_wire, logical_weight_payload_bytes=logical_payload,
                logical_weight_packets=logical_packets, multicast_envelopes=envelope_count, multicast_branches=branches,
                native_singleton_packets=singleton_packets, logical_groups=groups,
                full_layer_tpack_packets=packet_totals['transport_ack'], full_layer_taack_packets=packet_totals['transaction_response'],
                remote_WQEs=summary['remote_WQEs'], TA_count=summary['TA_count'], pair_jetties=summary['jettys'],
                combine_fnv1a64=summary['combine_fnv1a64'], executed_graph_fnv1a64=summary['executed_graph_fnv1a64'],
                assignments=summary['assignments'], replicas=summary['replicas'], per_npu_load=summary['per_npu_load'],
                all_native_pairs_safe=True, verification=verified,
                wall_seconds=resource['wall_seconds'], peak_rss_kib=resource['peak_rss_kib'],
                sampled_peak_tree_rss_bytes=resource['sampled_peak_tree_rss_bytes'],
                user_cpu_seconds=resource['user_cpu_seconds'], system_cpu_seconds=resource['system_cpu_seconds'], hybrid=details)


def run_five(args):
    root = args.private.resolve()
    ledger, prepared, approval = read(root / 'ledger.json'), read(root / 'prepared-manifest.json'), read(args.approval)
    require(ledger['status'] == 'PREPARED', 'No implicit resume or rerun')
    require(approval.get('status') == 'PASS' and approval.get('approved_to_run') is True, 'Explicit formal approval missing')
    require(approval.get('independent_reviewer'), 'Independent read-only reviewer missing')
    require(approval.get('prepared_manifest_sha256') == sha(root / 'prepared-manifest.json') == ledger['prepared_manifest_sha256'], 'Approval does not bind exact prepared five')
    require(prepared['tokens'] == 256 and prepared['strategies'] == list(STRATEGIES), 'Formal scope drift')
    require([row['strategy'] for row in prepared['runs']] == list(STRATEGIES) == [row['strategy'] for row in ledger['runs']], 'Exactly five rows required')
    for key in ('phase_b', 'old_mode_regression', 'independent_review', 'reuse_decision'):
        bound = evidence(approval.get(key, {}), key)
        if key == 'phase_b':
            require(bound.get('phase') == 'B' and bound.get('coverage', {}).get('status') == 'PASS' and not bound['coverage'].get('missing'), 'Phase B complete coverage gate missing')
            require(bound.get('rows') and all(row.get('status') == 'PASS' for row in bound['rows']), 'Phase B row coverage incomplete')
        if key == 'old_mode_regression':
            require(len(bound.get('rows', [])) == 12 and all(row.get('status') == 'PASS' for row in bound['rows']), 'Twelve exact old-mode paired regressions required')
        if key in ('independent_review', 'reuse_decision'):
            require(bound.get('prepared_manifest_sha256') == approval['prepared_manifest_sha256'], 'Review/prepared manifest mismatch')
    require(sha(root / 'identity.json') == prepared['identity_sha256'] and sha(root / 'prepared/preparation.json') == prepared['preparation_sha256'], 'Preparation/identity drift')
    identity = read(root / 'identity.json')
    identity.update(freeze([args.approval, *(approval[key]['path'] for key in ('phase_b', 'old_mode_regression', 'independent_review', 'reuse_decision'))]))
    check(identity)
    prepared['_sha256'], prepared['_root'] = sha(root / 'prepared-manifest.json'), str(root)
    reuse = reuse_decisions(approval['reuse_decision']['path'], prepared, identity)
    for row, live_row in zip(prepared['runs'], ledger['runs']):
        directory = root / 'prepared' / row['strategy']
        require(live_row['command'] == row['command'] == simulator(prepared['binary'], directory, row['strategy']), 'Frozen formal command drift')
        require(live_row['immutable_files'] == row['immutable_files'], 'Ledger input identity drift')
        check(row['immutable_files'])
        require(sha(root / 'prepared' / row['strategy'] / 'preflight.json') == row['preflight_sha256'], 'Preflight drift')
    resource_admission(root, simulation=True)
    ledger.update(status='RUNNING', approval_sha256=sha(args.approval))
    write(root / 'ledger.json', ledger)
    results = []
    try:
        for row in ledger['runs']:
            strategy = row['strategy']
            directory = root / 'prepared' / strategy
            if strategy in reuse and reuse[strategy]['reuse']:
                source = Path(prepared['accepted_campaign']) / 'prepared' / strategy
                row.update(status='REUSED', reuse_reasons=reuse[strategy]['reasons'])
                aggregate = collect(source, strategy, 'REUSED', dict(status='PASS', original_accepted_gates=True, reuse_decision_sha256=sha(approval['reuse_decision']['path'])))
            else:
                resource_admission(root, simulation=True)
                row['status'] = 'RUNNING'
                write(root / 'ledger.json', ledger)
                check(row['immutable_files'])
                stage(row['command'], directory / 'simulator-host', identity)
                require(read(directory / 'validation.json')['status'] == 'PASS', 'Online validation failed')
                stage(preflight_command(directory, prepared['graph_tool'], directory / 'postflight.json', True), directory / 'postflight-host', identity)
                stage([sys.executable, H / 'verify.py', directory, '--out', directory / 'independent.json'], directory / 'independent-host', identity)
                stage([sys.executable, E / 'qwen-roofline-compute/verify-compute.py', directory, '--expected-model=roofline'], directory / 'compute-host', identity)
                check(row['immutable_files'])
                aggregate = collect(directory, strategy, 'NEW', read(directory / 'independent.json'))
                row['status'] = 'PASS'
            row['aggregate'] = aggregate
            results.append(aggregate)
            write(root / 'ledger.json', ledger)
            print('VERIFIED N256 ' + strategy + ' ' + aggregate['provenance'], flush=True)
        require(len({row['combine_fnv1a64'] for row in results}) == 1, 'Five-strategy logical output mismatch')
        balanced = [row for row in results if row['strategy'] != 'no-balancing']
        require(len({semantic(row['per_npu_load']) for row in balanced}) == 1, 'Balanced compute assignment/load mismatch')
        by_strategy = {row['strategy']: row for row in results}
        require(by_strategy['chunk-streaming']['executed_graph_fnv1a64'] == by_strategy[HYBRID]['executed_graph_fnv1a64'], 'CS/hybrid executed graph mismatch')
        require(by_strategy['no-balancing']['replicas'] == 0 and by_strategy['no-balancing']['weight_duration_ps'] == 0, 'NoBal weight baseline contract')
        check(identity)
        ledger['status'] = 'PASS'
        write(root / 'five-strategy-results.json', dict(status='PASS', base=BASE, tokens=256, cases=results,
              limitations=['One deterministic N256 case per strategy, not stability or crossover evidence.',
                           'Native original controls are unchanged; host costs distinguish REUSED from NEW.',
                           'NoBal is main-only. Its zero weight duration is not a speedup denominator.',
                           'Actual opportunistic merge coverage is measured, not assumed from ideal graph grouping.']))
        keys = ['strategy', 'provenance', 'layer_latency_ps', 'weight_duration_ps', 'source_weight_payload_bytes', 'source_weight_wire_bytes',
                'downstream_native_weight_wire_bytes', 'multicast_envelopes', 'multicast_branches', 'native_singleton_packets',
                'full_layer_tpack_packets', 'full_layer_taack_packets', 'remote_WQEs', 'TA_count', 'pair_jetties', 'wall_seconds', 'peak_rss_kib']
        with (root / 'results.csv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n')
            writer.writeheader()
            writer.writerows({key: row[key] for key in keys} for row in results)
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
    for key in ('private', 'accepted-campaign', 'graph-tool', 'binary', 'identity'):
        prep.add_argument('--' + key, type=Path, required=True)
    run = sub.add_parser('execute')
    for key in ('private', 'approval'):
        run.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    require(__debug__ and os.environ.get('PYTHONOPTIMIZE', '') in ('', '0'), 'Assertions must execute')
    os.umask(0o077)
    prepare_run(args) if args.phase == 'prepare' else run_five(args)

if __name__ == '__main__':
    main()
