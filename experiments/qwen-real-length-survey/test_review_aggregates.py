"""Synthetic-only fault tests for the separately implemented readback checker."""
import csv
import gzip
import json
import unittest
import review_aggregates as review
import test_offline_batch as fixtures


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Tests()
        self.fixture.setUp()
        self.fixture.run_batch()
        self.root = self.fixture.root
        # Normalize fixtures to plaintext; the success test then repackages them.
        for path in (self.root/'stats').glob('*.csv.gz'):
            path.with_suffix('').write_bytes(gzip.decompress(path.read_bytes()))
            path.unlink()

    def tearDown(self):
        self.fixture.tearDown()

    def check(self):
        return review.review(self.fixture.path, self.root/'stats', self.root/'private')

    def test_success_plain_and_gzip(self):
        self.assertEqual(self.check()['status'], 'PASS')
        for path in (self.root/'stats').glob('*.csv'):
            with gzip.open(str(path)+'.gz','wb') as f:
                f.write(path.read_bytes())
            path.unlink()
        self.assertEqual(self.check()['status'], 'PASS')

    def test_reject_corrupted_statistic(self):
        path=self.root/'stats/layer-statistics.csv'
        with path.open(newline='') as f: rows=list(csv.DictReader(f))
        rows[0]['gini']='0.123456789'
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
        with self.assertRaises(AssertionError): self.check()

    def test_reject_export_row_swap(self):
        path=self.root/'private/batch/layer_0.csv'
        lines=path.read_text().splitlines()
        lines[1],lines[2]=lines[2],lines[1]
        path.write_text('\n'.join(lines)+'\n')
        with self.assertRaises(AssertionError): self.check()

if __name__=='__main__': unittest.main()
