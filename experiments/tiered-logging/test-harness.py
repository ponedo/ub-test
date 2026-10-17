#!/usr/bin/env python3
"""Fast self-tests of result accounting and independent CSV aggregation."""
import tempfile
import unittest
from pathlib import Path
from common import account_files, differences, event_evidence, stable


class Helpers(unittest.TestCase):
    def test_only_documented_fields_excluded(self):
        left = {'log_level': 'debug', 'verification_wall_ns': 4, 'simulator_events': 7, 'nested': [{'count': 3}]}
        right = {'log_level': 'summary', 'verification_wall_ns': 9, 'simulator_events': 7, 'nested': [{'count': 3}]}
        self.assertEqual(stable(left), stable(right))
        right['simulator_events'] += 1
        self.assertEqual(differences(stable(left), stable(right)), ['simulator_events'])

    def test_accounting_excludes_inputs_and_metadata(self):
        out = account_files({'input.txt': 100, 'config.json': 200, 'input-summary.json': 50,
                             'online-summary.json': 10, 'events.csv': 20, 'received-payloads.bin': 30,
                             'native/PacketTrace_node_0.csv': 40})
        self.assertEqual(out['generated_bytes'], 100)
        self.assertEqual(out['total_bytes'], 450)
        self.assertEqual(out['categories']['native_traces'], 40)
        self.assertEqual(out['categories']['inputs'], 300)
        self.assertEqual(out['categories']['input_metadata'], 50)

    def test_independent_spans(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'events.csv'
            path.write_text('time_ps,event,stage,id,node,offset,bytes,task\n'
                            '2,send,0,0,0,0,4,0\n5,data_ready,0,0,1,0,4,0\n'
                            '5,compute_start,-1,0,1,0,0,-1\n8,compute_end,-1,0,1,0,0,-1\n'
                            '8,send,1,0,1,0,4,1\n10,data_ready,1,0,0,0,4,1\n')
            value = event_evidence(path)
            self.assertEqual(value['row_count'], 6)
            self.assertEqual(value['timeline']['send'], [2, 8, 2])
            self.assertEqual(value['stage_spans'], {'dispatch': [2, 5, 3], 'compute': [5, 8, 3], 'combine': [8, 10, 2]})


if __name__ == '__main__':
    unittest.main()
