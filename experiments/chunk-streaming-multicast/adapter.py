#!/usr/bin/env python3
"""Accepted CS graph byte-for-byte, with separate APP transport metadata."""
import argparse
import csv
import json
import shutil
import tempfile
from collections import Counter
from common import *


def group_specs(config, plan):
    """Fixed members, stable first-occurrence operation IDs; no regrouping at runtime."""
    byid = {p['id']: p for p in plan['physical']}
    weights = [x for x in config['transfers'] if x['stage'] == 2]
    relay_experts = {byid[x['physical']]['expert'] for x in weights if byid[x['source_physical']]['kind'] != 'main'}
    groups = {}
    for x in weights:
        src, dst = byid[x['source_physical']], byid[x['physical']]
        require(src['expert'] == dst['expert'], 'Cross-expert graph edge')
        role = 'stage2' if src['kind'] != 'main' else ('stage1' if src['expert'] in relay_experts else 'direct-fallback')
        key = (x['source'], x['source_physical'], src['expert'], x['offset'], x['bytes'], role, tuple(x['dependencies']))
        if key not in groups:
            groups[key] = dict(group=len(groups) + 1, graph_role=role, expert=src['expert'], source=x['source'],
                               source_physical=x['source_physical'], offset=x['offset'], bytes=x['bytes'],
                               dependencies=list(x['dependencies']), members=[])
        g = groups[key]
        require(x['source'] == src['rank'] and x['target'] == dst['rank'], 'Rank/physical mismatch')
        require(all(m['target'] != x['target'] for m in g['members']), 'Duplicate group destination')
        g['members'].append(dict(task=x['task'], target=x['target'], physical=x['physical']))
    return list(groups.values())


def decorate_cs(config, plan, out):
    require(config['weight_strategy'] == 'chunk-streaming', 'Hybrid must start from accepted CS')
    config['weight_strategy'] = HYBRID
    for name in ('runtime', 'parameters'):
        config[name]['weight_strategy'] = HYBRID
    config['weight_transport'] = dict(schema_version=1, selector='cs-mc', policy='opportunistic-full-fixed-group-or-immediate-native',
                                    graph_kind=2, graph_strategy='chunk-streaming', group_id_order='first-weight-task-occurrence')
    config['hybrid_groups'] = group_specs(config, plan)
    write(Path(out) / 'config.json', config)
    return config, plan


def from_cs_control(source, out):
    """Pure metadata adaptation, useful for exact accepted-control reuse."""
    source, out = Path(source), Path(out)
    require(source.resolve() != out.resolve(), 'Do not modify the CS control')
    require(not out.exists(), 'Fresh hybrid output required')
    c, plan = read(source / 'config.json'), read(source / 'plan.json')
    require(c['weight_strategy'] == 'chunk-streaming', 'Not an accepted CS input')
    require((source / 'input.txt').read_text().splitlines()[1].split()[6] == '2', 'CS input graph kind')
    out.mkdir(parents=True)
    for name in GRAPH_FILES:
        shutil.copyfile(source / name, out / name)
    return decorate_cs(c, plan, out)


def emit(source, parameters, strategy, out):
    require(strategy in STRATEGIES, 'Unsupported five-strategy label')
    old = load('accepted_cs_mc_relay_adapter', E / 'multi-npu-relay/adapter.py')
    if strategy == HYBRID:
        c, plan = old.emit(source, parameters, 'chunk-streaming', out)
        return decorate_cs(c, plan, out)
    if strategy == 'no-balancing':
        direct = load('accepted_cs_mc_direct_adapter', E / 'direct-weight-forward/adapter.py')
        c = read(Path(source) / 'config.json')
        params = dict(c['parameters'], weight_strategy='direct')
        with tempfile.TemporaryDirectory(prefix='cs-mc-nobal-') as temporary:
            direct.emit(c['planner_input'], params, 'no-balancing', temporary)
            return old.emit(temporary, parameters, 'direct', out)
    accepted = load('accepted_cs_mc_v2_adapter', E / 'ultraep-multicast-integration/adapter.py')
    return accepted.emit(source, parameters, strategy, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--strategy', choices=STRATEGIES, default=HYBRID)
    parser.add_argument('--cs-control', action='store_true')
    parser.add_argument('--parameters', type=Path)
    args = parser.parse_args()
    if args.cs_control:
        require(args.strategy == HYBRID, '--cs-control is only a hybrid metadata adaptation')
        c, _ = from_cs_control(args.source, args.out)
    else:
        c, _ = emit(args.source, read(args.parameters) if args.parameters else RELAY, args.strategy, args.out)
    print(json.dumps(dict(status='PREPARED', strategy=args.strategy, weight_tasks=sum(x['stage'] == 2 for x in c['transfers']), groups=len(c.get('hybrid_groups', [])))))

if __name__ == '__main__':
    main()
