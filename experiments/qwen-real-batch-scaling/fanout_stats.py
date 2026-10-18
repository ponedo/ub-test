"""Read-only placement/weight-graph audit. No planner or simulator invocation.

Ported independently from ponedo/ub-test @93bdf7fef154743738910da9e561d796f5955507
experiments/direct-weight-forward/weight-distribution.h, RelayWeightDistribution::Edges.
Input: unchanged config.json, plan.json and actual weight-edges.csv from adapter.
Output contains aggregate per-expert counts only; no token/source routing records.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from math import isqrt
from pathlib import Path

SOURCE = 'https://github.com/ponedo/ub-test/blob/93bdf7fef154743738910da9e561d796f5955507/experiments/direct-weight-forward/weight-distribution.h'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def eligibility(count, p):
    nr = min(isqrt(count), p['relay_max_relays'], count - 1) if count > 1 else 0
    gain = count - max(nr, (count - nr + nr - 1) // nr) if nr else None
    reasons = []
    if not nr:
        reasons.append('no_relay_candidate_R_le_1')
    if not p['force_relay']:
        if count < p['relay_min_replicas']:
            reasons.append('below_min_replicas')
        if gain is not None and gain < p['relay_min_fanout_gain']:
            reasons.append('below_min_fanout_gain')
    return dict(eligible=not reasons, candidate_relay_count=nr, fanout_gain=gain,
                reasons=reasons or ['force_relay' if p['force_relay'] else 'adaptive_thresholds_pass'])


def expected_graph(config, plan):
    """Reconstruct exact graph including selection, ordering and persistent rank loads."""
    p = config['runtime']; pc = config['planner_input']; n = pc['npus']
    strategy = config.get('weight_strategy', p.get('weight_strategy', 'direct'))
    require(strategy in ('direct', 'two-stage', 'chunk-streaming'), 'unknown strategy')
    b = p['weight_bytes']; chunk = p['chunk_bytes']
    cut = ((p['matrices'] - 1) * p['model_dim'] * p['ff_dim'] * p.get('weight_dtype_bytes', p['dtype_bytes'])
           if p['weight_size_kind'] == 'matrix_exact' else 0)
    require(n > 0 and b > 0 and chunk > 0 and p['relay_max_relays'] > 0 and 0 <= cut < b, 'invalid graph parameters')
    domain = p.get('domain', [])
    require(not domain or (len(domain) == n and len(set(domain)) == 1), 'multiple/invalid domains')
    rows = plan['physical']; byid = {x['id']: x for x in rows}
    require(len(rows) == len(byid), 'duplicate physical ID')
    require(all(x['kind'] in ('main', 'replica') and 0 <= x['rank'] < n for x in rows), 'invalid physical identity')
    order = plan.get('ordinal_physical_order', list(byid)) if strategy != 'direct' else list(byid)
    require(len(order) == len(rows) and set(order) == set(byid), 'invalid ordinal order')
    mains = {}; replicas = defaultdict(list)
    for pid in order:
        x = byid[pid]
        if x['kind'] == 'main':
            require(x['expert'] not in mains, 'duplicate main expert')
            mains[x['expert']] = x
        else:
            replicas[x['expert']].append(x)
    require(not (set(replicas) - set(mains)), 'orphan replicas')
    for e, reps in replicas.items():
        m = mains[e]
        require(all(x['weight_source_physical'] == m['id'] and x['weight_source_rank'] == m['rank'] and x['rank'] != m['rank'] for x in reps), 'replica provenance')
    decisions = {e: eligibility(len(replicas[e]), p) for e in mains}
    edges = []; load = [0] * n
    def edge(src, dst, off, size, scope):
        edges.append((src['id'], dst['id'], off, size, scope))
    if strategy == 'direct':
        for x in rows:
            if x['kind'] == 'replica':
                edge(mains[x['expert']], x, 0, b, 0)
        return edges, decisions, byid
    for main in sorted(mains.values(), key=lambda x: (x['rank'], x['id'])):
        reps = replicas[main['expert']]; count = len(reps); d = decisions[main['expert']]
        if not count:
            continue
        if not d['eligible']:
            load[main['rank']] += count * b
            for x in reps:
                edge(main, x, 0, b, 0)
            continue
        nr = d['candidate_relay_count']; selected = []; used_ranks = set()
        for _ in range(nr):
            best = min((j for j in range(count) if j not in selected), key=lambda j: (reps[j]['rank'] in used_ranks, load[reps[j]['rank']], reps[j]['rank'], j))
            selected.append(best); used_ranks.add(reps[best]['rank'])
        leaves = [j for j in range(count) if j not in selected]
        projected = [load[reps[j]['rank']] for j in selected]; children = [0] * nr; owners = []
        for j in range(len(leaves)):
            owner = j if j < nr else min(range(nr), key=lambda r: (projected[r], children[r], reps[selected[r]]['rank'], selected[r]))
            owners.append(owner); children[owner] += 1; projected[owner] += b
        load[main['rank']] += nr * b
        for r in range(nr):
            load[reps[selected[r]]['rank']] += children[r] * b
        ranges = [(0, b)]
        if strategy == 'chunk-streaming':
            bounds = [0] + ([cut] if cut else []) + [b]
            ranges = [(off, min(chunk, end - off)) for start, end in zip(bounds, bounds[1:]) for off in range(start, end, chunk)]
        for off, size in ranges:
            for i in selected:
                edge(main, reps[i], off, size, 0)
        for r in range(nr):
            for off, size in ranges:
                for j, leaf in enumerate(leaves):
                    if owners[j] == r:
                        edge(reps[selected[r]], reps[leaf], off, size, 2 if strategy == 'chunk-streaming' else 0)
    return edges, decisions, byid


def audit(config, plan, actual_edges):
    expected, decisions, byid = expected_graph(config, plan)
    actual = [(int(x['source_physical']), int(x['physical']), int(x['offset']), int(x['bytes']), int(x['scope'])) for x in actual_edges]
    require(Counter(actual) == Counter(expected), 'actual graph differs from exact production selection/ranges/scopes')
    require(actual == expected, 'actual graph submission order differs')
    p = config['runtime']; segment = p['segment_bytes']; require(segment > 0, 'invalid segment size')
    transfers = [x for x in config['transfers'] if x['stage'] == 2]
    core = [(x['source_physical'], x['physical'], x['offset'], x['bytes']) for x in transfers]
    require(core == [x[:4] for x in actual], 'config weight transfers differ from actual graph')
    require(len({x['task'] for x in transfers}) == len(transfers), 'duplicate transfer task IDs')
    incoming = defaultdict(list); main_chunks = defaultdict(list)
    for t in transfers:
        incoming[t['physical']].append(t['task'])
        if byid[t['source_physical']]['kind'] == 'main':
            main_chunks[(byid[t['physical']]['expert'], t['offset'], t['bytes'])].append(t['task'])
    for t, edge in zip(transfers, actual):
        src, dst, off, size, scope = edge
        require(t['source'] == byid[src]['rank'] and t['target'] == byid[dst]['rank'], 'transfer rank mismatch')
        deps = []
        if byid[src]['kind'] != 'main':
            deps = main_chunks[(byid[dst]['expert'], off, size)] if scope == 2 else incoming[src]
        require(t['dependencies'] == deps, 'transfer dependency mismatch')
    rows = []; all_relays = set()
    for e in sorted(decisions):
        physical = [x for x in byid.values() if x['expert'] == e]
        edges = [x for x in actual if byid[x[1]]['expert'] == e]
        main_edges = [x for x in edges if byid[x[0]]['kind'] == 'main']
        forwarded = [x for x in edges if byid[x[0]]['kind'] != 'main']
        relay_ids = {x[0] for x in forwarded}; relay_nodes = {byid[x]['rank'] for x in relay_ids}; all_relays |= relay_nodes
        remote = [x for x in edges if byid[x[0]]['rank'] != byid[x[1]]['rank']]
        rows.append(dict(expert=e, physical_instances_including_main=len(physical), new_replicas_excluding_main=sum(x['kind'] == 'replica' for x in physical), **decisions[e], actual_relay=bool(forwarded), relay_physical_count=len(relay_ids), relay_node_count=len(relay_nodes), main_outgoing_copies=len({x[1] for x in main_edges}), main_outgoing_tasks=len(main_edges), forwarded_tasks=len(forwarded), direct_fallback_tasks=len(edges) if not forwarded else 0, relay_tree_tasks=len(edges) if forwarded else 0, weight_tasks=len(edges), weight_wqes=len(remote), local_weight_tasks=len(edges)-len(remote), weight_tas=sum((x[3]+segment-1)//segment for x in remote), weight_bytes=sum(x[3] for x in edges), remote_weight_bytes=sum(x[3] for x in remote)))
    sums = ('physical_instances_including_main', 'new_replicas_excluding_main', 'main_outgoing_copies', 'main_outgoing_tasks', 'forwarded_tasks', 'direct_fallback_tasks', 'relay_tree_tasks', 'weight_tasks', 'weight_wqes', 'local_weight_tasks', 'weight_tas', 'weight_bytes', 'remote_weight_bytes', 'relay_physical_count')
    totals = {key: sum(r[key] for r in rows) for key in sums}
    totals.update(eligible_experts=sum(r['eligible'] for r in rows), actual_relay_experts=sum(r['actual_relay'] for r in rows), relay_node_count=len(all_relays))
    return dict(status='PASS', source=SOURCE, graph_validation='exact ordered edge fields and dependencies', strategy=config.get('weight_strategy', 'direct'), totals=totals, experts=rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    with (a.case / 'weight-edges.csv').open() as f:
        edges = list(csv.DictReader(f))
    result = audit(json.loads((a.case/'config.json').read_text()), json.loads((a.case/'plan.json').read_text()), edges)
    a.out.write_text(json.dumps(result, indent=2) + '\n')

if __name__ == '__main__':
    main()
