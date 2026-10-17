"""Synthetic failure-injection tests; no restricted routing content embedded."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('checker', Path(__file__).with_name('independent_validator.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class IndependentValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'synthetic.json'
        self.source = [{str(layer): [list(range(8)), list(range(8,16))] for layer in range(94)},
                       {str(layer): [list(range(8))] for layer in range(94)}]

    def write(self):
        self.path.write_text(json.dumps(self.source))

    def test_valid_and_conservation(self):
        self.write()
        _, data = checker.read_source(self.path)
        m, loads = checker.independent_metrics(data[0]['0'])
        self.assertEqual(m['assignments'], 16)
        self.assertEqual(sum(loads), 16)
        self.assertAlmostEqual(m['jain'], 0.125)
        self.assertAlmostEqual(m['gini'], 0.875)
        self.assertAlmostEqual(m['cv'], 7**0.5)

    def test_missing_layer(self):
        del self.source[0]['93']
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_reordered_layers(self):
        self.source[0] = dict(reversed(list(self.source[0].items())))
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_phase_shape_convention(self):
        for layer in self.source[1]:
            self.source[1][layer].append(list(range(8,16)))
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)
        self.source = [{str(layer): [list(range(8))] for layer in range(94)}]
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_duplicate_json_key(self):
        self.path.write_text('[{"0": [], "0": []}]')
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_bad_experts(self):
        for value in [-1, 128, 2.0, True, 1]:
            with self.subTest(value=value):
                self.source[0]['0'][0][0] = value
                self.write()
                with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_short_topk(self):
        self.source[0]['0'][0].pop()
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_mismatched_rows(self):
        self.source[0]['0'].pop()
        self.write()
        with self.assertRaises(ValueError): checker.read_source(self.path)

    def test_export_exact_order_and_corruption(self):
        for layer in range(94):
            with (self.root/f'layer_{layer}.csv').open('w',newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['token_id']+[f'expert_{i}' for i in range(8)])
                writer.writerows([i]+row for i,row in enumerate(self.source[0][str(layer)]))
        self.assertEqual(checker.check_exports(self.source,self.root),94*2*8)
        path=self.root/'layer_0.csv'
        original=path.read_text()
        path.write_text(original.replace('0,0,1,2,3,4,5,6,7','0,1,0,2,3,4,5,6,7'))
        with self.assertRaises(ValueError): checker.check_exports(self.source,self.root)
        path.write_text(original.replace('0,0,1,2,3,4,5,6,7','9,0,1,2,3,4,5,6,7'))
        with self.assertRaises(ValueError): checker.check_exports(self.source,self.root)
        path.write_text('\n'.join(original.splitlines()[:-1])+'\n')
        with self.assertRaises(ValueError): checker.check_exports(self.source,self.root)

if __name__=='__main__': unittest.main()
