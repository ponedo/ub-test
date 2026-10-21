#!/usr/bin/env python3
"""Synthetic aggregate-contract tests only. Never launches a simulation."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('screening_analyze', Path(__file__).with_name('analyze.py'))
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def write_json(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def write_csv(root, name, data):
    with (root / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def change_json(root, name, update):
    value = json.loads((root / name).read_text())
    update(value)
    write_json(root, name, value)


def change_csv(root, name, update):
    with (root / name).open(newline='') as stream:
        data = list(csv.DictReader(stream))
    update(data)
    write_csv(root, name, data)


def fixture(root, strategy='chunk-streaming'):
    begin, end = 1000, 101000
    edges = [(1, 3), (3, 4)] if strategy == 'chunk-streaming' else [(1, 3), (1, 4)]
    transfers = [dict(task=i, stage=2, source=s, target=t, physical=i, bytes=1024, offset=0)
                 for i, (s, t) in enumerate(edges)]
    config = {'planner_input': {'npus': 64, 'mapping': [{}] * 256}, 'weight_strategy': strategy,
              'runtime': dict(link_gbps=3136, link_delay_ns=20, segment_bytes=1024, weight_bytes=1024),
              'transfers': transfers, 'multicast_groups': []}
    if strategy == 'multicast-v2':
        config['multicast_groups'] = [dict(group=1, source=1, members=[dict(target=3), dict(target=4)])]
    write_json(root, 'config.json', config)
    write_json(root, 'compute-model.json', dict(model='roofline', compute_tflops=100,
        hbm_bandwidth_gbps=2692, roofline_launch_ns=0))
    write_json(root, 'ablation-config.json', dict(jetty_ta_window=512, jetty_ooo_ack_window=2048,
        tp_packet_window=1000, measurement_enabled=True, allocator_policy='original',
        logical_ssn_uint32_no_wrap_bound=True, predicted_total_tas_upper_bound=2))
    write_json(root, 'simulator-host/resource.json', dict(status='PASS', returncode=0, guard=None,
        command=['/private/build/layer', '--diagnostic=1', '--diagnosticSource=4294967294',
                 '--diagnosticGroup=4294967294', '--logLevel=summary'], wall_seconds=1.5,
        user_cpu_seconds=1.2, system_cpu_seconds=.1, peak_rss_kib=4096,
        sampled_peak_tree_rss_bytes=4194304, max_observed_threads_per_process=1,
        host_before={'cpuinfo': 'PRIVATE-MACHINE-SECRET'}, cwd='/private/dataset'))
    for name in ('validation.json', 'compute-validation.json'):
        write_json(root, name, dict(status='PASS'))
    write_csv(root, 'transfers.csv', transfers)
    write_json(root, 'diagnostic-status.json', dict(enabled=True, incomplete=False,
        last_weight_ready_ps=end, queue_observations_open=0, queue_unmatched=0,
        queue_order_errors=0, queue_depth_errors=0, grant_outcomes_unmatched=0,
        grant_start_overwrites=0, grant_starts_open=0))
    write_json(root, 'diagnostic-jetty-status.json', dict(incomplete=False, tracked_jetties=2,
        terminal_nonzero_jetties=0, pending_ta_observations=0, pending_source_frames=0,
        pending_ack_marks=0, occupancy_errors=0, unmatched_accepted_taacks=0))
    parts = [dict(node=n, port=p, phase_start_ps=begin, phase_end_ps=end,
        tx_busy_union_ps=30000, allocator_pending_excluding_tx_ps=20000,
        uncovered_idle_ps=50000, total_ps=end-begin) for n, p in sorted(analyze.PORTS)]
    write_csv(root, 'diagnostic-port-partition.csv', parts)
    write_csv(root, 'diagnostic-source-last-send-partition.csv', [dict(node=s, port=0,
        phase_start_ps=begin, last_weight_native_send_ps=5000, tx_busy_union_ps=2000,
        allocator_pending_excluding_tx_ps=1000, uncovered_idle_ps=1000, total_ps=4000)
        for s in sorted({s for s, t in edges})])
    diagnostic = [{**r, 'expert': 0, 'submit_ps': begin, 'first_native_send_ps': 2000,
        'last_native_send_ps': 5000, 'last_received_ps': end, 'receiver_ready_ps': end,
        'sender_complete_ps': end+2000} for r in transfers]
    write_csv(root, 'diagnostic-transfers.csv', diagnostic)
    outgoing, incoming = [0]*64, [0]*64
    for s, t in edges:
        outgoing[s] += 1
        incoming[t] += 1
    packets = []
    def packet(node, port, kind, count, size):
        if count:
            packets.append(dict(node=node, port=port, kind=kind, packets=count, wire_bytes=count*size))
    for s in range(64):
        packet(s, 0, 'weight_write', outgoing[s] if strategy == 'chunk-streaming' else 0, 1102)
        packet(64, s, 'weight_write', incoming[s], 1102)
        packet(s, 0, 'transport_ack', outgoing[s]+incoming[s], 64)
        packet(64, s, 'transport_ack', outgoing[s]+incoming[s], 64)
        packet(s, 0, 'transaction_response', incoming[s], 78)
        packet(64, s, 'transaction_response', outgoing[s], 78)
    packet(0, 0, 'credit', 1, 16)
    if strategy == 'multicast-v2':
        packet(1, 0, 'multicast_v2', 1, 1200)
        write_json(root, 'multicast-lifecycle.json', dict(status='PASS', pair_jetties=2,
            native_retry_packets=0, injected_losses=0, pending_associations=0, invalidated_grants=0,
            envelopes=1, branches=2))
        write_csv(root, 'multicast-stats.csv', [dict(group=1, source=1, fanout=2, payload_bytes=1024,
            wire_bytes=1200, envelopes=1, native_singleton_packets=0, header_bytes=176,
            association_limit=32, association_peak=2, association_restored=2,
            first_send_grants=1, admitted_ps=begin, first_send_done_ps=5000)])
    write_csv(root, 'packet-counts.csv', packets)
    metrics = {}
    def metric(m, n, p, c, count, total, maximum):
        key = m, n, p, c
        row = metrics.setdefault(key, dict(metric=m, node=n, port=p, **{'class': c}, count=0, sum=0, max=0))
        row['count'] += count
        row['sum'] += total
        row['max'] = max(maximum, row['max'])
    txp, txb, rxp, rxb = [0]*65, [0]*65, [0]*65, [0]*65
    for row in packets:
        n, p = row['node'], row['port']
        peer = (64, n) if n < 64 else (p, 0)
        cls = 0 if row['kind'] in ('weight_write', 'multicast_v2') else 2 if row['kind'] == 'credit' else 1
        metric(5, n, p, cls, row['packets'], row['wire_bytes'], row['wire_bytes']//row['packets'])
        metric(6, *peer, cls, row['packets'], row['wire_bytes'], row['wire_bytes']//row['packets'])
        txp[n] += row['packets']; txb[n] += row['wire_bytes']
        rxp[peer[0]] += row['packets']; rxb[peer[0]] += row['wire_bytes']
    for n, p in sorted(analyze.PORTS):
        committed = sum(r['packets'] for r in packets if (r['node'], r['port']) == (n, p))
        if committed:
            metric(2, n, p, 2, committed, 5000*committed, 5000)
            metric(10, n, p, 2, committed, 5000*committed, 5000)
    # Port 17, not a historical or terminal source, is deliberately hottest.
    metric(0, 64, 17, 1, 5, 50000, 10000)
    write_csv(root, 'diagnostic-native-aggregates.csv', list(metrics.values()))
    write_csv(root, 'diagnostic-weight-phase-cohorts.csv', [dict(r, cohort=(
        'end_event_in_weight_phase_full_residence' if r['metric'] in (0, 1, 3, 8, 9, 10) or r['metric'] >= 1000
        else 'event_start_in_weight_phase_full_value')) for r in metrics.values()])
    summary = dict(completed_tokens=256, log_level='summary', remote_WQEs=2,
        sender_completions=2, TA_count=2, jettys=2, event_spans={'weights_start': [begin, begin]},
        timeline={'weights_end': end}, layer_latency_ps=200000,
        packet_tx_per_node=txp, packet_rx_per_node=rxp, byte_tx_per_node=txb, byte_rx_per_node=rxb)
    write_json(root, 'online-summary.json', summary)
    jetties, hist = [], []
    for jid, (s, t) in enumerate(edges):
        row = dict(source=s, target=t, jetty=jid, window=512, ssn_next=1, ssn_una=1,
            terminal_outstanding=0, max_outstanding=1, max_window_full_interval_ps=0,
            weight_ack_without_source_tx=0, weight_ack_without_native_pop=0,
            admissions=1, window_tests=1, window_limited_tests=0, accepted_taacks=1,
            rejected_taacks=0, duplicate_taacks=0, ssn_progress=1, cleanup_events=0,
            window_full_intervals=0, observed_ps=120000, outstanding_ta_ps=100,
            window_saturated_ps=0, weight_phase_observed_ps=100000,
            weight_phase_outstanding_ta_ps=100, weight_phase_window_saturated_ps=0)
        for prefix in ('admission_to_ack', 'weight_admission_to_ack', 'weight_native_pop_to_ack', 'weight_source_tx_to_ack'):
            for suffix in ('_count', '_sum_ps', '_max_ps'):
                row[prefix+suffix] = 0
        jetties.append(row)
        for b in range(6):
            hist.append(dict(source=s, target=t, jetty=jid, window=512, bin=b,
                all_observed_ps=119900 if b == 0 else 100 if b == 1 else 0,
                weight_phase_ps=99900 if b == 0 else 100 if b == 1 else 0))
    write_csv(root, 'diagnostic-jetty-aggregates.csv', jetties)
    write_csv(root, 'diagnostic-jetty-occupancy.csv', hist)
    # Deliberately invalid forbidden files ensure no fallback reads are possible.
    for name in ('diagnostic-tail.csv', 'diagnostic-weight-tail.csv', 'diagnostic-jetty-tail.csv',
                 'diagnostic-jetty-weight-tail.csv', 'diagnostic-ta-rtt-tail.csv', 'events.csv', 'weight-packets.csv'):
        (root / name).write_text('NOT TO BE READ\n')


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_chunk_success_all_ties_relay_feedback_and_hot_port(self):
        result = analyze.analyze_case(self.root)
        self.assertEqual(result['timing']['weight_duration_ps'], 100000)
        self.assertEqual(result['critical_transfer_count'], 2)
        self.assertEqual({r['source'] for r in result['critical_transfers']}, {1, 3})
        self.assertEqual(len(result['native_partitions_by_node']), 65)
        self.assertEqual(result['hot_return_ports']['ports'][0]['port'], 17)
        relay = result['feedback']['sources'][3]
        self.assertEqual(relay['incoming_weight_tas'], 1)
        self.assertEqual(relay['weight_return_tpack_after_token_subtraction'], 2)
        self.assertEqual(relay['weight_return_taack_after_token_subtraction'], 1)
        self.assertEqual(relay['weight_return_feedback_frames'], 3)
        self.assertEqual(relay['nominal_weight_return_allocator_service_ps'], 15000)
        self.assertEqual(result['feedback']['physical_tpack_transmissions'], 8)
        self.assertEqual(result['feedback']['physical_taack_transmissions'], 4)
        self.assertFalse(result['jetty']['selected_ta_rtt']['completeness_evidence'])
        self.assertEqual(result['host_resources']['cpu_seconds'], 1.3)
        self.assertTrue(all(p['accounting_residual_ps'] == 0 for p in result['critical_source_paths']))

    def test_every_critical_target_has_forward_and_receiver_resources(self):
        for strategy, expected in (('chunk-streaming', {(1, 3), (3, 4)}),
                                   ('multicast-v2', {(1, 3), (1, 4)})):
            fixture(self.root, strategy)
            result = analyze.analyze_case(self.root)
            found = set()
            for source in result['critical_source_paths']:
                for target in source['target_paths']:
                    found.add((source['source'], target['target']))
                    self.assertEqual(target['forward_switch_port']['node'], 64)
                    self.assertEqual(target['forward_switch_port']['port'], target['target'])
                    self.assertEqual(target['receiver_port']['node'], target['target'])
                    self.assertEqual(target['receiver_port']['port'], 0)
                    self.assertGreater(target['forward_switch_port']['weight_tx']['count'], 0)
                    self.assertGreater(target['receiver_port']['weight_rx']['count'], 0)
            self.assertEqual(found, expected)

    def test_credit_frames_count_as_allocator_commits(self):
        result = analyze.analyze_case(self.root)
        self.assertEqual(result['allocator_callbacks']['whole_run']['committed']['count'],
                         result['physical_network']['physical_tx_packets'])
        with (self.root / 'packet-counts.csv').open(newline='') as stream:
            credits = [r for r in csv.DictReader(stream) if r['kind'] == 'credit']
        self.assertEqual(sum(int(r['packets']) for r in credits), 1)

    def test_multicast_success(self):
        fixture(self.root, 'multicast-v2')
        result = analyze.analyze_case(self.root)
        self.assertEqual(result['multicast']['envelopes'], 1)
        self.assertEqual(result['multicast']['native_branches'], 2)
        self.assertEqual(result['multicast']['source_wire_bytes'], 1200)
        self.assertNotIn('global_drop', json.dumps(result))

    def test_never_reads_tails_or_exports_private_metadata(self):
        original = Path.open
        def limited(path, *args, **kwargs):
            self.assertNotIn('tail', path.name)
            self.assertNotIn(path.name, ('events.csv', 'weight-packets.csv'))
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', limited):
            output = json.dumps(analyze.analyze_case(self.root))
        self.assertNotIn('PRIVATE-MACHINE-SECRET', output)
        self.assertNotIn('/private/', output)
        self.assertNotIn(self.temp.name, output)
        self.assertNotIn('host_before', output)

    def test_missing_and_corrupt_evidence_fail(self):
        (self.root / 'diagnostic-native-aggregates.csv').unlink()
        with self.assertRaises(ValueError):
            analyze.analyze_case(self.root)
        fixture(self.root)
        (self.root / 'config.json').write_text('{bad')
        with self.assertRaises(ValueError):
            analyze.analyze_case(self.root)

    def test_reject_changed_scope(self):
        for update in (lambda v: v['planner_input'].update(mapping=[{}]*512),
                       lambda v: v['runtime'].update(link_gbps=1568),
                       lambda v: v.update(weight_strategy='direct')):
            with self.subTest(update=update):
                fixture(self.root)
                change_json(self.root, 'config.json', update)
                with self.assertRaises(ValueError):
                    analyze.analyze_case(self.root)

    def test_reject_filtered_native_or_selected_rtt(self):
        change_json(self.root, 'simulator-host/resource.json',
                    lambda v: v['command'].append('--diagnosticNodes=3,64'))
        with self.assertRaisesRegex(ValueError, 'Global aggregate'):
            analyze.analyze_case(self.root)
        fixture(self.root)
        change_csv(self.root, 'diagnostic-jetty-aggregates.csv',
                   lambda rs: rs[0].update(admission_to_ack_count='1'))
        with self.assertRaisesRegex(ValueError, 'Disabled selected-TA'):
            analyze.analyze_case(self.root)

    def test_reject_missing_native_node(self):
        change_csv(self.root, 'diagnostic-port-partition.csv',
                   lambda rs: rs.__setitem__(slice(None), [r for r in rs if not (r['node']=='64' and r['port']=='3')]))
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            analyze.analyze_case(self.root)

    def test_accept_legitimately_absent_idle_switch_partition(self):
        change_csv(self.root, 'diagnostic-port-partition.csv',
                   lambda rs: rs.__setitem__(slice(None), [r for r in rs if not (r['node']=='64' and r['port']=='63')]))
        change_csv(self.root, 'diagnostic-weight-phase-cohorts.csv',
                   lambda rs: rs.__setitem__(slice(None), [r for r in rs if not (r['node']=='64' and r['port']=='63')]))
        result = analyze.analyze_case(self.root)
        self.assertEqual(result['native_partition_coverage']['recorded_ports'], 127)
        self.assertEqual(result['native_partition_coverage']['unobserved_switch_ports'], [63])
        self.assertEqual(result['native_partitions_by_node'][64]['total_ps'], 6300000)

    def test_reject_bad_callback_and_partition(self):
        change_csv(self.root, 'diagnostic-native-aggregates.csv',
                   lambda rs: next(r for r in rs if r['metric']=='2').update(sum='4999'))
        with self.assertRaises(ValueError):
            analyze.analyze_case(self.root)
        fixture(self.root)
        change_csv(self.root, 'diagnostic-port-partition.csv', lambda rs: rs[0].update(total_ps='100001'))
        with self.assertRaisesRegex(ValueError, 'partition conservation'):
            analyze.analyze_case(self.root)

    def test_reject_tpack_and_taack_mismatches(self):
        for kind in ('transport_ack', 'transaction_response'):
            with self.subTest(kind=kind):
                fixture(self.root)
                change_csv(self.root, 'packet-counts.csv',
                    lambda rs: next(r for r in rs if r['kind']==kind).update(packets='19'))
                with self.assertRaisesRegex(ValueError, 'TPACK|TAACK|Committed allocation'):
                    analyze.analyze_case(self.root)

    def test_reject_physical_loss_and_jetty_incomplete(self):
        change_json(self.root, 'online-summary.json', lambda v: v['packet_rx_per_node'].__setitem__(3, 0))
        with self.assertRaisesRegex(ValueError, 'physical counters'):
            analyze.analyze_case(self.root)
        fixture(self.root)
        change_csv(self.root, 'diagnostic-jetty-aggregates.csv', lambda rs: rs[0].update(accepted_taacks='0'))
        with self.assertRaisesRegex(ValueError, 'accepted TAACK'):
            analyze.analyze_case(self.root)

    def test_reject_bad_histogram_and_duplicate_rows(self):
        change_csv(self.root, 'diagnostic-jetty-occupancy.csv', lambda rs: rs[0].update(all_observed_ps='0'))
        with self.assertRaisesRegex(ValueError, 'integral mismatch'):
            analyze.analyze_case(self.root)
        fixture(self.root)
        change_csv(self.root, 'diagnostic-port-partition.csv', lambda rs: rs.append(copy.deepcopy(rs[0])))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            analyze.analyze_case(self.root)

    def test_reject_mc_retry_or_test_loss(self):
        for key in ('native_retry_packets', 'injected_losses'):
            with self.subTest(key=key):
                fixture(self.root, 'multicast-v2')
                change_json(self.root, 'multicast-lifecycle.json', lambda v: v.update({key: 1}))
                with self.assertRaisesRegex(ValueError, 'Multicast lifecycle'):
                    analyze.analyze_case(self.root)

    def test_reject_enabled_retransmission(self):
        change_json(self.root, 'simulator-host/resource.json',
                    lambda v: v['command'].append('--nativeRetrans=1'))
        with self.assertRaisesRegex(ValueError, 'Fault injection'):
            analyze.analyze_case(self.root)

    def test_reject_failed_verifier_or_guard(self):
        write_json(self.root, 'independent-host/resource.json', dict(status='FAIL', returncode=1, guard=None))
        with self.assertRaisesRegex(ValueError, 'External verifier'):
            analyze.analyze_case(self.root)

    def test_cli_output(self):
        out = self.root / 'public-summary.json'
        completed = subprocess.run([sys.executable, str(Path(__file__).with_name('analyze.py')),
            str(self.root), '--out', str(out)], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout)['status'], 'PASS')
        self.assertEqual(json.loads(out.read_text())['tokens'], 256)


if __name__ == '__main__':
    unittest.main()
