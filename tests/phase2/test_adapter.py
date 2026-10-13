import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from workloads.schema.trace import make_wr, write_trace
from simulators.nano_ub.run import prepare

BINARY=Path(os.environ.get('TRACE_BINARY','build-phase2/trace_e2e')).resolve()

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def run_trace(self,rows,policy='drr',tag='run'):
        trace=self.root/(tag+'.csv');write_trace(trace,rows)
        out=self.root/tag;prepared=prepare(trace,out,policy)
        result=subprocess.run([str(BINARY),policy,str(prepared),str(out/'systemc')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        with (out/'systemc.wr.csv').open() as f:data=list(csv.DictReader(f))
        return out,data
    def test_dependencies_ready_and_independent_progress(self):
        rows=[make_wr(10,7,90,8,4096,0,0),make_wr(20,7,5,9,64,0,0),
              make_wr(30,7,90,9,64,0,1),make_wr(40,7,6,8,64,0,0),make_wr(50,7,90,8,1,5000,2)]
        rows[1]['depends_on']=[10];rows[2]['depends_on']=[20]
        for policy in ('fifo','rr','drr'):
            with self.subTest(policy=policy):
                _,r=self.run_trace(rows,policy,policy);d={int(x['wr_id']):x for x in r}
                self.assertGreaterEqual(int(d[20]['submit_ps']),int(d[10]['complete_ps']))
                self.assertGreaterEqual(int(d[30]['submit_ps']),int(d[20]['complete_ps']))
                self.assertEqual(int(d[40]['submit_ps']),0)
                self.assertEqual(int(d[50]['ready_ps']),5000000)
                self.assertGreaterEqual(int(d[50]['submit_ps']),5000000)
    def test_blocked_head_preserves_jetty_order(self):
        rows=[make_wr(0,0,1,1,4096,0,0),make_wr(1,0,2,1,64,0,0),make_wr(2,0,2,1,64,0,1)]
        rows[1]['depends_on']=[0]
        _,r=self.run_trace(rows)
        self.assertGreaterEqual(int(r[2]['submit_ps']),int(r[0]['complete_ps']))
        self.assertLess(int(r[1]['dispatch_ps']),int(r[2]['dispatch_ps']))
    def test_large_payload_destination_isolation(self):
        rows=[make_wr(2**40,100,4000,3000,1048577,0,0),make_wr(2**40+1,100,5000,4000,12672,0,0)]
        out,r=self.run_trace(rows)
        with (out/'input.tsv').open() as f:
            next(f);mapped=list(csv.DictReader(f,delimiter='\t'))
        self.assertEqual([x['mem_addr'] for x in mapped],['0','0'])
        self.assertEqual([int(x['wr_id']) for x in r],[2**40,2**40+1])
    def test_fifo_capacity_and_scheduler_backpressure(self):
        rows=[make_wr(i,0,1,1,1,0,i) for i in range(8300)]
        _,r=self.run_trace(rows)
        self.assertGreater(int(r[-1]['submit_ps']),0)
    def test_empty(self):self.assertEqual(self.run_trace([])[1],[])
    def test_determinism(self):
        rows=[make_wr(i,0,i%3,1+i%2,65+i,50*(i//3),i//3) for i in range(18)]
        for p in ('fifo','rr','drr'):
            a,_=self.run_trace(rows,p,p+'a');b,_=self.run_trace(rows,p,p+'b')
            for ext in ('events.csv','wr.csv'):self.assertEqual((a/('systemc.'+ext)).read_bytes(),(b/('systemc.'+ext)).read_bytes())
    def rejected(self,rows):
        path=self.root/'bad.csv';write_trace(path,rows)
        with self.assertRaises(ValueError):prepare(path,self.root/'bad','rr')
    def test_multisource_rejected(self):self.rejected([make_wr(0,0,1,2,64,0,0),make_wr(1,1,1,2,64,0,0)])
    def test_large_size_rejected(self):self.rejected([make_wr(0,0,1,1,16777217,0,0)])
    def test_time_horizon_rejected(self):self.rejected([make_wr(0,0,1,1,64,1000000001,0)])
    def test_jetty_limit_rejected(self):self.rejected([make_wr(i,0,i,1,1,0,0) for i in range(1025)])
    def test_unknown_field_rejected(self):
        path=self.root/'bad.csv';write_trace(path,[make_wr(0,0,1,1,1,0,0)])
        path.write_text(path.read_text().replace('phase\n','phase,transport_fence\n'))
        with self.assertRaises(ValueError):prepare(path,self.root/'bad','rr')
    def test_dependency_cycle_rejected(self):
        r=make_wr(0,0,1,1,1,0,0);r['depends_on']=[0]
        with self.assertRaises(ValueError):write_trace(self.root/'bad.csv',[r])
    def test_prepared_mapping_tampering_rejected(self):
        out,_=self.run_trace([make_wr(0,0,1,1,64,0,0)])
        p=out/'input.tsv';lines=p.read_text().splitlines();v=lines[2].split('\t');v[7]='1';lines[2]='\t'.join(v);p.write_text('\n'.join(lines)+'\n')
        r=subprocess.run([str(BINARY),'rr',str(p),str(out/'bad')],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('overlapping',r.stderr)

if __name__=='__main__':unittest.main()
