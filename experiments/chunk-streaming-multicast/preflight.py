#!/usr/bin/env python3
"""Independent original-graph oracle plus exact fixed-member hybrid contracts."""
import argparse
import csv
import hashlib
import subprocess
import tempfile
from collections import Counter, defaultdict
from common import *


def expected_groups(config, plan):
    """Independent partition, intentionally does not call the new adapter."""
    physical = {row['id']: row for row in plan['physical']}
    require(len(physical) == len(plan['physical']), 'Duplicate physical ID')
    require(all(type(pid) is int and 0 <= pid < 2**32 for pid in physical), 'Physical ID bounds')
    edges = [row for row in config['transfers'] if row['stage'] == 2]
    relayed = set()
    for edge in edges:
        if physical[edge['source_physical']]['kind'] == 'replica':
            relayed.add(physical[edge['source_physical']]['expert'])
    main_ranges = defaultdict(list)
    for edge in edges:
        if physical[edge['source_physical']]['kind'] == 'main':
            main_ranges[(physical[edge['physical']]['expert'], edge['offset'], edge['bytes'])].append((edge['task'], edge['physical']))
    keys, ordered = {}, []
    tasks = set()
    for edge in edges:
        require(edge['task'] not in tasks, 'Duplicate logical task')
        tasks.add(edge['task'])
        require(all(type(edge[key]) is int and 0 <= edge[key] < 2**32 for key in ('task', 'source', 'target', 'source_physical', 'physical', 'offset', 'bytes')), 'Task/physical/range unsigned bounds')
        require(edge['source'] != edge['target'], 'Hybrid local weight edge unsupported')
        require(edge['dependencies'] == sorted(set(edge['dependencies'])) and all(type(task) is int and 0 <= task < len(config['transfers']) for task in edge['dependencies']), 'Canonical dependency IDs')
        src, dst = physical[edge['source_physical']], physical[edge['physical']]
        require(src['expert'] == dst['expert'] and src['rank'] == edge['source'] and dst['rank'] == edge['target'], 'Hybrid physical provenance')
        role = 'stage2' if src['kind'] == 'replica' else 'stage1' if src['expert'] in relayed else 'direct-fallback'
        if src['kind'] == 'replica':
            parent_rows = main_ranges[(src['expert'], edge['offset'], edge['bytes'])]
            parents = [task for task, target in parent_rows]
            require(edge['dependencies'] == parents and parents, 'Original all-main-edge GroupChunk dependencies')
            require(any(target == src['id'] for task, target in parent_rows), 'Relay source chunk coverage')
        else:
            require(not edge['dependencies'], 'Main-origin edge cannot gain a dependency')
        identity = (src['expert'], src['id'], src['rank'], edge['offset'], edge['bytes'], role, tuple(edge['dependencies']))
        if identity not in keys:
            group = dict(group=len(ordered) + 1, graph_role=role, expert=src['expert'], source=src['rank'],
                         source_physical=src['id'], offset=edge['offset'], bytes=edge['bytes'], dependencies=list(edge['dependencies']), members=[])
            keys[identity] = group
            ordered.append(group)
        group = keys[identity]
        require(not any(member['target'] == edge['target'] for member in group['members']), 'Duplicate fixed group target')
        require(edge['bytes'] > 0 and edge['offset'] >= 0, 'Empty/negative group range')
        if role == 'direct-fallback':
            require(edge['offset'] == 0 and edge['bytes'] == config['runtime']['weight_bytes'] and not edge['dependencies'], 'CS fallback must remain whole-expert')
        group['members'].append(dict(task=edge['task'], target=edge['target'], physical=edge['physical']))
    return ordered


def check_groups(config, plan):
    groups = expected_groups(config, plan)
    require(config.get('hybrid_groups') == groups, 'Fixed transport groups differ from exact ordered graph partition')
    require(config.get('weight_transport') == dict(schema_version=1, selector='cs-mc', policy='opportunistic-full-fixed-group-or-immediate-native', graph_kind=2, graph_strategy='chunk-streaming', group_id_order='first-weight-task-occurrence'), 'Hybrid transport selector/policy')
    require(len(config['transfers']) <= 131072, 'Hybrid total task lookup capacity')
    require(config['planner_input']['npus'] <= 64 and 1 <= config['runtime']['segment_bytes'] <= 4096, 'Codec node/segment bound')
    require(len(groups) <= 65536 and sum(len(g['members']) for g in groups) <= 65536, 'Hybrid finite spec/member capacity')
    require(all(1 <= len(g['members']) <= 63 for g in groups), 'Hybrid fanout capacity')
    require(sum(1 + len(g['members']) + len(g['dependencies']) for g in groups) <= 131072, 'Finite descriptor/dependency capacity')
    require(len({(x['source'], x['target']) for x in config['transfers'] if x['source'] != x['target']}) <= 8192, 'Directed Jetty capacity')
    return dict(operations=len(groups), members=sum(len(g['members']) for g in groups),
                multi_target_operations=sum(len(g['members']) > 1 for g in groups),
                singleton_operations=sum(len(g['members']) == 1 for g in groups),
                roles=dict(Counter(g['graph_role'] for g in groups)),
                perfect_merge_source_payload_lower_bound=sum(g['bytes'] for g in groups),
                original_logical_payload_bytes=sum(g['bytes'] * len(g['members']) for g in groups),
                native_weight_packets=sum((g['bytes'] + config['runtime']['segment_bytes'] - 1) // config['runtime']['segment_bytes'] * len(g['members']) for g in groups),
                note='Perfect all-group payload is a lower bound, not an executed-envelope assertion.')


def compare_cs_bytes(directory, control):
    directory, control = Path(directory), Path(control)
    require(directory.resolve() != control.resolve(), 'Hybrid input cannot alias its CS reference')
    for name in GRAPH_FILES:
        require((directory / name).read_bytes() == (control / name).read_bytes(), 'CS byte/order identity failed: ' + name)
    actual, reference = read(directory / 'config.json'), read(control / 'config.json')
    require(reference['weight_strategy'] == 'chunk-streaming', 'Reference is not CS')
    clean = json.loads(json.dumps(actual))
    for key in ('hybrid_groups', 'weight_transport'):
        clean.pop(key, None)
    clean['weight_strategy'] = 'chunk-streaming'
    for name in ('runtime', 'parameters'):
        clean[name]['weight_strategy'] = 'chunk-streaming'
    require(clean == reference, 'CS config changed beyond strategy identity/transport metadata')
    return {name: sha(directory / name) for name in GRAPH_FILES}


def check_directory(directory, graph_tool, cs_control=None, execution_summary=None, formal=False):
    directory = Path(directory).resolve()
    config, plan = read(directory / 'config.json'), read(directory / 'plan.json')
    hybrid = config.get('weight_strategy') == HYBRID
    accepted = load('accepted_cs_mc_preflight', E / 'ultraep-multicast-integration/preflight.py')
    if hybrid:
        require(cs_control is not None, 'Hybrid requires independent unchanged CS reference')
        identical = compare_cs_bytes(directory, cs_control)
        group_info = check_groups(config, plan)
        normalized = json.loads(json.dumps(config))
        normalized['weight_strategy'] = 'chunk-streaming'
        for key in ('runtime', 'parameters'):
            normalized[key]['weight_strategy'] = 'chunk-streaming'
        # A temporary read-only view lets the unchanged checker validate strategy2.
        # Never rewrite accepted or candidate inputs to satisfy a checker.
        with tempfile.TemporaryDirectory(prefix='cs-mc-preflight-') as temporary:
            view = Path(temporary)
            for item in directory.iterdir():
                if item.name != 'config.json' and item.is_file():
                    (view / item.name).symlink_to(item)
            write(view / 'config.json', normalized)
            result = accepted.check(view, Path(graph_tool).resolve(), execution_summary)
        result['input_sha256'] = sha(directory / 'input.txt')
        result.update(strategy=HYBRID, graph_strategy='chunk-streaming', graph_kind=2, cs_byte_identity=identical, grouping=group_info)
    else:
        result = accepted.check(directory, Path(graph_tool).resolve(), execution_summary)
        result['strategy'] = 'no-balancing' if config['mode'] == 'no-balancing' else config['weight_strategy']
    # The original checker reconstructs from config; additionally bind the stored
    # graph input/output bytes to the actual accepted standalone graph oracle.
    graph_output = subprocess.run([str(Path(graph_tool).resolve())], input=(directory / 'graph-input.txt').read_bytes(), capture_output=True, check=True).stdout
    require(graph_output == (directory / 'weight-edges.csv').read_bytes(), 'Stored ordered weight graph differs byte-for-byte from native graph oracle')
    require(int((directory / 'graph-input.txt').read_text().split()[0]) == (2 if hybrid else accepted.KINDS[config['weight_strategy']]), 'Stored graph input strategy')
    if formal:
        pc, p = config['planner_input'], config['runtime']
        require(len(pc['mapping']) == 256 and pc['npus'] == 64 and pc['experts'] == 128 and pc['top_k'] == 8, 'Only frozen N256 formal workload')
        for key, value in dict(model_dim=4096, ff_dim=1536, matrices=3, dtype_bytes=2, weight_dtype_bytes=1,
                               weight_bytes=18874368, segment_bytes=1024, link_gbps=3136, link_delay_ns=20).items():
            require(p.get(key) == value, 'Formal runtime drift: ' + key)
        require(all(p[key] == value for key, value in RELAY.items()), 'Formal relay/chunk drift')
        if hybrid:
            require(group_info['members'] == 23079 and group_info['operations'] == 13844 and group_info['multi_target_operations'] == 9233, 'Formal CS graph/group count drift')
            require(group_info['roles'] == {'stage1': 4608, 'stage2': 9216, 'direct-fallback': 20}, 'Formal graph role count drift')
            require(group_info['perfect_merge_source_payload_lower_bound'] == 23 * 18874368, 'Formal ideal payload bound drift')
            require(result['executed_graph_sha256'] == '1aa978dde5e8f116ec308a24576ea754f17639af61d0dd611139074f956c236a', 'Formal canonical CS graph drift')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--graph-tool', type=Path, required=True)
    parser.add_argument('--cs-control', type=Path)
    parser.add_argument('--execution-summary', type=Path)
    parser.add_argument('--formal', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = check_directory(args.directory, args.graph_tool, args.cs_control, args.execution_summary, args.formal)
    except Exception as exc:
        result = dict(status='FAIL', error=str(exc))
        if args.out:
            write(args.out, result)
        print(json.dumps(result), file=sys.stderr)
        return 2
    if args.out:
        write(args.out, result)
    print(json.dumps(result, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
