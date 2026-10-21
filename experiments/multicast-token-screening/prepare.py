#!/usr/bin/env python3
"""Emit the fixed N256 pair from ONE cached natural plan; never call a solver."""
import argparse
from collections import Counter
import os
import shutil
from common import *

def prepare(source, routing, manifest, counts, graph_tool, out):
    require(not out.exists(), 'Fresh preparation directory required')
    for name, expected in SOURCE_SHA.items():
        require(sha(source / name) == expected, 'Cached N256 source drift: ' + name)
    require(sha(routing) == ROUTING_SHA, 'Wrong real source routing')
    require(semantic_plan(source / 'plan.json') == PLAN_SEMANTIC, 'Wrong natural plan')
    config, plan = read(source / 'config.json'), read(source / 'plan.json')
    require(semantic(config['planner_input']['mapping']) == MAPPING_SHA, 'Wrong routing mapping')
    require(len(config['planner_input']['mapping']) == 256, 'Only 256 tokens authorized')
    out.mkdir(parents=True)
    accepted = load('accepted_real_preparation', E / 'qwen-real-minimal/prepare.py')
    data, mapping = accepted.load_routing(routing, tokens=256)
    accepted.verify_source(data, 37, manifest, counts, out / 'source-audit')
    require(mapping == config['planner_input']['mapping'], 'Cached input differs from exact raw prefix')
    direct = out / 'shared-direct'
    direct.mkdir()
    for name in SOURCE_SHA:
        shutil.copyfile(source / name, direct / name)
    # Propagation remains 20 ns. The independent native allocator remains 5 ns.
    for key in ('runtime', 'parameters'):
        require(config[key]['link_delay_ns'] == 20, 'Unexpected propagation delay')
        config[key]['link_gbps'] = 3136
    write(direct / 'config.json', config)
    lines = (direct / 'input.txt').read_text().splitlines()
    fields = lines[0].split()
    require(fields[3] == '256' and fields[12:] == ['100', '20'], 'Cached input header drift')
    fields[12] = '3136'
    lines[0] = ' '.join(fields)
    (direct / 'input.txt').write_text('\n'.join(lines) + '\n')
    adapter = load('accepted_v2_adapter', E / 'ultraep-multicast-integration/adapter.py')
    os.environ['RELAY_GRAPH_TOOL'] = str(graph_tool.resolve())
    replicas = [p for p in plan['physical'] if p['kind'] == 'replica']
    fanout = Counter(p['expert'] for p in replicas)
    require(len(replicas) == 44 and len(fanout) == 21 and max(fanout.values()) == 5,
            'Natural fanout unexpectedly changed')
    result = dict(status='PREPARED', base=BASE, tokens=256, serialized_layer=37,
                  link_gbps=3136, propagation_ns=20, allocator_ns=5, jetty_ta_window=512,
                  tp_packet_window=1000, roofline_tflops=100, hbm_GBps=2692,
                  shared_plan_semantic_sha256=PLAN_SEMANTIC, mapping_sha256=MAPPING_SHA,
                  replicas=44, groups=21, max_fanout=5,
                  fanout_histogram=dict(sorted(Counter(fanout.values()).items())), cases=[])
    for strategy in STRATEGIES:
        target = out / strategy
        emitted, _ = adapter.emit(direct, RELAY, strategy, target)
        require(sha(target / 'plan.json') == SOURCE_SHA['plan.json'], 'Plan copied incorrectly')
        require(sha(target / 'assignments.csv') == SOURCE_SHA['assignments.csv'], 'Assignments copied incorrectly')
        weights = [x for x in emitted['transfers'] if x['stage'] == 2]
        remote = [x for x in emitted['transfers'] if x['source'] != x['target']]
        pairs = {(x['source'], x['target']) for x in remote}
        require(len(weights) <= 65536, 'Bounded diagnostic weight-transfer cap exceeded')
        require(len(emitted.get('multicast_groups', [])) <= 1024, 'Bounded group cap exceeded')
        require(len(pairs) <= 8192, 'Bounded Jetty cap exceeded')
        result['cases'].append(dict(strategy=strategy, weight_transfers=len(weights),
            transfer_count=len(emitted['transfers']), remote_pairs=len(pairs),
            logical_tas_upper_bound=sum((x['bytes'] + 1023) // 1024 for x in remote),
            immutable_files=freeze(target / name for name in INPUTS)))
    write(out / 'preparation.json', result)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'routing', 'manifest', 'counts', 'graph-tool', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    result = prepare(args.source.resolve(), args.routing.resolve(), args.manifest.resolve(),
                     args.counts.resolve(), args.graph_tool.resolve(), args.out.resolve())
    print('PREPARED N256 natural-plan pair: ' + ', '.join(x['strategy'] for x in result['cases']))

if __name__ == '__main__':
    main()
