#!/usr/bin/env python3
"""Read-only six-cell controlled-ablation analysis; outputs PRIVATE review candidates.

Never launches a simulation, changes inputs, or publishes evidence. Publication
must review the bounded CSVs, rather than copying full private recorder files.
"""
import argparse
import csv
import json
from pathlib import Path

from common import (WINDOWS, REAL_STRATEGIES, ORIGINAL, check, parity, semantic_parity, sha,
                    validate_config, validate_diagnostics)

ACCEPTED = {
    'chunk-streaming': {'weight_ps': 552893591, 'layer_ps': 732284971},
    'multicast-v2': {'weight_ps': 717182855, 'layer_ps': 898435170},
}
PARTS = ['tx_busy_union_ps', 'allocator_pending_excluding_tx_ps', 'uncovered_idle_ps']
PAIR_TARGETS = (5, 13, 52, 59)
SELECTED_SOURCES = (3, 36, 50)
ZERO_JETTY_STATUS = ('terminal_nonzero_jetties', 'pending_ta_observations',
    'pending_source_frames', 'pending_ack_marks', 'occupancy_errors',
    'unmatched_accepted_taacks')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline='') as stream:
        return [{k: int(v) if v and v.lstrip('-').isdigit() else v
                 for k, v in row.items()} for row in csv.DictReader(stream)]


def csv_write(path, data):
    # Even an absent cohort receives a readable, explicit header-only artifact.
    keys = list(dict.fromkeys(k for row in data for k in row)) or ['no_observations']
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)


def case_id(window, strategy):
    return ('baseline-512' if window == 512 else f'window-{window}') + '-' + strategy


def contrast(current, baseline):
    require(baseline > 0 and current > 0, 'Latency must be positive')
    return {'absolute_change_ps': current - baseline,
            'relative_change_percent': 100.0 * (current - baseline) / baseline,
            'intervention_speedup_vs_same_strategy_512': baseline / current}


def timing_contrasts(cases):
    within, between = [], []
    for window in WINDOWS:
        for strategy in REAL_STRATEGIES:
            row = cases[case_id(window, strategy)]
            baseline = cases[case_id(512, strategy)]
            item = dict(case_id=row['case_id'], strategy=strategy, window=window,
                        weight_ps=row['weight_ps'], layer_ps=row['layer_ps'])
            for endpoint in ('weight', 'layer'):
                item.update({endpoint + '_' + k: v for k, v in
                    contrast(row[endpoint + '_ps'], baseline[endpoint + '_ps']).items()})
            item['interpretation'] = ('fresh exact original baseline' if window == 512
                                     else 'capacity intervention; not original algorithm performance')
            within.append(item)
        a, b = [cases[case_id(window, s)] for s in REAL_STRATEGIES]
        a0, b0 = [cases[case_id(512, s)] for s in REAL_STRATEGIES]
        item = {'window': window}
        for endpoint in ('weight', 'layer'):
            field = endpoint + '_ps'
            gap, initial_gap = b[field] - a[field], b0[field] - a0[field]
            did = (b[field] - b0[field]) - (a[field] - a0[field])
            require(did == gap - initial_gap, 'Difference-in-differences identity')
            item.update({endpoint + '_mc_minus_chunk_ps': gap,
                endpoint + '_difference_in_differences_ps': did,
                endpoint + '_gap_reduction_vs_512_ps': -did,
                endpoint + '_mc_over_chunk_time_ratio': b[field] / a[field]})
        item['interpretation'] = 'Same-window comparison; negative DID preferentially benefits MC, not a mediator share'
        between.append(item)
    return within, between


def integrated_occupancy(data, exposure, occupancy, saturated):
    total = sum(row[exposure] for row in data)
    area = sum(row[occupancy] for row in data)
    full = sum(row[saturated] for row in data)
    require(0 <= full <= total, 'Saturated exposure exceeds observed Jetty-time')
    return {'jetty_count': len(data), 'exposure_jetty_ps': total,
            'outstanding_ta_jetty_ps': area, 'full_window_jetty_ps': full,
            'mean_outstanding_tas': area / total if total else None,
            'full_window_fraction': full / total if total else None,
            'whole_observed_run_max_outstanding_tas': max((row['max_outstanding'] for row in data), default=0)}


def jetty_summary(data, histograms, window):
    hist = {}
    for row in histograms:
        key = (row['source'], row['target'], row['jetty'])
        bins = hist.setdefault(key, {})
        require(row['bin'] not in bins, 'Repeated Jetty histogram bin')
        bins[row['bin']] = row
    for row in data:
        key = (row['source'], row['target'], row['jetty'])
        require(row['window'] == window and row['terminal_outstanding'] == 0,
                'Wrong actual Jetty window or nonzero terminal outstanding')
        require(0 <= row['max_outstanding'] <= window, 'Jetty occupancy out of range')
        require(row['ssn_next'] == row['ssn_una'], 'Jetty completion frontier mismatch')
        bins = hist.get(key, {})
        require(set(bins) == set(range(6)), 'Incomplete occupancy histogram')
        require(sum(x['all_observed_ps'] for x in bins.values()) == row['observed_ps'],
                'Whole-run histogram exposure mismatch')
        require(sum(x['weight_phase_ps'] for x in bins.values()) == row['weight_phase_observed_ps'],
                'Weight histogram exposure mismatch')
        require(bins[5]['all_observed_ps'] == row['window_saturated_ps'] and
                bins[5]['weight_phase_ps'] == row['weight_phase_window_saturated_ps'],
                'Full-window integral/histogram mismatch')
        for count, sum_key, max_key in [
                ('weight_source_tx_to_ack_count', 'weight_source_tx_to_ack_sum_ps', 'weight_source_tx_to_ack_max_ps'),
                ('weight_native_pop_to_ack_count', 'weight_native_pop_to_ack_sum_ps', 'weight_native_pop_to_ack_max_ps'),
                ('weight_admission_to_ack_count', 'weight_admission_to_ack_sum_ps', 'weight_admission_to_ack_max_ps')]:
            require(row[sum_key] >= row[max_key] and (row[count] > 0 or row[sum_key] == 0),
                    'Invalid latency aggregate')
    scopes = [('all_pairs', lambda r: True)]
    scopes += [(f'source_{source}', lambda r, s=source: r['source'] == s) for source in SELECTED_SOURCES]
    scopes += [(f'source_3_target_{target}', lambda r, t=target: r['source'] == 3 and r['target'] == t)
               for target in PAIR_TARGETS]
    occupancy, latency, histogram = [], [], []
    for scope, predicate in scopes:
        selected = [row for row in data if predicate(row)]
        for phase, exposure, area, full in [
                ('observed_run', 'observed_ps', 'outstanding_ta_ps', 'window_saturated_ps'),
                ('weight_phase', 'weight_phase_observed_ps', 'weight_phase_outstanding_ta_ps', 'weight_phase_window_saturated_ps')]:
            result = integrated_occupancy(selected, exposure, area, full)
            result.update(scope=scope, phase=phase, admissions=sum(r['admissions'] for r in selected),
                window_tests=sum(r['window_tests'] for r in selected),
                window_limited_tests=sum(r['window_limited_tests'] for r in selected),
                accepted_taacks=sum(r['accepted_taacks'] for r in selected),
                ssn_progress=sum(r['ssn_progress'] for r in selected),
                rejected_taacks=sum(r['rejected_taacks'] for r in selected),
                duplicate_taacks=sum(r['duplicate_taacks'] for r in selected),
                window_full_intervals=sum(r['window_full_intervals'] for r in selected),
                max_window_full_interval_ps=max((r['max_window_full_interval_ps'] for r in selected), default=0),
                counter_scope='counts and full-interval count/max whole observed run; integrals use explicit phase',
                semantics='sum of Jetty-time exposures, not elapsed wall time; includes empty/completed exposure')
            occupancy.append(result)
            for b in range(6):
                key = 'all_observed_ps' if phase == 'observed_run' else 'weight_phase_ps'
                n = sum(hist[(r['source'], r['target'], r['jetty'])][b][key] for r in selected)
                histogram.append(dict(scope=scope, phase=phase, bin=b, exposure_jetty_ps=n,
                    fraction=n / result['exposure_jetty_ps'] if result['exposure_jetty_ps'] else None))
        for prefix, boundary in [('weight_admission_to_ack', 'TA admission to accepted TAACK'),
                ('weight_native_pop_to_ack', 'native packet pop to accepted TAACK; pop is not physical TX'),
                ('weight_source_tx_to_ack', 'first physical source TxStart to accepted TAACK; includes receiver and return path')]:
            count = sum(r[prefix + '_count'] for r in selected)
            total = sum(r[prefix + '_sum_ps'] for r in selected)
            latency.append(dict(scope=scope, boundary=boundary, count=count, sum_ps=total,
                mean_ps=total / count if count else None,
                max_ps=max((r[prefix + '_max_ps'] for r in selected), default=0),
                missing_source_tx=sum(r['weight_ack_without_source_tx'] for r in selected),
                missing_native_pop=sum(r['weight_ack_without_native_pop'] for r in selected),
                complete_physical_boundary_correlation=all(r['weight_ack_without_source_tx'] == 0 and
                    r['weight_ack_without_native_pop'] == 0 for r in selected),
                cohort='selected-source weight TAs by admission identity; may complete after WeightReady',
                coverage='MC source 3; Chunk preselected sources. Global row is selected-TAs, not all-pair RTT.'))
    return occupancy, latency, histogram


def partitions(case, begin, end):
    result = []
    for name, scope, endpoint in [
            ('diagnostic-port-partition.csv', 'weight_phase', 'phase_end_ps'),
            ('diagnostic-source-last-send-partition.csv', 'source_own_last_dequeue', 'last_weight_native_send_ps')]:
        for row in rows(case / name):
            require(sum(row[k] for k in PARTS) == row['total_ps'] == row[endpoint] - row['phase_start_ps'],
                    'Elapsed resource partition does not close')
            require(row['phase_start_ps'] == begin and row[endpoint] <= end, 'Partition boundaries differ')
            if (row['node'] in SELECTED_SOURCES and row['port'] == 0) or (
                    scope == 'weight_phase' and row['node'] == 64 and row['port'] in (17, 27, 59)):
                result.append(dict(scope=scope, node=row['node'], port=row['port'],
                    start_ps=row['phase_start_ps'], end_ps=row[endpoint],
                    **{k: row[k] for k in PARTS}, total_ps=row['total_ps'],
                    semantics='exact disjoint elapsed partition; whole-phase includes post-source completion'))
    return result


def selected_native(case):
    cohort = rows(case / 'diagnostic-weight-phase-cohorts.csv')
    output, reasons = [], []
    for row in cohort:
        if row['node'] == 64 and row['port'] in (17, 27, 59) and row['class'] in (0, 1) and row['metric'] in (0, 3):
            output.append({**row, 'mean_ps': row['sum'] / row['count'] if row['count'] else None,
                'metric_name': 'VOQ residence' if row['metric'] == 0 else 'egress wait',
                'traffic': 'weight' if row['class'] == 0 else 'ACK-response',
                'semantics': 'end-in-weight-phase full residence cohort; overlapping packet-times, not causal wall time'})
        if row['node'] in SELECTED_SOURCES and 200 <= row['metric'] < 209:
            reasons.append({**row, 'reason': ['none', 'empty', 'ack', 'cnp', 'inflight', 'cc', 'eligible', 'retransmission', 'failed'][row['metric'] - 200],
                           'semantics': 'actual native TpLimited evaluations during weight phase, not continuous waits'})
    return output, reasons


def selected_jetty_events(case, begin, end):
    # Retain a single predeclared physical pair. Prefer a weight-frozen ring when
    # available; a run-end ring is explicitly labeled and may lack early history.
    path = case / 'diagnostic-jetty-weight-tail.csv'
    if not path.exists():
        path = case / 'diagnostic-jetty-tail.csv'
    selected = [(i, row) for i, row in enumerate(rows(path))
        if row['source'] == 3 and row['target'] == 59 and begin <= row['time_ps'] <= end]
    if not selected:
        return [], {'status': 'no_selected_weight_events_retained', 'source_file': path.name}
    # A native TA event tuple has ordinal 25..30. The latest actual full-to-not-
    # full transition within one Jetty is preferable; otherwise take a bounded
    # late observation without calling it a full-window admission cycle.
    prior, candidates = {}, []
    for j, (_, row) in enumerate(selected):
        key = row['jetty']
        old = prior.get(key)
        if old and old['ssn_next'] - old['ssn_una'] == old['window'] and (
                row['ssn_una'] > old['ssn_una'] and row['ssn_next'] - row['ssn_una'] < row['window']):
            candidates.append(j)
        prior[key] = row
    center = candidates[-1] if candidates else len(selected) - 1
    sample = selected[max(0, center - 8):min(len(selected), center + 16)]
    return [{'ring_index': i, **r, 'selection': 'preselected source3→59; bounded late SSN transition context',
             'source_file': path.name} for i, r in sample], {
        'status': 'observed_full_window_release' if candidates else 'no_full_release_in_retained_scope',
        'source_file': path.name, 'selected_events': len(sample),
        'coverage': 'bounded ring, not whole-run intervals; absence is not proof of no event'}


def selected_rtt_events(case, begin, end):
    path = case / 'diagnostic-ta-rtt-tail.csv'
    data = [row for row in rows(path) if row['source'] == 3 and row['target'] == 59
            and begin <= row['admission_ps'] <= end]
    chosen = data[-4:]
    for row in chosen:
        require(row['admission_ps'] <= row['first_native_pop_ps'] <= row['first_source_tx_ps'] <= row['accepted_taack_ps'],
                'Selected TA latency boundary order/correlation invalid')
    return [{**row, 'admission_to_taack_ps': row['accepted_taack_ps'] - row['admission_ps'],
             'native_pop_to_taack_ps': row['accepted_taack_ps'] - row['first_native_pop_ps'],
             'source_tx_to_taack_ps': row['accepted_taack_ps'] - row['first_source_tx_ps'],
             'selection': 'last four retained source3→59 weight-admission TAs; may ACK after WeightReady'}
            for row in chosen]


def analyze(root, out):
    root, out = root.resolve(), out.resolve()
    require(root != out and root in out.parents, 'Outputs must remain in a new private analysis directory under run root')
    require(not out.exists(), 'Refusing to overwrite prior analysis')
    ledger = read_json(root / 'ledger.json')
    require(ledger['status'] == 'PASS' and ledger['link_gbps'] == 3136, 'Six-case formal ledger must PASS at 3136 Gbps')
    expected = [case_id(w, s) for w in WINDOWS for s in REAL_STRATEGIES]
    require([r['case_id'] for r in ledger['runs']] == expected, 'Not the prespecified six cells')
    require(read_json(ledger['stage_a_path'])['status'] == 'PASS', 'Regression gate failed')
    require(sha(ledger['stage_a_path']) == ledger['stage_a_sha256'], 'Regression gate identity changed')
    require(sha(ledger['a_decision_path']) == ledger['a_decision_sha256'], 'A decision identity changed')
    a_decision = read_json(ledger['a_decision_path'])
    require(a_decision['status'] in ('STOPPED', 'UNSUPPORTED'), 'Unsupported A decision')
    require(len(ledger['stopped_runs']) == 2 and all(r['measured'] is False for r in ledger['stopped_runs']),
            'A must not have fabricated performance measurements')
    for identity in ledger['identities'].values():
        check(identity)
    collections = {name: [] for name in ('timing', 'contrasts', 'occupancy', 'latency', 'histogram',
        'partitions', 'switch_cohorts', 'tp_reasons', 'allready', 'critical', 'selected_events', 'selected_rtt')}
    cases, proof = {}, []
    for record in ledger['runs']:
        identifier = record['case_id']
        case = root / identifier
        actual = read_json(case / 'run-result.json')
        require(record['status'] == actual['status'] == 'PASS', 'Unverified formal case: ' + identifier)
        require(all(actual[key] == record[key] for key in ('case_id', 'strategy', 'window', 'allocator')),
                'Per-case identity differs from formal ledger')
        require(record['allocator'] == 'original', 'Mixed allocator intervention')
        check(actual['baseline_identity'])
        check(actual['immutable_files'])
        validate_diagnostics(case)
        cfg = validate_config(case, record['window'], True)
        require(cfg['tp_packet_window'] == 1000, 'TP window changed')
        for name in ('validation.json', 'compute-validation.json'):
            require(read_json(case / name)['status'] == 'PASS', 'Correctness not PASS: ' + name)
        semantic_parity(Path(record['baseline']), case)
        js = read_json(case / 'diagnostic-jetty-status.json')
        for key in ZERO_JETTY_STATUS:
            require(js[key] == 0, 'Jetty status not clean: ' + key)
        summary = read_json(case / 'online-summary.json')
        require(summary == actual['summary'], 'Online summary changed after run verification')
        begin, end = summary['event_spans']['weights_start'][0], summary['timeline']['weights_end']
        require(end > begin, 'Nonpositive weight phase')
        timing = dict(case_id=identifier, strategy=record['strategy'], window=record['window'],
                      weight_ps=end - begin, layer_ps=summary['layer_latency_ps'],
                      weights_start_ps=begin, weights_end_ps=end)
        if record['window'] == 512:
            require(actual['exact_baseline_parity'] is True, 'Fresh baseline lacks exact parity')
            parity(Path(record['baseline']), case)
            parity(ORIGINAL / 'real-3136' / record['strategy'], case)
            for key, value in ACCEPTED[record['strategy']].items():
                require(timing[key] == value, 'Fresh baseline did not reproduce original ' + key)
        cases[identifier] = timing
        prefix = dict(case_id=identifier, strategy=record['strategy'], window=record['window'])

        def add(name, data):
            collections[name].extend({**prefix, **row} for row in data)

        o, l, h = jetty_summary(rows(case / 'diagnostic-jetty-aggregates.csv'),
                              rows(case / 'diagnostic-jetty-occupancy.csv'), record['window'])
        add('occupancy', o)
        add('latency', l)
        add('histogram', h)
        resource = partitions(case, begin, end)
        add('partitions', resource)
        switch, reasons = selected_native(case)
        add('switch_cohorts', switch)
        add('tp_reasons', reasons)
        add('allready', [{**row, 'semantics': 'group8 actual first-failure queries; held spans are not continuous waits'}
                        for row in rows(case / 'diagnostic-poll-upper-bounds.csv') if row['group'] == 8])
        critical = [r for r in rows(case / 'diagnostic-transfers.csv') if r['receiver_ready_ps'] == end]
        require(critical, 'No true terminal receiver dependency')
        require(len(critical) <= 16, 'Too many terminal dependencies for bounded export; review required')
        for row in critical:
            matched = [r for r in resource if r['node'] == row['source'] and
                       r['scope'] == 'source_own_last_dequeue' and r['end_ps'] == row['last_native_send_ps']]
            row = {**row, 'dequeue_to_ready_ps': end - row['last_native_send_ps'],
                   'sender_cleanup_after_weightready_ps': row['sender_complete_ps'] - end,
                   'source_prefix_accounting_available': len(matched) == 1}
            if len(matched) == 1:
                residual = end - begin - matched[0]['total_ps'] - row['dequeue_to_ready_ps']
                require(residual == 0, 'Critical-source accounting residual')
                row['accounting_residual_ps'] = residual
            add('critical', [row])
        events, sample_proof = selected_jetty_events(case, begin, end)
        add('selected_events', events)
        add('selected_rtt', selected_rtt_events(case, begin, end))
        proof.append({**prefix, 'exact_original_parity': record['window'] == 512,
                      'logical_semantic_parity': True, 'diagnostic_complete': True,
                      'selected_jetty_timeline': sample_proof,
                      'all_pair_jetty_count': js['tracked_jetties'],
                      'tail_overwrites': js['tail_overwrites']})
    collections['timing'], collections['contrasts'] = timing_contrasts(cases)
    require(len(collections['selected_events']) + len(collections['selected_rtt']) <= 240, 'Selected event cap exceeded')
    out.mkdir(parents=False)
    for name, data in collections.items():
        csv_write(out / (name + '.csv'), data)
    report = {'status': 'PASS', 'publication_status': 'PRIVATE_REVIEW_CANDIDATES',
        'accepted_commit': 'b149fdd4d40d72791a84b788443b0450c41f6180',
        'a': {'status': a_decision['status'], 'reason': a_decision['reason'], 'measured': False},
        'cases': cases, 'verification': proof, 'timing': collections['timing'],
        'contrasts': collections['contrasts'],
        'cautions': [
            'Changed-window speedups are intervention results, never original Multicast v2 performance.',
            'B identifies total capacity-intervention effects, not isolated ACK/allocator/AllReady mediation.',
            'Negative DID preferentially benefits MC; inspect each within-strategy effect for harm or benefit.',
            'Full-window exposure sums are Jetty-time, not wall time or automatically harmful blocked wait.',
            'TAACK latencies have explicit distinct boundaries and selected weight-admission coverage.',
            'VOQ residence and held AllReady spans cannot be added to source elapsed-resource partitions.',
            'Original terminal resources are preselected controls; true terminal dependencies can move.',
            'Deterministic fixed-workload contrasts have no statistical confidence interval or broad generalization.',
            'TP1000 may produce diminishing returns, but a plateau alone does not prove a TP bottleneck.'],
        'artifact_rows': {name: len(value) for name, value in collections.items()}}
    (out / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'artifact-manifest.json').write_text(json.dumps({p.name: sha(p) for p in sorted(out.iterdir())
        if p.is_file()}, indent=2) + '\n')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    result = analyze(args.root, args.out or args.root / 'analysis')
    print(json.dumps({'status': result['status'], 'rows': result['artifact_rows'],
                      'weight_contrasts': result['contrasts']}, indent=2))


if __name__ == '__main__':
    main()
