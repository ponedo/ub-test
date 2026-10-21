"""Pure harness contract tests. Does not build or invoke a simulator."""
import json
from pathlib import Path
import tempfile
import unittest
from common import *

scheduler = load('controlled_ablation_scheduler_test', H / 'run-real.py')


class Contracts(unittest.TestCase):
    def test_accepted_command_cannot_receive_window_intervention(self):
        cmd = simulator(Path('/build'), Path('/case'), 'accepted')
        self.assertEqual(cmd[0], ACCEPTED / 'build/layer')
        self.assertFalse(any('jetty-ta-window' in str(value) for value in cmd))
        with self.assertRaises(AssertionError):
            simulator(Path('/build'), Path('/case'), 'accepted', 1024)

    def test_new_default_and_explicit_window_commands(self):
        default = simulator(Path('/build'), Path('/case'), 'off', explicit_window=False)
        self.assertFalse(any('jetty-ta-window' in str(value) for value in default))
        for window in WINDOWS:
            cmd = simulator(Path('/build'), Path('/case'), 'on', window)
            self.assertIn('--jetty-ta-window=' + str(window), cmd)
            self.assertIn('--diagnostic=1', cmd)
            self.assertFalse(any('allocator' in str(value) for value in cmd))

    def test_unknown_treatment_reserves_full_rss_limit(self):
        for window in [1024, 2048]:
            for strategy in REAL_STRATEGIES:
                self.assertEqual(scheduler.estimate(dict(window=window, strategy=strategy)), 6 * 1024 ** 3)
        self.assertLess(scheduler.estimate(dict(window=512, strategy='chunk-streaming')), 6 * 1024 ** 3)

    def test_identity_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'input'
            path.write_text('frozen')
            identity = freeze([path])
            check(identity)
            path.write_text('changed')
            with self.assertRaises(AssertionError):
                check(identity)

    def test_parity_excludes_only_verification_wall(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / 'a', Path(temp) / 'b'
            first.mkdir()
            second.mkdir()
            for directory, wall in [(first, 1), (second, 2)]:
                write(directory / 'online-summary.json', dict(verification_wall_ns=wall, fixed=4))
                for name in EXACT + ['events.csv']:
                    (directory / name).write_text('same\n')
            parity(first, second, True)
            write(second / 'online-summary.json', dict(verification_wall_ns=2, fixed=5))
            with self.assertRaises(AssertionError):
                parity(first, second, True)
            write(second / 'online-summary.json', dict(verification_wall_ns=2, fixed=4))
            (second / 'events.csv').write_text('changed\n')
            with self.assertRaises(AssertionError):
                parity(first, second, True)

    def test_unchanged_allocator_required(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            cfg = dict(jetty_ta_window=512, jetty_ooo_ack_window=2048, measurement_enabled=True, allocator_policy='original', tp_packet_window=1000, predicted_total_tas_upper_bound=1, logical_ssn_uint32_no_wrap_bound=True)
            write(directory / 'ablation-config.json', cfg)
            validate_config(directory, 512, True)
            cfg['allocator_policy'] = 'null-callback-suppression'
            write(directory / 'ablation-config.json', cfg)
            with self.assertRaises(AssertionError):
                validate_config(directory, 512, True)

    def test_formal_matrix_contains_six_independent_runs_and_two_stops(self):
        matrix = json.loads((H / 'matrix.yaml').read_text())
        runs = [row for row in matrix['cases'] if row['status'] == 'pending']
        stopped = [row for row in matrix['cases'] if row['status'] == 'STOPPED']
        self.assertEqual([(row['window'], row['strategy']) for row in runs], [(window, strategy) for window in WINDOWS for strategy in REAL_STRATEGIES])
        self.assertEqual(len(stopped), 2)
        self.assertTrue(all(row['allocator'] == 'original' for row in runs))
        self.assertTrue(all(row['window'] == 512 and row['measured'] is False for row in stopped))
        for row in matrix['cases']:
            self.assertTrue((H / 'cases' / row['case_id'] / 'experiment-spec.md').is_file())


if __name__ == '__main__':
    unittest.main()
