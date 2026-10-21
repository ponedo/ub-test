#!/usr/bin/env python3
"""Pure arithmetic/schema tests. No native binaries or simulations are invoked."""
import copy
import importlib.util
from pathlib import Path
import unittest

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ablation_analyze', H / 'analyze.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AnalysisTests(unittest.TestCase):
    def test_did_signs_and_identity(self):
        cases = {}
        for w, chunk, mc in [(512, 100, 150), (1024, 90, 120), (2048, 95, 125)]:
            for strategy, value in [('chunk-streaming', chunk), ('multicast-v2', mc)]:
                key = m.case_id(w, strategy)
                cases[key] = dict(case_id=key, weight_ps=value, layer_ps=value + 20)
        within, between = m.timing_contrasts(cases)
        self.assertEqual(between[1]['weight_difference_in_differences_ps'], -20)
        self.assertEqual(between[1]['weight_gap_reduction_vs_512_ps'], 20)
        self.assertEqual(between[2]['weight_difference_in_differences_ps'], -20)
        self.assertAlmostEqual(within[3]['weight_relative_change_percent'], -20)
        self.assertAlmostEqual(within[3]['weight_intervention_speedup_vs_same_strategy_512'], 1.25)

    def test_negative_did_can_be_chunk_harm(self):
        cases = {}
        for w, chunk, mc in [(512, 100, 150), (1024, 120, 150), (2048, 120, 150)]:
            for s, value in [('chunk-streaming', chunk), ('multicast-v2', mc)]:
                key = m.case_id(w, s)
                cases[key] = dict(case_id=key, weight_ps=value, layer_ps=value)
        within, between = m.timing_contrasts(cases)
        self.assertEqual(between[1]['weight_difference_in_differences_ps'], -20)
        self.assertEqual(within[3]['weight_absolute_change_ps'], 0)
        self.assertEqual(within[2]['weight_absolute_change_ps'], 20)

    def test_exposure_weighted_not_pair_mean(self):
        data = [dict(t=10, a=50, f=5, max_outstanding=10),
                dict(t=90, a=90, f=0, max_outstanding=1)]
        result = m.integrated_occupancy(data, 't', 'a', 'f')
        self.assertEqual(result['mean_outstanding_tas'], 1.4)
        self.assertEqual(result['full_window_fraction'], .05)
        self.assertEqual(result['exposure_jetty_ps'], 100)
        with self.assertRaises(ValueError):
            m.integrated_occupancy([dict(t=1, a=1, f=2, max_outstanding=1)], 't', 'a', 'f')

    def test_original_numbers_not_treatment_numbers(self):
        self.assertEqual(m.ACCEPTED['multicast-v2']['weight_ps'] - m.ACCEPTED['chunk-streaming']['weight_ps'], 164289264)
        self.assertLess(m.contrast(90, 100)['relative_change_percent'], 0)
        with self.assertRaises(ValueError):
            m.contrast(90, 0)

    def test_histogram_integrity(self):
        row = {key: 0 for key in ('terminal_outstanding', 'ssn_next', 'ssn_una',
            'admissions', 'window_tests', 'window_limited_tests', 'accepted_taacks', 'ssn_progress',
            'rejected_taacks', 'duplicate_taacks', 'weight_ack_without_source_tx', 'weight_ack_without_native_pop',
            'window_full_intervals', 'max_window_full_interval_ps')}
        row.update(source=3, target=59, jetty=9, window=512, max_outstanding=512,
            observed_ps=100, outstanding_ta_ps=25600, window_saturated_ps=50,
            weight_phase_observed_ps=50, weight_phase_outstanding_ta_ps=12800,
            weight_phase_window_saturated_ps=25)
        for boundary in ('weight_admission_to_ack', 'weight_native_pop_to_ack', 'weight_source_tx_to_ack'):
            row.update({boundary + '_count': 1, boundary + '_sum_ps': 50, boundary + '_max_ps': 50})
        hist = [dict(source=3, target=59, jetty=9, window=512, bin=b,
                     all_observed_ps=50 if b in (0, 5) else 0,
                     weight_phase_ps=25 if b in (0, 5) else 0) for b in range(6)]
        occupancy, latency, bins = m.jetty_summary([row], hist, 512)
        self.assertEqual(occupancy[0]['full_window_fraction'], .5)
        self.assertEqual(len(bins), 8 * 2 * 6)
        damaged = copy.deepcopy(hist)
        damaged[0]['all_observed_ps'] += 1
        with self.assertRaises(ValueError):
            m.jetty_summary([row], damaged, 512)


if __name__ == '__main__':
    unittest.main()
