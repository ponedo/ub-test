#!/usr/bin/env python3
"""Strict aggregate-only postflight for the fixed N256/3136-Gbps screening.

No simulation or verifier is launched. Reads only named metadata/aggregate files;
never opens packet/event rings, TA RTT tails, or token traces. Output is an
allowlisted aggregate report, not a copy of private evidence or host metadata.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path

N = 64
WINDOW = 512
DISABLED_SELECTION = 4294967294
PARTS = ('tx_busy_union_ps', 'allocator_pending_excluding_tx_ps', 'uncovered_idle_ps')
PORTS = {(i, 0) for i in range(N)} | {(N, i) for i in range(N)}
STRATEGIES = ('chunk-streaming', 'multicast-v2')


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, label):
    require(type(value) is int and value >= 0, 'Invalid nonnegative integer: ' + label)
    return value


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'Invalid nonnegative number: ' + label)
    return value


def read_json(directory, name):
    try:
        with (directory / name).open() as stream:
            value = json.load(stream)
        require(isinstance(value, dict), 'Expected JSON object: ' + name)
        return value
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Missing or corrupt evidence: ' + name) from exc


def rows(directory, name, fields, strings=()):
    try:
        with (directory / name).open(newline='') as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames)
                    and set(fields) <= set(reader.fieldnames), 'Invalid CSV schema: ' + name)
            result = []
            for raw in reader:
                require(None not in raw and all(v is not None for v in raw.values()), 'Invalid CSV row: ' + name)
                row = {}
                for key in fields:
                    if key in strings:
                        row[key] = raw[key]
                    else:
                        require(raw[key].isdigit(), 'Invalid CSV integer: ' + name + ':' + key)
                        row[key] = int(raw[key])
                result.append(row)
            return result
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError('Missing or corrupt evidence: ' + name) from exc


def unique(data, fields, label):
    result = {}
    for row in data:
        key = tuple(row[k] for k in fields)
        require(key not in result, 'Duplicate ' + label)
        result[key] = row
    return result


def zero_fields(data, fields, label):
    for key in fields:
        require(integer(data[key], label + '.' + key) == 0, label + ' not zero: ' + key)


def metric_index(data):
    for row in data:
        require((row['node'], row['port']) in PORTS or row['metric'] >= 200,
                'Invalid native metric port')
        require(row['class'] in (0, 1, 2) and row['count'] > 0 and row['max'] <= row['sum'],
                'Invalid native aggregate')
    return unique(data, ('metric', 'node', 'port', 'class'), 'native aggregate key')


def measure(index, metric, node=None, port=None, cls=None):
    selected = [v for (m, n, p, c), v in index.items()
                if m == metric and (node is None or n == node)
                and (port is None or p == port) and (cls is None or c == cls)]
    return {'count': sum(v['count'] for v in selected), 'sum': sum(v['sum'] for v in selected),
            'max': max((v['max'] for v in selected), default=0)}


def callback_summary(index, node=None, port=None):
    request = measure(index, 2, node, port)
    require(request['sum'] == 5000 * request['count'] and
            request['max'] == (5000 if request['count'] else 0), 'Allocator requested service is not 5 ns')
    return {'requested': request, 'committed': measure(index, 10, node, port),
            'rejected': measure(index, 8, node, port), 'no_ingress': measure(index, 9, node, port)}


def read_partitions(directory, name, endpoint, begin, end=None):
    data = rows(directory, name, ('node', 'port', 'phase_start_ps', endpoint, *PARTS, 'total_ps'))
    indexed = unique(data, ('node', 'port'), 'resource partition')
    for key, row in indexed.items():
        require(key in PORTS and row['phase_start_ps'] == begin and row[endpoint] >= begin,
                'Resource partition boundary mismatch')
        require(end is None or row[endpoint] == end, 'Resource phase end mismatch')
        require(sum(row[k] for k in PARTS) == row['total_ps'] == row[endpoint] - begin,
                'Resource partition conservation failed')
    return indexed


def resource_and_settings(directory, config, summary):
    runtime = config['runtime']
    require(config['weight_strategy'] in STRATEGIES, 'Not a screening strategy')
    require(config['planner_input']['npus'] == N and len(config['planner_input']['mapping']) == 256,
            'Only EP64/N256 is authorized')
    require(runtime['link_gbps'] == 3136 and runtime['link_delay_ns'] == 20
            and runtime['segment_bytes'] == 1024, 'Screening network parameters changed')
    require(summary['completed_tokens'] == 256 and summary['log_level'] == 'summary',
            'Incomplete tokens or non-summary simulation')
    ablation = read_json(directory, 'ablation-config.json')
    require(ablation['jetty_ta_window'] == WINDOW and ablation['jetty_ooo_ack_window'] == 2048
            and ablation['tp_packet_window'] == 1000 and ablation['measurement_enabled'] is True
            and ablation['allocator_policy'] == 'original'
            and ablation['logical_ssn_uint32_no_wrap_bound'] is True,
            'Native capacity or allocator configuration changed')
    require(0 <= integer(ablation['predicted_total_tas_upper_bound'], 'predicted TAs') <= 2**32 - 1,
            'Logical SSN upper bound exceeded')
    model = read_json(directory, 'compute-model.json')
    require(model['model'] == 'roofline' and model['compute_tflops'] == 100
            and model['hbm_bandwidth_gbps'] == 2692 and model['roofline_launch_ns'] == 0,
            'Roofline configuration changed')
    resource = read_json(directory, 'simulator-host/resource.json')
    require(resource['status'] == 'PASS' and resource['returncode'] == 0 and resource['guard'] is None,
            'Simulator did not finish successfully')
    command = resource['command']
    require(isinstance(command, list) and all(isinstance(v, str) for v in command), 'Missing simulator command')
    options = {}
    for arg in command[1:]:
        if arg.startswith('--'):
            key, sep, value = arg[2:].partition('=')
            require(sep and key not in options, 'Ambiguous simulator arguments')
            options[key] = value
    require(options.get('diagnostic') == '1'
            and options.get('diagnosticSource') == str(DISABLED_SELECTION)
            and options.get('diagnosticGroup') == str(DISABLED_SELECTION)
            and options.get('diagnosticNodes', '') in ('', ','.join(map(str, range(N + 1)))),
            'Global aggregate / disabled selected RTT configuration not proved')
    require(options.get('logLevel', 'summary') == 'summary'
            and options.get('networkFault', '') == '' and options.get('fault', '') == ''
            and options.get('invalidateGrant', '0') == '0'
            and options.get('nativeRetrans', '0') == '0', 'Fault injection or detailed logs enabled')
    fields = ('wall_seconds', 'user_cpu_seconds', 'system_cpu_seconds', 'peak_rss_kib',
              'sampled_peak_tree_rss_bytes', 'max_observed_threads_per_process')
    public_resource = {k: number(resource[k], k) for k in fields}
    public_resource['cpu_seconds'] = public_resource['user_cpu_seconds'] + public_resource['system_cpu_seconds']
    validations = {}
    for name in ('validation.json', 'compute-validation.json'):
        require(read_json(directory, name)['status'] == 'PASS', 'Correctness verification not PASS: ' + name)
        validations[name.removesuffix('.json')] = 'PASS'
    # Runner performs these existing full verifiers separately. If their receipts
    # are present, a failed/partial receipt may never be hidden by this analyzer.
    for name in ('postflight-host', 'independent-host', 'compute-host'):
        if (directory / name / 'resource.json').exists():
            receipt = read_json(directory, name + '/resource.json')
            require(receipt['status'] == 'PASS' and receipt['returncode'] == 0 and receipt['guard'] is None,
                    'External verifier not PASS: ' + name)
            validations[name] = 'PASS'
    return public_resource, validations


def transfers_and_acks(directory, config, summary, packet_index):
    fields = ('task', 'stage', 'source', 'target', 'physical', 'bytes', 'offset')
    transfers = rows(directory, 'transfers.csv', fields)
    unique(transfers, ('task',), 'transfer task')
    expected = config['transfers']
    require([{k: r[k] for k in fields} for r in expected] == transfers, 'Transfer file/config mismatch')
    remote = [r for r in transfers if r['source'] != r['target']]
    require(summary['remote_WQEs'] == summary['sender_completions'] == len(remote), 'WQE completion mismatch')
    incoming, outgoing = defaultdict(Counter), defaultdict(Counter)
    incoming_bytes, outgoing_bytes = defaultdict(Counter), defaultdict(Counter)
    pair_tas = Counter()
    for row in remote:
        require(0 <= row['source'] < N and 0 <= row['target'] < N and row['stage'] in (0, 1, 2)
                and row['bytes'] > 0, 'Invalid remote transfer')
        count = (row['bytes'] + 1023) // 1024
        kind = 'weight' if row['stage'] == 2 else 'token'
        outgoing[row['source']][kind] += count
        incoming[row['target']][kind] += count
        outgoing_bytes[row['source']][kind] += row['bytes']
        incoming_bytes[row['target']][kind] += row['bytes']
        pair_tas[row['source'], row['target']] += count
    total = sum(pair_tas.values())
    require(summary['TA_count'] == total and summary['jettys'] == len(pair_tas), 'Global TA/Jetty count mismatch')
    def count(node, port, kind):
        return packet_index.get((node, port, kind), {}).get('packets', 0)
    def wire(node, port, kind):
        return packet_index.get((node, port, kind), {}).get('wire_bytes', 0)
    reconciliation = []
    for source in range(N):
        ot, ow = outgoing[source]['token'], outgoing[source]['weight']
        it, iw = incoming[source]['token'], incoming[source]['weight']
        require(count(N, source, 'transport_ack') == count(source, 0, 'transport_ack') == ot + ow + it + iw,
                'Per-source TPACK count does not reconcile with all outgoing/incoming TAs')
        require(count(N, source, 'transaction_response') == ot + ow
                and count(source, 0, 'transaction_response') == it + iw,
                'Per-source TAACK count does not reconcile with transfers')
        require(count(source, 0, 'token_write') == ot and count(N, source, 'token_write') == it,
                'Token WRITE packet count mismatch')
        require(count(N, source, 'weight_write') == iw, 'Downstream weight WRITE packet count mismatch')
        require(wire(N, source, 'weight_write') == incoming_bytes[source]['weight'] + 78 * iw
                and wire(N, source, 'token_write') == incoming_bytes[source]['token'] + 78 * it
                and wire(source, 0, 'token_write') == outgoing_bytes[source]['token'] + 78 * ot,
                'Native WRITE payload/header byte reconciliation failed')
        if config['weight_strategy'] == 'chunk-streaming':
            require(count(source, 0, 'weight_write') == ow and count(source, 0, 'multicast_v2') == 0
                    and wire(source, 0, 'weight_write') == outgoing_bytes[source]['weight'] + 78 * ow,
                    'Chunk source WRITE packet count mismatch')
        reconciliation.append({'source': source, 'outgoing_token_tas': ot, 'incoming_token_tas': it,
            'outgoing_weight_tas': ow, 'incoming_weight_tas': iw,
            'switch_return_tpack': count(N, source, 'transport_ack'),
            'switch_return_taack': count(N, source, 'transaction_response'),
            'weight_return_tpack_after_token_subtraction': count(N, source, 'transport_ack') - ot - it,
            'weight_return_taack_after_token_subtraction': count(N, source, 'transaction_response') - ot,
            'weight_return_feedback_frames': 2 * ow + iw,
            'nominal_weight_return_allocator_service_ps': 5000 * (2 * ow + iw)})
    return transfers, pair_tas, {'logical_remote_tas': total,
        'physical_tpack_transmissions': sum(r['packets'] for r in packet_index.values() if r['kind'] == 'transport_ack'),
        'physical_taack_transmissions': sum(r['packets'] for r in packet_index.values() if r['kind'] == 'transaction_response'),
        'all_64_sources_reconciled': True, 'sources': reconciliation,
        'semantics': 'Whole lifecycle native opcode split, not weight-phase counts. Nominal allocator demand is service workload, not elapsed wall time or a new lower bound. Each WRITE TA yields one TAACK and two TPACKs; each crosses two physical links. Return TPACK includes outgoing and incoming TAs, including relay-source incoming weights.'}


def validate_jetty(directory, summary, pair_tas, duration):
    status = read_json(directory, 'diagnostic-jetty-status.json')
    require(status['incomplete'] is False, 'Incomplete Jetty observer')
    zero_fields(status, ('terminal_nonzero_jetties', 'pending_ta_observations', 'pending_source_frames',
                        'pending_ack_marks', 'occupancy_errors', 'unmatched_accepted_taacks'), 'Jetty status')
    counts = ('admissions', 'window_tests', 'window_limited_tests', 'accepted_taacks', 'rejected_taacks',
              'duplicate_taacks', 'ssn_progress', 'cleanup_events', 'window_full_intervals')
    integrals = ('observed_ps', 'outstanding_ta_ps', 'window_saturated_ps', 'weight_phase_observed_ps',
                 'weight_phase_outstanding_ta_ps', 'weight_phase_window_saturated_ps')
    selected_fields = tuple(prefix + suffix for prefix in ('admission_to_ack', 'weight_admission_to_ack',
        'weight_native_pop_to_ack', 'weight_source_tx_to_ack') for suffix in ('_count', '_sum_ps', '_max_ps'))
    data = rows(directory, 'diagnostic-jetty-aggregates.csv', ('source', 'target', 'jetty', 'window',
        'ssn_next', 'ssn_una', 'terminal_outstanding', 'max_outstanding', 'max_window_full_interval_ps',
        'weight_ack_without_source_tx', 'weight_ack_without_native_pop', *counts, *integrals, *selected_fields))
    indexed = unique(data, ('source', 'target'), 'Jetty source-target pair')
    require(len(data) == status['tracked_jetties'] == summary['jettys'] and set(indexed) == set(pair_tas),
            'Global Jetty observation coverage incomplete')
    histogram = rows(directory, 'diagnostic-jetty-occupancy.csv',
        ('source', 'target', 'jetty', 'window', 'bin', 'all_observed_ps', 'weight_phase_ps'))
    hist = unique(histogram, ('source', 'target', 'jetty', 'bin'), 'Jetty occupancy bin')
    require(len(hist) == 6 * len(data), 'Jetty occupancy bin count mismatch')
    for row in data:
        require(row['window'] == WINDOW and row['ssn_next'] == row['ssn_una']
                and row['terminal_outstanding'] == 0 and row['max_outstanding'] <= WINDOW,
                'Jetty capacity/completion invariant')
        require(row['admissions'] == row['ssn_progress'] == row['accepted_taacks'] == pair_tas[row['source'], row['target']],
                'Jetty admissions/accepted TAACK/SSN progress mismatch')
        zero_fields(row, ('rejected_taacks', 'cleanup_events'), 'Jetty completion')
        # These counters are selection-scoped, not independent all-pair proof.
        zero_fields(row, (*selected_fields, 'weight_ack_without_source_tx', 'weight_ack_without_native_pop',
                          'duplicate_taacks'), 'Disabled selected-TA observation')
        require(row['window_limited_tests'] <= row['window_tests']
                and row['weight_phase_observed_ps'] <= duration
                and row['max_window_full_interval_ps'] <= row['window_saturated_ps'], 'Jetty interval invariant')
        require(row['window_full_intervals'] != 0 or row['window_saturated_ps'] == row['max_window_full_interval_ps'] == 0,
                'Jetty full-interval mismatch')
        bins = [hist.get((row['source'], row['target'], row['jetty'], i)) for i in range(6)]
        require(all(b is not None and b['window'] == WINDOW for b in bins), 'Missing Jetty histogram bins')
        for exposure, area, full, binfield in (
                ('observed_ps', 'outstanding_ta_ps', 'window_saturated_ps', 'all_observed_ps'),
                ('weight_phase_observed_ps', 'weight_phase_outstanding_ta_ps', 'weight_phase_window_saturated_ps', 'weight_phase_ps')):
            require(sum(b[binfield] for b in bins) == row[exposure] and bins[5][binfield] == row[full]
                    and 0 <= row[full] <= row[exposure]
                    and WINDOW * row[full] <= row[area] <= WINDOW * row[exposure], 'Jetty occupancy integral mismatch')
    result = {'tracked_jetties': len(data), 'window': WINDOW,
              **{key: sum(row[key] for row in data) for key in counts if key != 'duplicate_taacks'},
              'max_outstanding': max(row['max_outstanding'] for row in data),
              'terminal_outstanding': 0, 'all_pair_completion_reconciled': True,
              'selected_ta_rtt': {'enabled': False, 'completeness_evidence': False,
                  'reason': 'Impossible source/group selection disables selected TA latency and duplicate tracking. Zero selected counters do not prove global latency or identity coverage.'}}
    for prefix, exposure, area, full, binfield in (
            ('observed_run', 'observed_ps', 'outstanding_ta_ps', 'window_saturated_ps', 'all_observed_ps'),
            ('weight_phase', 'weight_phase_observed_ps', 'weight_phase_outstanding_ta_ps', 'weight_phase_window_saturated_ps', 'weight_phase_ps')):
        total = sum(r[exposure] for r in data)
        occupied = sum(r[area] for r in data)
        saturated = sum(r[full] for r in data)
        result[prefix] = {'exposure_jetty_ps': total, 'outstanding_ta_jetty_ps': occupied,
            'full_window_jetty_ps': saturated, 'mean_outstanding_tas': occupied / total if total else None,
            'full_window_fraction': saturated / total if total else None,
            'histogram_jetty_ps': [sum(r[binfield] for r in histogram if r['bin'] == b) for b in range(6)]}
    result['semantics'] = 'Exact transition-integrated Jetty-time, not wall-clock blocked time; includes empty/completed exposure.'
    return result


def validate_physical(summary, native, packet_index):
    by_port = defaultdict(lambda: [0, 0])
    for (node, port, kind), row in packet_index.items():
        require((node, port) in PORTS and kind in ('credit', 'transport_ack', 'transaction_response',
                'token_write', 'weight_write', 'multicast_v2') and row['packets'] > 0 and row['wire_bytes'] > 0,
                'Invalid physical packet statistics')
        by_port[node, port][0] += row['packets']
        by_port[node, port][1] += row['wire_bytes']
    for field in ('packet_tx_per_node', 'packet_rx_per_node', 'byte_tx_per_node', 'byte_rx_per_node'):
        require(len(summary[field]) == N + 1, 'Physical node coverage incomplete')
        for value in summary[field]:
            integer(value, field)
    for node, port in PORTS:
        peer = (N, node) if node != N else (port, 0)
        tx, rx = measure(native, 5, node, port), measure(native, 6, *peer)
        require((tx['count'], tx['sum']) == (rx['count'], rx['sum']) == tuple(by_port[node, port]),
                'Physical link packet/byte conservation failed')
    for node in range(N + 1):
        tx, rx = measure(native, 5, node), measure(native, 6, node)
        require(tx['count'] == summary['packet_tx_per_node'][node] and tx['sum'] == summary['byte_tx_per_node'][node]
                and rx['count'] == summary['packet_rx_per_node'][node] and rx['sum'] == summary['byte_rx_per_node'][node],
                'Native/summary physical counters disagree')
    return {'nodes': N + 1, 'directed_links': 2 * N, 'all_links_packet_and_byte_conserved': True,
        'physical_tx_packets': sum(summary['packet_tx_per_node']), 'physical_rx_packets': sum(summary['packet_rx_per_node']),
        'physical_tx_wire_bytes': sum(summary['byte_tx_per_node']), 'physical_rx_wire_bytes': sum(summary['byte_rx_per_node'])}


def validate_multicast(directory, config, transfers, packets, pair_tas):
    if config['weight_strategy'] != 'multicast-v2':
        return {'applicable': False}
    lifecycle = read_json(directory, 'multicast-lifecycle.json')
    require(lifecycle['status'] == 'PASS' and lifecycle['pair_jetties'] == len(pair_tas), 'Multicast lifecycle mismatch')
    zero_fields(lifecycle, ('native_retry_packets', 'injected_losses', 'pending_associations', 'invalidated_grants'),
                'Multicast lifecycle')
    data = rows(directory, 'multicast-stats.csv', ('group', 'source', 'fanout', 'payload_bytes', 'wire_bytes',
        'envelopes', 'native_singleton_packets', 'header_bytes', 'association_limit', 'association_peak',
        'association_restored', 'first_send_grants', 'admitted_ps', 'first_send_done_ps'))
    indexed = unique(data, ('group',), 'multicast group')
    wanted = config['multicast_groups']
    require(set(indexed) == {(g['group'],) for g in wanted}, 'Multicast group coverage mismatch')
    source_packets, source_bytes, singleton_packets = Counter(), Counter(), Counter()
    fanouts = Counter()
    weight_bytes = config['runtime']['weight_bytes']
    count = (weight_bytes + 1023) // 1024
    for group in wanted:
        row = indexed[group['group'],]
        fan = len(group['members'])
        require(fan > 0 and row['fanout'] == fan and row['source'] == group['source'], 'Multicast fanout/source mismatch')
        overhead = 78 if fan == 1 else 24 + 76 * fan
        require(row['payload_bytes'] == weight_bytes and row['header_bytes'] == overhead * count
                and row['wire_bytes'] == weight_bytes + overhead * count
                and row['first_send_grants'] == count
                and row['envelopes'] == (count if fan > 1 else 0)
                and row['native_singleton_packets'] == (count if fan == 1 else 0), 'Multicast envelope accounting failed')
        require(row['association_peak'] <= row['association_limit']
                and row['association_restored'] == (fan * count if fan > 1 else 0)
                and row['admitted_ps'] <= row['first_send_done_ps'], 'Multicast association/lifecycle invariant')
        source_packets[group['source']] += row['envelopes']
        singleton_packets[group['source']] += row['native_singleton_packets']
        source_bytes[group['source']] += row['wire_bytes']
        fanouts[fan] += 1
    for source in range(N):
        actual = [r for r in packets.values() if r['node'] == source and r['kind'] in ('weight_write', 'multicast_v2')]
        require(sum(r['wire_bytes'] for r in actual) == source_bytes[source]
                and sum(r['packets'] for r in actual if r['kind'] == 'multicast_v2') == source_packets[source]
                and sum(r['packets'] for r in actual if r['kind'] == 'weight_write') == singleton_packets[source],
                'Multicast physical source packet/byte mismatch')
    envelopes = sum(r['envelopes'] for r in data)
    branches = sum(r['envelopes'] * r['fanout'] for r in data)
    require(lifecycle['envelopes'] == envelopes and lifecycle['branches'] == branches
            and not any(r['node'] == N and r['kind'] == 'multicast_v2' for r in packets.values()),
            'Multicast replication conservation failed')
    return {'applicable': True, 'groups': len(data), 'fanout_histogram': dict(sorted(fanouts.items())),
        'fanout_total': sum(r['fanout'] for r in data), 'envelopes': envelopes, 'native_branches': branches,
        'native_singleton_packets': sum(singleton_packets.values()), 'source_wire_bytes': sum(source_bytes.values()),
        'source_payload_bytes': sum(r['payload_bytes'] for r in data),
        'source_header_bytes': sum(r['header_bytes'] for r in data),
        'native_retry_packets': 0, 'injected_test_losses': 0, 'pending_associations': 0,
        'loss_counter_scope': 'injected_test_losses counts only explicit test-hook injections, not all network drops.'}


def analyze_case(directory):
    """Return only public-safe aggregates; reject absent, corrupt or inconsistent evidence."""
    directory = Path(directory)
    try:
        config = read_json(directory, 'config.json')
        summary = read_json(directory, 'online-summary.json')
        resource, validations = resource_and_settings(directory, config, summary)
        begin = integer(summary['event_spans']['weights_start'][0], 'weights_start')
        end = integer(summary['timeline']['weights_end'], 'weights_end')
        duration = end - begin
        require(duration > 0, 'Nonpositive WeightDuration')
        status = read_json(directory, 'diagnostic-status.json')
        require(status['enabled'] is True and status['incomplete'] is False
                and status['last_weight_ready_ps'] == end, 'Incomplete or misaligned native recorder')
        zero_fields(status, ('queue_observations_open', 'queue_unmatched', 'queue_order_errors', 'queue_depth_errors',
                            'grant_outcomes_unmatched', 'grant_start_overwrites', 'grant_starts_open'), 'Native observer')
        native = metric_index(rows(directory, 'diagnostic-native-aggregates.csv',
            ('metric', 'node', 'port', 'class', 'count', 'sum', 'max')))
        phase_rows = rows(directory, 'diagnostic-weight-phase-cohorts.csv',
            ('metric', 'node', 'port', 'class', 'count', 'sum', 'max', 'cohort'), ('cohort',))
        phase = metric_index(phase_rows)
        for key, row in phase.items():
            expected_cohort = ('end_event_in_weight_phase_full_residence' if row['metric'] in (0, 1, 3, 8, 9, 10)
                               or row['metric'] >= 1000 else 'event_start_in_weight_phase_full_value')
            require(row['cohort'] == expected_cohort and key in native
                    and all(row[field] <= native[key][field] for field in ('count', 'sum', 'max')),
                    'Weight event cohort scope/accounting mismatch')
        partitions = read_partitions(directory, 'diagnostic-port-partition.csv', 'phase_end_ps', begin, end)
        weight_nodes = {row[key] for row in config['transfers'] if row['stage'] == 2
                        for key in ('source', 'target')}
        remote_nodes = {row[key] for row in config['transfers'] if row['source'] != row['target']
                        for key in ('source', 'target')}
        required_ports = {(node, 0) for node in remote_nodes} | {(N, node) for node in weight_nodes}
        required_ports |= {(node, port) for metric, node, port, cls in phase if (node, port) in PORTS}
        require(required_ports <= set(partitions) <= PORTS, 'Global active-port partition coverage incomplete')
        absent_idle_ports = sorted(port for node, port in PORTS - set(partitions) if node == N)
        absent_idle_hosts = sorted(node for node, port in PORTS - set(partitions) if node < N)
        # Native switch VOQs are lazy. With global recording, a switch port with
        # no weight endpoint and no in-phase native aggregate can legitimately
        # lack an Activity row. Never fabricate a measured idle partition.
        prefixes = read_partitions(directory, 'diagnostic-source-last-send-partition.csv',
                                   'last_weight_native_send_ps', begin)
        callbacks = callback_summary(native)
        require(callbacks['requested']['count'] > 0
                and callbacks['requested']['count'] == sum(callbacks[k]['count'] for k in ('committed', 'rejected', 'no_ingress')),
                'Allocation callback outcome conservation failed')
        packets = unique(rows(directory, 'packet-counts.csv', ('node', 'port', 'kind', 'packets', 'wire_bytes'),
                              ('kind',)), ('node', 'port', 'kind'), 'physical packet kind')
        # Credits use priority-0 VOQs and the original allocator too. Detached
        # TX belongs to the disabled fault seam, so include credits here.
        for node, port in PORTS:
            committed = measure(native, 10, node, port)['count']
            transmitted = sum(row['packets'] for row in packets.values()
                              if row['node'] == node and row['port'] == port)
            require(committed == transmitted, 'Committed allocation / physical transmission count mismatch')
        transfers, pair_tas, feedback = transfers_and_acks(directory, config, summary, packets)
        physical = validate_physical(summary, native, packets)
        jetty = validate_jetty(directory, summary, pair_tas, duration)
        multicast = validate_multicast(directory, config, transfers, packets, pair_tas)
        weights = [r for r in transfers if r['stage'] == 2]
        diagnostic = rows(directory, 'diagnostic-transfers.csv', ('task', 'expert', 'source', 'target', 'physical',
            'offset', 'bytes', 'submit_ps', 'first_native_send_ps', 'last_native_send_ps', 'last_received_ps',
            'receiver_ready_ps', 'sender_complete_ps'))
        by_task = unique(diagnostic, ('task',), 'diagnostic transfer')
        require(set(by_task) == {(r['task'],) for r in weights}, 'Weight transfer diagnostic coverage mismatch')
        for row in weights:
            require(row['source'] != row['target'], 'Screening weight transfers must be remote')
            diag = by_task[row['task'],]
            require(all(diag[k] == row[k] for k in ('source', 'target', 'physical', 'offset', 'bytes')),
                    'Weight transfer identity mismatch')
            require(begin <= diag['submit_ps'] <= diag['first_native_send_ps'] <= diag['last_native_send_ps']
                    <= diag['last_received_ps'] <= diag['receiver_ready_ps'] <= end
                    and diag['receiver_ready_ps'] <= diag['sender_complete_ps'], 'Weight transfer timestamp order invalid')
        critical = [r for r in diagnostic if r['receiver_ready_ps'] == end]
        require(critical, 'No true terminal weight transfer')
        critical_sources = sorted({r['source'] for r in critical})
        def port_result(node, port):
            partition = partitions[node, port]
            q = measure(phase, 0, node, port, 1)
            return {'node': node, 'port': port, **{k: partition[k] for k in (*PARTS, 'total_ps')},
                'busy_or_allocator_fraction': 1 - partition['uncovered_idle_ps'] / duration,
                'ack_response_tx': measure(phase, 5, node, port, 1),
                'ack_response_rx': measure(phase, 6, node, port, 1),
                'weight_tx': measure(phase, 5, node, port, 0),
                'weight_rx': measure(phase, 6, node, port, 0),
                'weight_voq_residence': measure(phase, 0, node, port, 0),
                'weight_egress_wait': measure(phase, 3, node, port, 0),
                'ack_response_voq_residence': q, 'ack_response_egress_wait': measure(phase, 3, node, port, 1),
                'callback_event_cohorts': callback_summary(phase, node, port)}
        return_ports = [port_result(N, source) for source in range(N) if (N, source) in partitions]
        hot = sorted(return_ports, key=lambda r: (-r['ack_response_voq_residence']['sum'],
                                                -r['ack_response_tx']['count'], r['port']))[:8]
        critical_paths = []
        for source in critical_sources:
            prefix = prefixes.get((source, 0))
            require(prefix is not None, 'Critical-source own-last-dequeue partition missing')
            actual_last = max(r['last_native_send_ps'] for r in diagnostic if r['source'] == source)
            require(prefix['last_weight_native_send_ps'] == actual_last <= end,
                    'Critical-source last-dequeue boundary mismatch')
            critical_paths.append({'source': source, 'host': port_result(source, 0),
                'shared_return_port': port_result(N, source),
                'target_paths': [{'target': target,
                    'critical_transfer_count': sum(r['source'] == source and r['target'] == target for r in critical),
                    'forward_switch_port': port_result(N, target), 'receiver_port': port_result(target, 0)}
                    for target in sorted({r['target'] for r in critical if r['source'] == source})],
                'source_own_last_dequeue': {k: prefix[k] for k in ('last_weight_native_send_ps', *PARTS, 'total_ps')},
                'own_last_dequeue_to_weight_ready_ps': end - actual_last,
                'accounting_residual_ps': duration - prefix['total_ps'] - (end - actual_last)})
        global_partitions = [{'node': node, 'port_count': sum(n == node for n, p in partitions),
            'expected_port_count': N if node == N else 1,
            'unobserved_port_count': len(absent_idle_ports) if node == N else int(node in absent_idle_hosts),
            **{k: sum(v[k] for (n, p), v in partitions.items() if n == node) for k in (*PARTS, 'total_ps')}}
            for node in range(N + 1)]
        return {'schema_version': 1, 'status': 'PASS', 'strategy': config['weight_strategy'], 'tokens': 256,
            'settings': {'npus': N, 'link_gbps': 3136, 'propagation_ns': 20, 'allocator_requested_ns': 5,
                'jetty_ta_window': WINDOW, 'native_tp_packet_window': 1000,
                'compute_model': 'roofline', 'compute_tflops': 100, 'hbm_bandwidth_GBps': 2692},
            'timing': {'weight_duration_ps': duration, 'weights_start_ps': begin, 'weights_end_ps': end,
                'layer_latency_ps': integer(summary['layer_latency_ps'], 'layer latency')},
            'critical_transfer_count': len(critical),
            'critical_transfers': [{k: r[k] for k in ('task', 'source', 'target', 'physical', 'bytes',
                'last_native_send_ps', 'receiver_ready_ps', 'sender_complete_ps')} for r in critical],
            'critical_source_paths': critical_paths, 'native_partitions_by_node': global_partitions,
            'native_partition_coverage': {'nodes': N + 1, 'physical_ports': 2 * N,
                'recorded_ports': len(partitions), 'unobserved_switch_ports': absent_idle_ports, 'unobserved_host_ports': absent_idle_hosts,
                'basis': 'Every remote-TP host, weight endpoint and in-phase native aggregate port is covered. Absent ports have no recorded phase partition and no relevant phase event; inactivity is source-derived, not measured. No partition rows are fabricated.'},
            'hot_return_ports': {'ranking': 'All observed shared return ports ranked by weight-phase ACK/weight-response VOQ residence sum, then TX count; top eight. Unobserved inactive ports have no weight-phase cohorts.', 'ports': hot},
            'allocator_callbacks': {'whole_run': callbacks, 'weight_phase_event_cohorts': callback_summary(phase),
                'semantics': 'Requested services and callback durations are event aggregates, not disjoint wall time; phase starts and ends can straddle boundaries.'},
            'feedback': feedback, 'jetty': jetty, 'multicast': multicast, 'physical_network': physical,
            'host_resources': resource, 'verification': validations,
            'no_loss_evidence': {'aggregate_contract_passed': True,
                'basis': ['All 128 directed native links conserve TX/RX packets and bytes.',
                    'Per-source token/weight WRITE, TPACK and TAACK totals match the complete transfer graph.',
                    'All-pair admissions, accepted TAACKs and SSN progress reconcile exactly; native pairs complete.',
                    'Native retransmission and fault injection are disabled; simulator payload/completion and independent compute validations passed.']
                    + (['Multicast envelopes/branches/source bytes reconcile; native retry and injected-test-loss counters are zero.'] if multicast['applicable'] else []),
                'limits': 'No global drop counter is provided. This is a no-loss/no-retry aggregate consistency contract, not a direct measurement of every possible drop event. Disabled selected RTT counters are not part of this evidence.'},
            'cautions': ['Native partitions sum disjoint time within each port; sums across ports/nodes are resource-time, not elapsed wall time.',
                'Class 1 is TPACK plus weight TAACK; token TAACK is class 2. Native cohort residence sums overlap and are not causal wall-time attribution.',
                'Critical transfers include every receiver-ready tie at WeightReady; no fixed historical source is presumed critical.',
                'Only aggregate files were read; no raw rings, per-token traces or TA RTT samples are exported.']}
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('Missing or malformed required aggregate field') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = analyze_case(args.directory)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'strategy': report['strategy'],
                      'tokens': report['tokens'], 'timing': report['timing']}))


if __name__ == '__main__':
    main()
