#!/usr/bin/env python3
"""Pure unit tests only: no graph tool, build, or simulator is started."""
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import common
import run
from heartbeat import Heartbeat


class HarnessTests(unittest.TestCase):
    def test_plan_semantics_exclude_only_host_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            common.write(path, {'physical': [{'quota': 3}], 'cpu_wall_ns': 1})
            first = common.semantic_plan(path)
            common.write(path, {'physical': [{'quota': 3}], 'cpu_wall_ns': 20})
            self.assertEqual(first, common.semantic_plan(path))
            common.write(path, {'physical': [{'quota': 4}], 'cpu_wall_ns': 20})
            self.assertNotEqual(first, common.semantic_plan(path))

    def test_only_default_n256_pair(self):
        self.assertEqual(common.STRATEGIES, ('chunk-streaming', 'multicast-v2'))
        self.assertEqual(common.RELAY['chunk_bytes'], 4096)
        command = common.simulator('/binary/layer', Path('/private/case'))
        self.assertIn('--jetty-ta-window=512', command)
        self.assertIn('--compute-tflops=100', command)
        self.assertIn('--hbm-bandwidth-gbps=2692', command)
        self.assertIn('--logLevel=summary', command)
        self.assertIn('--diagnosticSource=4294967294', command)
        self.assertIn('--diagnosticGroup=4294967294', command)
        self.assertFalse(any(x.startswith('--diagnosticNodes') for x in command))
        self.assertFalse(any(x.startswith(('--nativeRetrans', '--networkFault', '--fault', '--invalidateGrant')) for x in command))

    def test_immutable_identity_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_text('accepted')
            identity = common.freeze([path])
            common.check(identity)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Immutable file changed'):
                common.check(identity)

    def test_existing_stage_cannot_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(run, 'load', side_effect=AssertionError('must not load guard')):
                with self.assertRaisesRegex(ValueError, 'No implicit restart'):
                    run.stage(['not-executed'], Path(directory), {})

    def test_no_approval_cannot_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common.write(root / 'ledger.json', {'status': 'PREPARED'})
            common.write(root / 'prepared-manifest.json', {'tokens': 256})
            common.write(root / 'approval.json', {'status': 'PASS', 'approved_to_run': False})
            args = type('Args', (), {'private': root, 'approval': root / 'approval.json'})()
            with patch.object(run, 'stage', side_effect=AssertionError('must not start')):
                with self.assertRaisesRegex(ValueError, 'Explicit preflight approval missing'):
                    run.run_pair(args)

    def test_stopped_campaign_cannot_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common.write(root / 'ledger.json', {'status': 'STOPPED'})
            common.write(root / 'prepared-manifest.json', {'tokens': 256})
            args = type('Args', (), {'private': root, 'approval': root / 'none'})()
            with self.assertRaisesRegex(ValueError, 'No implicit resume or rerun'):
                run.run_pair(args)

    def test_heartbeat_is_thread_free_and_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            heartbeat = Heartbeat(Path(directory), ['not-executed'])
            self.assertFalse(hasattr(heartbeat, 'thread'))
            heartbeat.start()
            heartbeat.tick()
            heartbeat.stop('PASS')
            result = common.read(Path(directory) / 'host-heartbeat.json')
            self.assertEqual(result['status'], 'PASS')
            self.assertGreater(result['driver']['pid'], 0)
            self.assertGreater(result['driver']['start_time_unix'], 0)
            self.assertTrue(result['driver']['pid_namespace'])
            self.assertTrue(result['last_sample_utc'])

    def test_sample_proxy_restored_without_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.write_text('immutable')
            accepted = types.SimpleNamespace(m=types.SimpleNamespace(time=time))
            def fake_run(*args, **kwargs):
                accepted.m.time.sleep(0)
                return {'status': 'PASS', 'guard': None}
            accepted.run = fake_run
            with patch.object(run, 'load', return_value=accepted):
                result = run.stage(['not-executed'], root / 'stage', common.freeze([source]))
            self.assertEqual(result['status'], 'PASS')
            self.assertIs(accepted.m.time, time)
            self.assertEqual(common.read(root / 'stage/host-heartbeat.json')['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
