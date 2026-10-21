#!/usr/bin/env python3
"""Independent hybrid conservation, immediate submission and lifecycle verifier."""
import argparse
import csv
import subprocess
from collections import Counter, defaultdict
import heapq
from common import *
from preflight import check_groups


def rows(root, name):
    with (Path(root) / name).open() as stream:
        return list(csv.DictReader(stream))


def integer(row, key):
    result = int(row[key])
    require(result >= 0, 'Negative counter: ' + key)
    return result


def verify_hybrid(root, fault=False, require_both_hops=False):
    root = Path(root)
    c, plan = read(root / 'config.json'), read(root / 'plan.json')
    require(c['weight_strategy'] == HYBRID, 'Not a hybrid result')
    group_contract = check_groups(c, plan)
    online, validation = read(root / 'online-summary.json'), read(root / 'validation.json')
    require(validation['status'] == 'PASS', 'Online payload/dependency validation did not pass')
    life, summary = read(root / 'hybrid-lifecycle.json'), read(root / 'hybrid-summary.json')
    require(life['status'] == 'PASS' and life['all_native_pairs_safe'] is True, 'Native final safe state')
    for key in ('pending_associations', 'pending_members', 'active_codecs'):
        require(integer(life, key) == 0, 'Undrained hybrid state: ' + key)
    require(integer(life, 'allocated_codecs') == integer(life, 'retired_codecs'), 'Codec lifetime leak')
    require(integer(life, 'max_live_codecs') <= len(c['hybrid_groups']), 'Live codec capacity')
    require(integer(life, 'descriptor_entries') == sum(1 + len(g['members']) + len(g['dependencies']) for g in c['hybrid_groups']), 'Missing finite descriptors')
    require(integer(life, 'max_rss_bytes') <= 6 * 1024**3 and integer(life, 'rss_limit_bytes') == 6 * 1024**3, 'Hybrid RSS bound')
    require(integer(life, 'max_stage2_tasks') == 65536 and integer(life, 'max_entries') == 131072, 'Observer finite bounds changed')
    pairs = {(x['source'], x['target']) for x in c['transfers'] if x['source'] != x['target']}
    require(integer(life, 'pair_jetties') == len(pairs), 'Hybrid pair Jetty reuse')
    weight_sources = {g['source'] for g in c['hybrid_groups']}
    proxy_pairs = {(a, b) for a, b in pairs | {(b, a) for a, b in pairs} if a in weight_sources}
    require(integer(life, 'pair_proxies') == len(proxy_pairs), 'Hybrid directed native TP/proxy identity')
    actual = rows(root, 'hybrid-groups.csv')
    expected = [(g, m) for g in c['hybrid_groups'] for m in g['members']]
    require(len(actual) == len(expected), 'Missing/extra hybrid member')
    by_task = {}
    done_by_group = defaultdict(list)
    for row, (g, m) in zip(actual, expected):
        for key, value in dict(group=g['group'], expert=g['expert'], source=g['source'], source_physical=g['source_physical'],
                               offset=g['offset'], bytes=g['bytes'], **m).items():
            require(integer(row, key) == value, 'Hybrid member identity/order: ' + key)
        require(row['graph_role'] == g['graph_role'] and row['dependencies'] == ';'.join(map(str, g['dependencies'])), 'Hybrid role/ordered parent identity')
        task = m['task']
        require(task not in by_task, 'Duplicate hybrid member task')
        by_task[task] = row
        require(integer(row, 'first_send_bytes') == g['bytes'], 'Original per-member first-send byte coverage')
        ready = integer(row, 'logical_ready_ps')
        require(integer(row, 'native_submit_ps') == ready, 'Native WQE submission was delayed')
        require(ready <= integer(row, 'first_send_ps') <= integer(row, 'first_send_done_ps') <= integer(row, 'receiver_ready_ps') <= integer(row, 'sender_complete_ps') <= integer(row, 'group_complete_ps'), 'Hybrid child event order')
        done_by_group[g['group']].append(row)
    for g in c['hybrid_groups']:
        expected_ready = max([online['timeline']['planning_end']] + [integer(by_task[task], 'receiver_ready_ps') for task in g['dependencies']])
        members = done_by_group[g['group']]
        require(all(integer(row, 'logical_ready_ps') == expected_ready for row in members), 'Original exact CS readiness/GroupChunk timing changed')
        complete = max(integer(row, 'sender_complete_ps') for row in members)
        require(all(integer(row, 'group_complete_ps') == complete for row in members), 'All-target native completion aggregation')
    require(max([online['timeline']['planning_end']] + [integer(row, 'receiver_ready_ps') for row in actual]) == online['timeline']['weights_end'], 'Weights end must use target readiness')
    stats = rows(root, 'hybrid-stats.csv')
    require(len(stats) == len(c['hybrid_groups']), 'Missing/extra hybrid statistics')
    totals = Counter()
    role_totals = defaultdict(Counter)
    derived_keys = ('groups', 'multi_target_groups', 'multicast_groups', 'envelopes', 'envelope_payload_bytes', 'envelope_wire_bytes',
                    'branch_payload_bytes', 'branch_wire_bytes', 'native_fallback_packets', 'native_fallback_payload_bytes',
                    'native_fallback_wire_bytes', 'original_first_send_packets', 'original_first_send_bytes', 'logical_native_wire_bytes', 'actual_source_wire_bytes')
    for row, g in zip(stats, c['hybrid_groups']):
        fan, size, segment = len(g['members']), g['bytes'], c['runtime']['segment_bytes']
        packets = (size + segment - 1) // segment
        for key in ('group', 'expert', 'source', 'source_physical', 'offset', 'bytes'):
            require(integer(row, key) == g[key], 'Hybrid statistics identity: ' + key)
        require(row['graph_role'] == g['graph_role'] and integer(row, 'fanout') == fan, 'Hybrid statistics role/fanout')
        get = lambda key: integer(row, key)
        env, envbytes = get('envelopes'), get('envelope_payload_bytes')
        fallback, fallbackbytes = get('native_fallback_packets'), get('native_fallback_payload_bytes')
        require(get('logical_packets') == packets * fan and get('logical_payload_bytes') == size * fan, 'Logical per-member packet/byte total')
        require(env <= packets and envbytes <= size and (fan > 1 or env == 0), 'Envelope coverage/fanout bound')
        require(env * fan + fallback == packets * fan and envbytes * fan + fallbackbytes == size * fan, 'Envelope/fallback exact native packet and payload conservation')
        require(get('envelope_header_bytes') == env * (24 + 76 * fan), 'Native accepted V2 envelope header model')
        require(get('envelope_wire_bytes') == envbytes + get('envelope_header_bytes'), 'Actual envelope wire accounting')
        require(get('branch_payload_bytes') == envbytes * fan and get('branch_wire_bytes') == envbytes * fan + env * fan * 78, 'Reconstructed native branch accounting')
        require(get('native_fallback_wire_bytes') == fallbackbytes + fallback * 78, 'Original native fallback accounting')
        require(get('association_peak') <= get('association_limit') and get('association_restored') == env * fan, 'Envelope-only association accounting')
        if env:
            require(get('first_envelope_offset') < get('last_envelope_end') <= size, 'Actual envelope covered range')
        require(get('group_complete_ps') == integer(done_by_group[g['group']][0], 'group_complete_ps'), 'Statistics completion identity')
        record = dict(groups=1, multi_target_groups=int(fan > 1), multicast_groups=int(env > 0),
                      envelopes=env, envelope_payload_bytes=envbytes, envelope_wire_bytes=get('envelope_wire_bytes'),
                      branch_payload_bytes=get('branch_payload_bytes'), branch_wire_bytes=get('branch_wire_bytes'),
                      native_fallback_packets=fallback, native_fallback_payload_bytes=fallbackbytes,
                      native_fallback_wire_bytes=get('native_fallback_wire_bytes'), original_first_send_packets=packets * fan,
                      original_first_send_bytes=size * fan, logical_native_wire_bytes=(size + 78 * packets) * fan,
                      actual_source_wire_bytes=get('envelope_wire_bytes') + get('native_fallback_wire_bytes'))
        totals.update(record)
        role_totals[g['graph_role']].update(record)
    for key in derived_keys:
        require(integer(summary['totals'], key) == totals[key], 'Hybrid summary does not equal exact group sum: ' + key)
    for role in ('stage1', 'stage2', 'direct-fallback'):
        for key in derived_keys:
            require(integer(summary['by_role'][role], key) == role_totals[role][key], 'Hybrid per-hop summary mismatch: ' + role + ':' + key)
    fallback = rows(root, 'hybrid-fallback.csv')
    fallback_keys = set()
    fallback_totals = defaultdict(Counter)
    for row in fallback:
        identity = row['graph_role'], row['reason']
        require(identity not in fallback_keys and row['graph_role'] in ('stage1', 'stage2', 'direct-fallback') and row['reason'], 'Duplicate/invalid actual fallback reason')
        fallback_keys.add(identity)
        count, payload, wire = (integer(row, key) for key in ('packets', 'payload_bytes', 'wire_bytes'))
        require(wire == payload + 78 * count, 'Actual fallback reason wire accounting')
        fallback_totals[row['graph_role']].update(packets=count, payload_bytes=payload, wire_bytes=wire)
    for role in ('stage1', 'stage2', 'direct-fallback'):
        for suffix, source in (('packets', 'packets'), ('payload_bytes', 'payload_bytes'), ('wire_bytes', 'wire_bytes')):
            require(fallback_totals[role][source] == role_totals[role]['native_fallback_' + suffix], 'Actual fallback pulls/reasons must conserve per-hop bytes')
    packets = rows(root, 'packet-counts.csv')
    n = c['planner_input']['npus']
    require(sum(integer(row, 'packets') for row in packets if row['kind'] == 'multicast_v2') == totals['envelopes'], 'Physical envelope path/count')
    require(not any(row['kind'] == 'multicast_v2' and integer(row, 'node') == n for row in packets), 'Switch must reconstruct native packets, not forward envelopes')
    source_wire = sum(integer(row, 'wire_bytes') for row in packets if integer(row, 'node') < n and row['kind'] in ('multicast_v2', 'weight_write'))
    downstream_wire = sum(integer(row, 'wire_bytes') for row in packets if integer(row, 'node') == n and row['kind'] == 'weight_write')
    if not fault:
        require(source_wire == totals['actual_source_wire_bytes'] and downstream_wire == totals['logical_native_wire_bytes'], 'Physical source/downstream weight wire reconciliation')
        require(integer(life, 'native_retry_packets') == 0 and integer(life, 'injected_losses') == 0, 'Unexpected formal native retry/loss')
    else:
        require(integer(life, 'injected_losses') + integer(life, 'injected_duplicates') > 0, 'Fault case did not actually inject loss/duplicate')
        require(source_wire >= totals['actual_source_wire_bytes'] and downstream_wire >= totals['logical_native_wire_bytes'], 'Fault physical path missing original traffic')
        # Exact forward and reverse retry identity/path is verified by the frozen
        # fault witness checker, not inferred from a forward-only aggregate.
    if require_both_hops:
        require(role_totals['stage1']['envelopes'] > 0 and role_totals['stage2']['envelopes'] > 0, 'Requested two-hop merge coverage absent')
    # Coverage is based on executed rows, never merely requested fixture labels.
    relays = defaultdict(set)
    intervals = []
    for g in c['hybrid_groups']:
        if g['graph_role'] == 'stage2':
            relays[g['expert']].add(g['source_physical'])
        children = done_by_group[g['group']]
        intervals.append((min(integer(row, 'first_send_ps') for row in children),
                          max(integer(row, 'sender_complete_ps') for row in children), g['expert']))
    active, active_experts, concurrent = [], Counter(), False
    for start, finish, expert in sorted(intervals):
        while active and active[0][0] <= start:
            _, old_expert = heapq.heappop(active)
            active_experts[old_expert] -= 1
            if not active_experts[old_expert]:
                del active_experts[old_expert]
        concurrent |= bool(set(active_experts) - {expert})
        heapq.heappush(active, (finish, expert))
        active_experts[expert] += 1
    coverage = dict(zero_replicas=not actual and not any(p['kind'] == 'replica' for p in plan['physical']),
                    direct_fallback=role_totals['direct-fallback']['original_first_send_bytes'] > 0,
                    resource_cleanup=True,
                    cross_expert_chunk_isolation=len({g['expert'] for g in c['hybrid_groups']}) > 1,
                    singleton_native=any(int(row['fanout']) == 1 and int(row['native_fallback_packets']) > 0 for row in stats),
                    stage1_envelope=role_totals['stage1']['envelopes'] > 0, stage2_envelope=role_totals['stage2']['envelopes'] > 0,
                    groupchunk_all_parents=any(g['graph_role'] == 'stage2' and len(g['dependencies']) > 1 for g in c['hybrid_groups']),
                    multiple_relays=any(len(value) > 1 for value in relays.values()), concurrent_experts=concurrent,
                    tail_ranges=any(g['graph_role'] != 'direct-fallback' and g['bytes'] % c['runtime']['chunk_bytes'] for g in c['hybrid_groups']),
                    lifetime_groups_gt1024=len(c['hybrid_groups']) > 1024,
                    all_native_pairs_safe=True, stale_grant=integer(life, 'invalidated_grants') > 0)
    for fanout in (2, 3, 4):
        coverage['fanout' + str(fanout)] = any(int(row['fanout']) == fanout and int(row['envelopes']) > 0 for row in stats)
    p = c['runtime']
    cut = (p['matrices'] - 1) * p['model_dim'] * p['ff_dim'] * p.get('weight_dtype_bytes', p['dtype_bytes'])
    coverage['nondivisible_shard'] = p['weight_size_kind'] == 'matrix_exact' and cut % p['chunk_bytes'] != 0 and any(g['offset'] + g['bytes'] == cut for g in c['hybrid_groups'])
    if (root / 'diagnostic-jetty-aggregates.csv').exists():
        jetty = rows(root, 'diagnostic-jetty-aggregates.csv')
        coverage['ta_window_512'] = any(int(row['window']) == 512 and int(row['max_outstanding']) == 512 and int(row['window_limited_tests']) > 0 for row in jetty)
    return dict(status='PASS', strategy=HYBRID, coverage=coverage, grouping=group_contract, actual=dict(totals),
                actual_by_role={role: dict(value) for role, value in role_totals.items()},
                two_hop_envelope_coverage=role_totals['stage1']['envelopes'] > 0 and role_totals['stage2']['envelopes'] > 0,
                native_safe=True, notes=['Immediate native submit and actual pull accounting checked.',
                'Streaming physical-TX witness and exact fault paths require the separate Phase B witness checks.'])


def expected_combine_hash(config):
    # Independent generated full logical result, preserving original assignment
    # order; physical placement and transport do not enter the byte function.
    p = config['runtime']
    size = p['model_dim'] * p['dtype_bytes']
    value = 14695981039346656037
    for assignment in config['assignments']:
        base = p['seed'] + assignment['token'] * 131 + assignment['expert'] * 71 + assignment['rank'] * 43
        transform = (assignment['expert'] * 37 + 165) & 255
        for offset in range(size):
            byte = ((base + offset * 17 + (offset >> 8) * 29) & 255) ^ transform
            value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return f'{value:016x}'


def check_physical_totals(directory):
    directory = Path(directory)
    summary = read(directory / 'online-summary.json')
    config = read(directory / 'config.json')
    require(summary['combine_fnv1a64'] == expected_combine_hash(config), 'Independent generated full combine payload hash')
    by_node_packets, by_node_bytes = Counter(), Counter()
    for row in rows(directory, 'packet-counts.csv'):
        by_node_packets[integer(row, 'node')] += integer(row, 'packets')
        by_node_bytes[integer(row, 'node')] += integer(row, 'wire_bytes')
    require(len(summary['packet_tx_per_node']) == len(summary['packet_rx_per_node']) == len(summary['byte_tx_per_node']) == len(summary['byte_rx_per_node']), 'Physical node counter dimensions')
    for node in range(len(summary['packet_tx_per_node'])):
        require(by_node_packets[node] == summary['packet_tx_per_node'][node] and by_node_bytes[node] == summary['byte_tx_per_node'][node], 'Per-node physical TX table mismatch')
    require(sum(summary['packet_tx_per_node']) == sum(summary['packet_rx_per_node']) and sum(summary['byte_tx_per_node']) == sum(summary['byte_rx_per_node']), 'Physical link TX/RX totals do not reconcile')
    for name in ('diagnostic-status.json', 'diagnostic-jetty-status.json'):
        if (directory / name).exists():
            status = read(directory / name)
            require(status.get('incomplete') is False, 'Incomplete bounded observer: ' + name)
    if (directory / 'diagnostic-jetty-status.json').exists():
        status = read(directory / 'diagnostic-jetty-status.json')
        for key in ('terminal_nonzero_jetties', 'pending_ta_observations', 'pending_source_frames', 'pending_ack_marks', 'occupancy_errors', 'unmatched_accepted_taacks'):
            require(integer(status, key) == 0, 'Undrained/inconsistent global Jetty observer: ' + key)
    return True


def check(directory, fault=False, require_both_hops=False):
    directory = Path(directory)
    subprocess.run([sys.executable, str(E / 'ultraep-multicast-integration/verify.py'), str(directory)], check=True)
    check_physical_totals(directory)
    c = read(directory / 'config.json')
    if c['weight_strategy'] == HYBRID:
        return verify_hybrid(directory, fault, require_both_hops)
    return dict(status='PASS', strategy='no-balancing' if c['mode'] == 'no-balancing' else c['weight_strategy'], coverage=dict(all_native_pairs_safe=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--fault', action='store_true')
    parser.add_argument('--require-both-hops', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    require(__debug__, 'Assertions must remain enabled')
    try:
        # The unchanged aggregate checker provides pair/credit/full-layer checks.
        # Hybrid intentionally does not enter its whole-expert MC statistics arm.
        result = check(args.root, args.fault, args.require_both_hops)
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
