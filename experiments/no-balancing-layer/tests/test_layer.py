#!/usr/bin/env python3
import argparse,csv,copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cases import generate,validate,emit,ConfigError
from verify import verify,EvidenceError
p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--ns3',required=True);args,other=p.parse_known_args();sys.argv=[sys.argv[0]]+other
class ConfigTests(unittest.TestCase):
    def test_seed(self):self.assertEqual(generate(),generate())
    def test_bad_topk(self):
        for k in [0,9,-1]:
            c=generate();c['top_k']=k
            with self.assertRaises(ConfigError):validate(c)
    def test_duplicate_and_out_of_range(self):
        for experts in [[1,1],[1,8],[-1,2]]:
            c=generate();c['mapping'][0]['experts']=experts
            with self.assertRaises(ConfigError):validate(c)
    def test_bad_placement(self):
        for placement in [[],[4]*8,[-1]*8]:
            c=generate();c['placement']=placement
            with self.assertRaises(ConfigError):validate(c)
    def test_bad_source(self):
        c=generate();c['mapping'][0]['source']=4
        with self.assertRaises(ConfigError):validate(c)
    def test_bad_model(self):
        for key,val in [('peak_gflops',0),('util_permille',1001),('dtype_bytes',0),('segment_bytes',0),('tokens',-1)]:
            c=generate();c[key]=val
            with self.assertRaises(ConfigError):validate(c)
    def test_cpp_rejects_invalid_input(self):
        c=generate()
        with tempfile.TemporaryDirectory() as d:
            case=Path(d);emit(c,case);original=(case/'input.txt').read_text().splitlines()
            mutations=[]
            v=original.copy();v[1]='4 '+' '.join(original[1].split()[1:]);mutations.append(v)
            v=original.copy();v[2]='0 1 1';mutations.append(v)
            v=original.copy();head=v[0].split();head[8]='0';v[0]=' '.join(head);mutations.append(v)
            mutations.append(original+['garbage'])
            for v in mutations:
                (case/'input.txt').write_text('\n'.join(v)+'\n')
                r=subprocess.run([sys.executable,'./ns3','run','--no-build',f'no-balancing-layer --input={case}/input.txt --out={case}/result'],cwd=args.ns3,capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0);self.assertIn('ERROR:',r.stdout+r.stderr)
class EvidenceTests(unittest.TestCase):
    def test_cases(self):
        for name in ['n4','n8','n64','skew4','empty4','local4','custom4']:verify(Path(args.evidence)/name)
    def mutate(self,fn):
        source=Path(args.evidence)/'n4'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            for name in ['config.json','input.txt','assignments.csv']:(path/name).write_bytes((source/name).read_bytes())
            with open(source/'events.csv') as f:rs=list(csv.DictReader(f))
            fn(rs)
            with open(path/'events.csv','w') as f:
                w=csv.DictWriter(f,fieldnames=rs[0].keys());w.writeheader();w.writerows(rs)
            with self.assertRaises(EvidenceError):verify(path)
    def test_missing_contribution(self):self.mutate(lambda rs:rs.pop(next(i for i,r in enumerate(rs) if r['event']=='data_ready' and r['stage']=='1')))
    def test_duplicate_token(self):
        def change(rs):
            i=next(i for i,r in enumerate(rs) if r['event']=='token_complete');rs.insert(i,dict(rs[i]))
        self.mutate(change)
    def test_wrong_payload(self):
        def change(rs):next(r for r in rs if r['event']=='payload_verified')['bytes']='1'
        self.mutate(change)
    def test_bad_ta_identity(self):
        def change(rs):next(r for r in rs if r['event']=='ta_admitted')['offset']='1'
        self.mutate(change)
    def test_early_compute(self):
        def change(rs):
            next(r for r in rs if r['event']=='compute_start')['time_ps']='0';rs.sort(key=lambda r:int(r['time_ps']))
        self.mutate(change)
    def test_early_combine(self):
        def change(rs):
            next(r for r in rs if r['event']=='send' and r['stage']=='1')['time_ps']='1000';rs.sort(key=lambda r:int(r['time_ps']))
        self.mutate(change)
    def test_wrong_expert_budget(self):
        def change(rs):
            r=next(r for r in rs if r['event']=='expert_end');r['time_ps']=str(int(r['time_ps'])-1);rs.sort(key=lambda r:int(r['time_ps']))
        self.mutate(change)
    def test_empty_local_skew(self):
        p=Path(args.evidence)
        self.assertEqual(verify(p/'empty4')['layer_latency_ps'],0)
        self.assertEqual(verify(p/'local4')['sender_completions'],0)
        self.assertEqual(verify(p/'skew4')['per_npu_assignments'],[16,0,0,0])
if __name__=='__main__':unittest.main()
