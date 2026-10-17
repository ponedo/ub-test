#!/usr/bin/env python3
"""Read-only evidence audit; writes only its requested JSON report.

This does not rerun simulations or replace the strict payload verifier.
TA accounting is a conservative upper bound: count an admitted request until
its entire WQE reports sender success. ACKed segments can remain counted.
It is not an actual native ACK-window occupancy measurement.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def window(run):
    config = json.loads((run / 'config.json').read_text())
    transfers = config['transfers']
    active = collections.Counter()
    per_task = collections.Counter()
    peaks = collections.Counter()
    completed = set()
    stages = collections.defaultdict(set)
    for x in transfers:
        if x['source'] != x['target']:
            stages[x['source'], x['target']].add(x['stage'])
    with (run / 'events.csv').open() as f:
        for row in csv.DictReader(f):
            event = row['event']
            if event not in ('ta_admitted', 'sender_complete'):
                continue
            task = int(row['task'])
            x = transfers[task]
            pair = x['source'], x['target']
            if pair[0] == pair[1]:
                raise ValueError('Local transfer used transport accounting')
            if task in completed:
                raise ValueError('Admission or duplicate success after completion')
            if event == 'ta_admitted':
                active[pair] += 1
                per_task[task] += 1
                peaks[pair] = max(peaks[pair], active[pair])
            else:
                if not per_task[task]:
                    raise ValueError('Success without admission')
                active[pair] -= per_task[task]
                if active[pair] < 0:
                    raise ValueError('Negative conservative TA count')
                completed.add(task)
    if any(active.values()) or set(per_task) != completed:
        raise ValueError('Unfinished TA or WQE accounting')
    peak = max(peaks.values(), default=0)
    return {
        'events_sha256': sha(run / 'events.csv'),
        'max_admitted_until_wqe_success_TAs_per_pair': peak,
        'default_512_window_provably_nonbinding': peak < 512,
        'directed_pairs': len(stages),
        'pairs_sharing_weight_and_token_stages': sum(
            2 in s and bool({0, 1} & s) for s in stages.values()),
        'max_pairs': ['%s->%s' % p for p, n in peaks.items() if n == peak],
    }


def baseline_case(case):
    for mode in ('no-balancing', 'chunk-streaming', 'two-stage', 'direct'):
        if case.endswith('-' + mode):
            return Path(case.removesuffix('-' + mode)) / mode
    raise ValueError('Unrecognized regression case: ' + case)


def parity(old, new):
    checked = []
    unavailable = []
    differences = []
    for p in sorted(old.rglob('*')):
        if not p.is_file() or p.name in ('summary.json', 'simulator-metrics.json'):
            continue
        rel = p.relative_to(old)
        q = new / rel
        if not q.is_file():
            unavailable.append(str(rel))
            continue
        a, b = sha(p), sha(q)
        checked.append({'file': str(rel), 'sha256': a})
        if a != b:
            differences.append(str(rel))
    a = json.loads((old / 'summary.json').read_text())
    b = json.loads((new / 'summary.json').read_text())
    return {'common_file_count': len(checked), 'common_files': checked,
            'different_files': differences, 'baseline_files_not_present': unavailable,
            'summary_exact_match': a == b,
            'summary_different_keys': sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))}


def main():
    here = Path(__file__).resolve().parent
    workspace = here.parents[2]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw', type=Path, default=workspace / 'pair-jetty-raw')
    p.add_argument('--baseline', type=Path,
                   default=workspace / 'wqe-completion-raw/regression-final/accepted')
    p.add_argument('--out', type=Path, default=here / 'review-audit.json')
    a = p.parse_args()
    report = {
        'status': 'PASS',
        'scope': 'Read-only audit of completed run evidence, no simulation execution',
        'window_metric': 'Conservative upper bound: request TAs admitted minus all TAs of WQEs with sender success; not actual native occupancy',
        'window_inference': 'A peak below 512 proves the default 512-TA shared window cannot bind; a peak at or above 512 is inconclusive',
        'limitation': 'Incomplete runs excluded. Archived or absent baseline counterpart files listed, never counted as equal. Host timing is one observation per arm, not a repeated timing estimate.',
        'gates': {},
    }
    gates = [a.raw / 'gate-b', a.raw / 'gate-c'] + sorted(a.raw.glob('gate-d-*'))
    for gate in gates:
        ledger = gate / 'results.json'
        if not ledger.exists():
            continue
        rows = json.loads(ledger.read_text())
        cases = collections.defaultdict(dict)
        for row in rows:
            if row.get('verification') == 'PASS':
                cases[row['case']][row['mode']] = row
        results = {}
        for case, arms in sorted(cases.items()):
            if set(arms) != {'pair', 'per-wqe'}:
                results[case] = {'status': 'INCOMPLETE', 'completed_arms': sorted(arms)}
                results[case]['observed_arm_outcomes'] = {
                    row['mode']: {k: row.get('host', {}).get(k) for k in (
                        'status', 'guard', 'returncode', 'wall_seconds', 'peak_rss_kib')}
                    for row in rows if row['case'] == case}
                if any(x.get('guard') for x in results[case]['observed_arm_outcomes'].values()):
                    results[case]['status'] = 'GUARD_STOPPED_COMPARISON'
                if 'pair' in arms:
                    results[case]['window'] = window(gate / case / 'pair/run')
                    results[case]['pair_metrics'] = arms['pair']['metrics']
                    results[case]['pair_layer_latency_ps'] = arms['pair']['summary']['layer_latency_ps']
                    results[case]['comparison_limit'] = 'No completed legacy counterpart: no A/B timing or logical-parity conclusion'
                continue
            run = gate / case / 'pair/run'
            pair, legacy = arms['pair'], arms['per-wqe']
            r = {'status': 'PASS', 'window': window(run),
                 'logical_exact_match': pair['logical'] == legacy['logical'],
                 'input_hashes_exact_match': pair['inputs'] == legacy['inputs'],
                 'layer_latency_equal': pair['summary']['layer_latency_ps'] == legacy['summary']['layer_latency_ps'],
                 'layer_latency_ps': {m: row['summary']['layer_latency_ps'] for m, row in arms.items()},
                 'host_observations': {m: {k: row['host'][k] for k in (
                     'wall_seconds', 'user_cpu_seconds', 'system_cpu_seconds', 'peak_rss_kib', 'guard')}
                     for m, row in arms.items()},
                 'metrics': {m: row['metrics'] for m, row in arms.items()}}
            if gate.name in ('gate-b', 'gate-c'):
                r['accepted_legacy_parity'] = parity(a.baseline / baseline_case(case), gate / case / 'per-wqe/run')
                b = r['accepted_legacy_parity']
                if b['different_files'] or not b['summary_exact_match']:
                    r['status'] = 'FAIL'
            if not r['logical_exact_match'] or not r['input_hashes_exact_match']:
                r['status'] = 'FAIL'
            if r['status'] == 'FAIL':
                report['status'] = 'FAIL'
            results[case] = r
        report['gates'][gate.name] = results
    report['incomplete_comparisons'] = sum(
        r['status'] in ('INCOMPLETE', 'GUARD_STOPPED_COMPARISON')
        for cases in report['gates'].values() for r in cases.values())
    if report['status'] == 'PASS' and report['incomplete_comparisons']:
        report['status'] = 'PARTIAL'
    a.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'out': str(a.out),
                      'cases': {g: len(c) for g, c in report['gates'].items()}}))
    return report['status'] == 'FAIL'


if __name__ == '__main__':
    raise SystemExit(main())
