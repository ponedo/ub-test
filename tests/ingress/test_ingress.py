import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from workloads.schema.trace import make_wr, write_trace
from simulators.nano_ub.run import prepare

BINARY=Path(os.environ.get('TRACE_BINARY','build-ingress/trace_e2e')).resolve()

class IngressTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run_id=0
    def tearDown(self):self.tmp.cleanup()
    def run_trace(self,rows,policy='rr',mode='epoch-rr',batch=64,source=4096,depth=4096):
        self.run_id+=1;out=self.root/str(self.run_id);trace=self.root/(str(self.run_id)+'.csv');write_trace(trace,rows)
        inp=prepare(trace,out,policy,mode,batch,source,depth)
        r=subprocess.run([str(BINARY),policy,str(inp),str(out/'systemc'),mode,str(batch),str(source),str(depth)],capture_output=True,text=True,timeout=45)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        def read(name):
            with (out/name).open() as f:return list(csv.DictReader(f))
        return out,read('systemc.wr.csv'),read('systemc.timeline.csv')
    def test_first_epoch_all_jetties_before_dequeue(self):
        rows=[make_wr(j*8+i,0,j,1,12672,0,i) for j in range(16) for i in range(8)]
        for policy in ('fifo','rr','drr'):
            _,_,events=self.run_trace(rows,policy)
            first=next(e for e in events if e['event']=='dequeue')
            before=[e for e in events if e['event']=='enqueue' and int(e['event_seq'])<int(first['event_seq'])]
            self.assertEqual({int(e['jetty']) for e in before},set(range(16)))
            self.assertEqual(int(first['time_ps']),16000)
    def test_small_capacities_and_rotating_bounded_batches(self):
        rows=[make_wr(j*10+i,0,j,1,64+i,0,i) for j in range(5) for i in range(10)]
        for policy in ('fifo','rr','drr'):
            _,_,events=self.run_trace(rows,policy,batch=2,source=2,depth=1)
            submit=[int(e['jetty']) for e in events if e['event']=='submit']
            self.assertEqual(submit[:5],list(range(5)))
            self.assertLessEqual(max(int(e['jetty_queued']) for e in events),1)
            for epoch in {e['epoch'] for e in events if e['event']=='submit'}:
                group=[e for e in events if e['epoch']==epoch and e['event']=='submit'];self.assertLessEqual(len(group),2)
    def test_many_single_jetty_wr_with_depth_one(self):
        _,rows,events=self.run_trace([make_wr(i,0,9,1,1,0,i) for i in range(4200)],depth=1,source=1,batch=1)
        self.assertEqual(len(rows),4200);self.assertGreater(int(rows[-1]['submit_ps']),0)
    def test_ready_groups_keep_temporal_priority(self):
        rows=[make_wr(i,0,i%4,1,128,100*(i//4),i//4) for i in range(20)]
        _,result,events=self.run_trace(rows,batch=2,source=2,depth=1)
        by_id={int(r['wr_id']):r for r in result}
        ready=[int(by_id[int(e['wr_id'])]['ready_ps']) for e in events if e['event']=='submit']
        self.assertEqual(ready,sorted(ready))
        for r in result:self.assertEqual(int(r['ready_ps']),rows[int(r['wr_id'])]['ready_ns']*1000)
    def test_dependency_blocked_jetty_does_not_join_barrier(self):
        rows=[make_wr(0,0,0,1,4096,0,0),make_wr(1,0,1,1,64,0,0),make_wr(2,0,1,1,64,0,1),make_wr(3,0,2,1,64,0,0)]
        rows[1]['depends_on']=[0]
        _,r,events=self.run_trace(rows,depth=1)
        by_id={int(x['wr_id']):x for x in r}
        self.assertEqual(int(by_id[3]['submit_ps']),0)
        self.assertGreaterEqual(int(by_id[1]['submit_ps']),int(by_id[0]['complete_ps']))
        self.assertGreaterEqual(int(by_id[2]['submit_ps']),int(by_id[1]['submit_ps']))
        first=[e['jetty'] for e in events if e['event']=='submit' and e['epoch']=='1']
        self.assertEqual(first,['0','2'])
    def test_ready_clock_runs_while_epoch_admission_waits(self):
        rows=[make_wr(j,0,j,1,64,0,0) for j in range(16)]+[make_wr(100,0,20,1,64,5,0)]
        _,r,events=self.run_trace(rows)
        ready=next(e for e in events if e['event']=='ready' and e['wr_id']=='100')
        self.assertEqual(int(ready['time_ps']),5000)
        target=next(x for x in r if x['wr_id']=='100');self.assertGreaterEqual(int(target['submit_ps']),16000)
    def test_same_time_completion_and_ready_dependency(self):
        # Use actual completion time to align another release to the same ns.
        _,r,_=self.run_trace([make_wr(0,0,0,1,122,0,0)])
        finish=int(r[0]['complete_ps']);self.assertEqual(finish%1000,0)
        rows=[make_wr(0,0,0,1,122,0,0),make_wr(1,0,1,1,64,finish//1000,0)]
        rows[1]['depends_on']=[0]
        _,rs,ev=self.run_trace(rows)
        self.assertEqual(int(rs[1]['submit_ps']),int(rs[0]['complete_ps']))
        complete=next(e for e in ev if e['event']=='complete' and e['wr_id']=='0')
        submit=next(e for e in ev if e['event']=='submit' and e['wr_id']=='1')
        self.assertGreater(int(submit['event_seq']),int(complete['event_seq']))
    def test_permutation_invariance_and_repeatability(self):
        original=[make_wr(j*8+i,0,j,1+(i%2),64+17*i,0,i) for j in range(4) for i in range(8)]
        reverse=sorted(original,key=lambda r:(-r['jetty_id'],r['sequence']))
        rotated=sorted(original,key=lambda r:(r['sequence'],r['jetty_id']))
        for policy in ('fifo','rr','drr'):
            outputs=[]
            for rows in (original,reverse,rotated,original):
                out,r,_=self.run_trace(rows,policy,batch=2,source=2,depth=2)
                outputs.append(sorted(r,key=lambda x:int(x['wr_id'])))
            self.assertTrue(all(r==outputs[0] for r in outputs))
    def test_default_projection_exact(self):
        rows=[make_wr(j*8+i,0,j,1,64,0,i) for j in range(3) for i in range(8)]
        out,_,_=self.run_trace(rows,mode='csv')
        inp=out/'input.tsv'
        subprocess.run([str(BINARY),'rr',str(inp),str(out/'default')],check=True,capture_output=True)
        for suffix in ['events.csv','wr.csv','timeline.csv']:self.assertEqual((out/('systemc.'+suffix)).read_bytes(),(out/('default.'+suffix)).read_bytes())
    def test_empty(self):self.assertEqual(self.run_trace([])[1],[])
    def test_invalid_capacity_rejected(self):
        trace=self.root/'bad.csv';write_trace(trace,[])
        with self.assertRaises(ValueError):prepare(trace,self.root/'bad','rr','epoch-rr',0)

if __name__=='__main__':unittest.main()
