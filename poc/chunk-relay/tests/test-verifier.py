#!/usr/bin/env python3
import csv,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify import verify,overlap
SOURCE=Path(sys.argv.pop(1))
class EvidenceTests(unittest.TestCase):
    def check_mutation(self,mutate):
        with open(SOURCE) as f: rows=list(csv.DictReader(f))
        mutate(rows)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'events.csv'
            with open(p,'w') as f:
                w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
            with self.assertRaises(AssertionError): verify(p)
    def test_baseline(self): verify(SOURCE)
    def test_disjoint_and_touching_intervals(self):
        self.assertEqual(overlap((0,10),(11,20)),0)
        self.assertEqual(overlap((0,10),(10,20)),0)
        self.assertEqual(overlap((0,10),(5,20)),5)
    def test_missing_ta(self):
        self.check_mutation(lambda rs:rs.pop(next(i for i,r in enumerate(rs) if r['event']=='target_ta_complete')))
    def test_duplicate_forward(self):
        def change(rs):
            i=next(i for i,r in enumerate(rs) if r['event']=='forward'); rs.insert(i,dict(rs[i]))
        self.check_mutation(change)
    def test_early_forward(self):
        def change(rs):
            r=next(r for r in rs if r['event']=='forward'); r['time_ps']='0'; rs.sort(key=lambda r:int(r['time_ps']))
        self.check_mutation(change)
    def test_wrong_metadata(self):
        def change(rs): next(r for r in rs if r['event']=='target_ta_complete')['bytes']='1'
        self.check_mutation(change)
    def test_missing_final(self):
        self.check_mutation(lambda rs:rs.pop(next(i for i,r in enumerate(rs) if r['event']=='chunk_complete' and r['hop']=='1')))
    def test_compute_dependency(self):
        def change(rs): next(r for r in rs if r['event']=='compute_end')['time_ps']='1'
        self.check_mutation(change)
unittest.main()
