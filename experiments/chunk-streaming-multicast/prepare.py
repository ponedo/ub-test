#!/usr/bin/env python3
"""Freeze exactly five N256 inputs from the one accepted cached natural plan."""
import argparse
import os
import shutil
from common import *
import adapter

PLAN_SEMANTIC = '5df5e9b331e487985f0b53a8e0485e9acc477bd71d756430029f8b7427bed06d'
MAPPING_SHA = '17c7c0a71bfd4062650f2d952f0fb9e451641d1c4680f28aecafe5060e71f959'


def prepare(accepted_campaign, graph_tool, out):
    accepted_campaign, out = Path(accepted_campaign).resolve(), Path(out).resolve()
    require(not out.exists(), 'Fresh preparation directory required')
    ledger = read(accepted_campaign / 'ledger.json')
    require(ledger['status'] == 'PASS', 'Accepted CS/MC campaign did not pass')
    previous = read(accepted_campaign / 'prepared-manifest.json')
    require(previous['tokens'] == 256 and previous['strategies'] == ['chunk-streaming', 'multicast-v2'], 'Wrong accepted campaign')
    check(read(accepted_campaign / 'identity.json'))
    for row in previous['runs']:
        check(row['immutable_files'])
    source = accepted_campaign / 'prepared/shared-direct'
    config, plan = read(source / 'config.json'), read(source / 'plan.json')
    semantic_plan = dict(plan)
    semantic_plan.pop('cpu_wall_ns', None)
    require(semantic(semantic_plan) == PLAN_SEMANTIC, 'Wrong cached natural plan')
    require(semantic(config['planner_input']['mapping']) == MAPPING_SHA, 'Wrong exact N256 routing')
    require(len(config['planner_input']['mapping']) == 256, 'Only N256 is authorized')
    require(sum(x['kind'] == 'replica' for x in plan['physical']) == 44, 'Cached natural replicas changed')
    out.mkdir(parents=True)
    os.environ['RELAY_GRAPH_TOOL'] = str(Path(graph_tool).resolve())
    result = dict(status='PREPARED', base=BASE, tokens=256, serialized_layer=37,
                  accepted_campaign=str(accepted_campaign), accepted_manifest_sha256=sha(accepted_campaign / 'prepared-manifest.json'),
                  shared_plan_semantic_sha256=PLAN_SEMANTIC, mapping_sha256=MAPPING_SHA, cases=[])
    for strategy in STRATEGIES:
        target = out / strategy
        if strategy in ('chunk-streaming', 'multicast-v2'):
            target.mkdir()
            for name in INPUTS:
                shutil.copyfile(accepted_campaign / 'prepared' / strategy / name, target / name)
        elif strategy == HYBRID:
            adapter.from_cs_control(out / 'chunk-streaming', target)
        else:
            adapter.emit(source, RELAY, strategy, target)
        c = read(target / 'config.json')
        if strategy != 'no-balancing':
            require((target / 'plan.json').read_bytes() == (source / 'plan.json').read_bytes(), 'Balanced plan bytes changed')
            require((target / 'assignments.csv').read_bytes() == (source / 'assignments.csv').read_bytes(), 'Balanced assignments bytes changed')
        else:
            require(c['mode'] == 'no-balancing' and not any(x['kind'] == 'replica' for x in read(target / 'plan.json')['physical']), 'NoBal must be genuinely main-only')
            require(not c['runtime']['planning_ns'] and not c['runtime']['reroute_ns'], 'NoBal planning/reroute changed')
        result['cases'].append(dict(strategy=strategy, weight_transfers=sum(x['stage'] == 2 for x in c['transfers']),
            transfer_count=len(c['transfers']), remote_pairs=len({(x['source'], x['target']) for x in c['transfers'] if x['source'] != x['target']}),
            groups=len(c.get('hybrid_groups', c.get('multicast_groups', []))), immutable_files=freeze(target / name for name in INPUTS)))
    write(out / 'preparation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('accepted-campaign', 'graph-tool', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    prepare(args.accepted_campaign, args.graph_tool, args.out)
    print('PREPARED five N256 inputs from one cached plan. No simulator ran.')

if __name__ == '__main__':
    main()
