import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from workloads.schema.trace import FIELDS, make_wr, read_trace, validate, write_trace
from workloads.generators.synthetic import Config as Synthetic, generate as synthetic
from workloads.generators.moe_dispatch import Config as MoE, generate as moe, token_layout, save

ROOT = Path(__file__).resolve().parents[2]


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.rows=[make_wr(0,0,0,1,128,0,0),make_wr(1,0,0,2,256,1,1)]

    def test_round_trip_and_dependencies(self):
        self.rows[1]['depends_on']=[0]
        self.rows[1]['phase']='next-stage'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.csv';write_trace(p,self.rows)
            self.assertEqual(read_trace(p),self.rows)

    def test_machine_schema_matches_contract(self):
        schema=json.loads((ROOT/'workloads/schema/wr-trace-v1.schema.json').read_text())
        self.assertEqual(schema['required'],list(FIELDS))
        self.assertEqual(set(schema['properties']),set(FIELDS))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['schema_version']['const'],'1.0')

    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.csv';write_trace(p,[])
            self.assertEqual(read_trace(p),[])

    def test_invalid_contract(self):
        edits=[(1,'wr_id',0),(1,'sequence',3),(0,'sequence',1),
               (1,'ready_ns',-1),(0,'ready_ns',1.5),(0,'ready_ns',True),
               (0,'payload_bytes',0),(0,'payload_bytes',2**63),(0,'src_node',-1),
               (0,'opcode','READ'),(0,'schema_version','2.0'),(0,'dst_node',0),
               (0,'phase','bad phase'),(1,'depends_on',[0,0]),
               (0,'depends_on',[1]),(1,'depends_on',[1]),(1,'depends_on',[99]),
               (1,'depends_on',['0'])]
        for idx,key,value in edits:
            with self.subTest(key=key,value=value):
                rows=copy.deepcopy(self.rows);rows[idx][key]=value
                with self.assertRaises(ValueError):validate(rows)
        rows=copy.deepcopy(self.rows);rows[0]['policy']='drr'
        with self.assertRaises(ValueError):validate(rows)

    def test_node_scopes_jetty_and_global_time(self):
        rows=[make_wr(0,0,0,1,1,2,0),make_wr(1,1,0,0,1,3,0)]
        self.assertEqual(validate(rows)['active_jetties'],2)
        rows[1]['ready_ns']=1
        with self.assertRaises(ValueError):validate(rows)

    def test_reject_unknown_column_and_bad_integer(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.csv';write_trace(p,self.rows);raw=p.read_text()
            p.write_text(raw.replace('wr_id','wr_id,policy',1))
            with self.assertRaises(ValueError):read_trace(p)
            p.write_text(raw.replace(',128,',',1e2,'))
            with self.assertRaises(ValueError):read_trace(p)


class SyntheticTests(unittest.TestCase):
    def test_matches_published_batch_inputs(self):
        for load,sizes in [('mixed',(64,256,1024)),('equal',(256,))]:
            rows,_=synthetic(Synthetic(sizes=sizes))
            with (ROOT/f'eval/e2e/fifo_{load}.wr.csv').open() as f:
                old=list(csv.DictReader(f))
            self.assertEqual(len(rows),len(old))
            for a,b in zip(rows,old):
                self.assertEqual((a['wr_id'],a['jetty_id'],a['sequence'],a['payload_bytes'],a['ready_ns']),
                                 tuple(int(b[k]) for k in ['wr_id','jetty','sequence','payload_bytes','submit_ps']))

    def test_arrivals_and_seed(self):
        for pattern in ('batch','burst','poisson'):
            c=Synthetic(jetties=2,wr_per_jetty=13,sizes=(16,),arrival=pattern,seed=19)
            a,m=synthetic(c);b,_=synthetic(c)
            self.assertEqual(a,b);self.assertEqual(len(a),26)
            if pattern=='burst':
                for r in a:self.assertEqual(r['ready_ns'],r['sequence']//8*1000)
            if pattern=='poisson':
                self.assertNotEqual(a,synthetic(replace(c,seed=20))[0])
                self.assertTrue(all(r['ready_ns']>0 for r in a))

    def test_empty_and_invalid(self):
        self.assertEqual(synthetic(Synthetic(wr_per_jetty=0))[0],[])
        for kw in [dict(jetties=0),dict(wr_per_jetty=-1),dict(sizes=(1,2)),dict(sizes=(0,)),
                   dict(arrival='bogus'),dict(mean_gap_ns=float('nan')),dict(mean_gap_ns=1e30),dict(burst_size=0)]:
            with self.subTest(kw=kw),self.assertRaises(ValueError):synthetic(replace(Synthetic(),**kw))


class MoETests(unittest.TestCase):
    def test_layout_bf16_fp8(self):
        c=MoE(top_k=6,hidden_size=7168)
        self.assertEqual(token_layout(c),dict(hidden_bytes=14336,metadata_sge_bytes=96,
            scale_bytes=0,semantic_bytes=14412,transfer_bytes=14432,padding_bytes=20))
        layout=token_layout(replace(c,dtype='fp8',sf_packs=7))
        self.assertEqual(layout['metadata_sge_bytes'],128)
        self.assertEqual(layout['transfer_bytes'],7296)
        self.assertEqual(layout['padding_bytes'],38)

    def test_dedup_local_and_two_sges(self):
        c=MoE(tokens=1,capacity=16,top_k=4)
        result=moe(c,{0:[[0,1,8,9]]})
        rows,meta,wr,_=result
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['dst_node'],1)
        self.assertEqual(wr[0]['sge_count'],2)
        self.assertEqual(wr[0]['tokens'],[0])
        self.assertEqual(meta['conservation']['local_token_rank_pairs'],1)
        self.assertEqual(meta['conservation']['remote_token_rank_pairs'],1)

    def test_six_pair_tail_and_no_cross_aiv_merge(self):
        c=MoE(tokens=7,capacity=112,top_k=1)
        rows,meta,wr,_=moe(c,{0:[[8]]*7})
        self.assertEqual([m['sge_pair_count'] for m in wr],[6,1])
        self.assertEqual([m['aggregation_end'] for m in wr],['full','destination_tail'])
        self.assertEqual([m['final_sqe_fence_and_cqe'] for m in wr],[False,True])
        self.assertTrue(all(r['ready_ns']==0 for r in rows))
        # Capacity 16 gives 1 token/AIV: seven independent one-pair WRs, not 6+1.
        rows,_,wr,_=moe(replace(c,capacity=16),{0:[[8]]*7})
        self.assertEqual(len(rows),7)
        self.assertTrue(all(m['sge_pair_count']==1 for m in wr))

    def test_peer_tail_never_mixed(self):
        c=MoE(tokens=2,capacity=32,top_k=2)
        rows,_,wr,_=moe(c,{0:[[8,16],[9,17]]})
        self.assertEqual([r['dst_node'] for r in rows],[1,2])
        self.assertEqual([m['tokens'] for m in wr],[[0,1],[0,1]])
        self.assertEqual([m['sge_pair_count'] for m in wr],[2,2])

    def test_all_local_and_empty(self):
        for c,fixture in [(MoE(tokens=1,capacity=16,top_k=1),{0:[[0]]}),
                          (MoE(tokens=0,capacity=16),None)]:
            rows,meta,wr,routes=moe(c,fixture)
            self.assertEqual(rows,[]);self.assertEqual(wr,[])
            self.assertEqual(len(meta['jetties']),16)

    def test_partial_partition_and_multi_source(self):
        c=MoE(tokens=17,capacity=31,src_nodes=(0,1))
        rows,m,wr,routes=moe(c)
        owned=[x['token_end']-x['token_begin'] for x in m['jetties'] if x['src_node']==0]
        self.assertEqual(owned,[2]*8+[1]+[0]*7)
        self.assertEqual(len({r['wr_id'] for r in rows}),len(rows))
        self.assertEqual(len(routes),34)
        self.assertEqual(len(m['jetty_keys']),32)

    def test_conservation_and_partial_bound(self):
        for factor in (1.,2.):
            c=MoE(tokens=257,capacity=512,score_factor=factor,hot_rank=1)
            rows,m,wr,routes=moe(c)
            expected={(r['src_node'],r['aiv'],dst,r['token']) for r in routes
                      for dst in r['destination_ranks'] if dst!=r['src_node']}
            actual=[(x['src_node'],x['jetty_id'],x['dst_node'],token) for x in wr for token in x['tokens']]
            self.assertEqual(len(actual),len(set(actual)))
            self.assertEqual(set(actual),expected)
            self.assertEqual(sum(r['payload_bytes'] for r in rows),m['conservation']['remote_transfer_bytes'])
            self.assertEqual(sum(x['semantic_bytes']+x['padding_bytes'] for x in wr),sum(r['payload_bytes'] for r in rows))
            tails={}
            for row,x in zip(rows,wr):
                self.assertEqual(row['payload_bytes'],sum(x['sge_lengths']))
                self.assertEqual(x['sge_count'],2*x['sge_pair_count'])
                if x['sge_pair_count']<6:
                    key=x['src_node'],x['jetty_id'],x['dst_node']
                    tails[key]=tails.get(key,0)+1
            self.assertTrue(all(n==1 for n in tails.values()))

    def test_arrival_model_preserves_aggregation(self):
        c=MoE(tokens=33,capacity=64)
        a=moe(c);b=moe(replace(c,start_ns=100,aiv_stagger_ns=7,token_prep_ns=3))
        key=lambda r:(r['src_node'],r['jetty_id'],r['sequence'])
        aa={key(r):r for r in a[0]};bb={key(r):r for r in b[0]}
        self.assertEqual(set(aa),set(bb))
        for k in aa:
            self.assertEqual(aa[k]['payload_bytes'],bb[k]['payload_bytes'])
        for j in b[1]['jetties']:
            times={r['ready_ns'] for r in b[0] if (r['src_node'],r['jetty_id'])==(j['src_node'],j['jetty_id'])}
            self.assertTrue(not times or times=={100+7*j['jetty_id']+3*(j['token_end']-j['token_begin'])})

    def test_invalid_inputs(self):
        for kw in [dict(tokens=-1),dict(tokens=129),dict(capacity=0),dict(ranks=3),dict(experts=65),
                   dict(experts=1024),dict(aivs=15),dict(aivs=65),dict(top_k=33),dict(hidden_size=1),
                   dict(score_factor=float('inf')),dict(score_factor=.5),dict(hot_rank=8),
                   dict(src_nodes=(0,0)),dict(src_nodes=(8,)),dict(dtype='fp8'),dict(sf_packs=1),
                   dict(capacity=1000000,top_k=32,ranks=64,experts=512)]:
            with self.subTest(kw=kw),self.assertRaises(ValueError):moe(replace(MoE(),**kw))
        with self.assertRaises(ValueError):moe(MoE(tokens=1),{0:[[1,1,2,3]]})

    def test_sq_limit_rejects_without_fabricated_flush(self):
        with self.assertRaisesRegex(ValueError,'SQ capacity'):
            moe(MoE(tokens=0,capacity=400000))

    def test_reproducible_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a.csv',Path(d)/'b.csv'
            save(a,moe(MoE(seed=456)));save(b,moe(MoE(seed=456)))
            for suffix in ('','.meta.json','.moe.jsonl','.routes.jsonl'):
                self.assertEqual(Path(str(a)+suffix).read_bytes(),Path(str(b)+suffix).read_bytes())
            self.assertNotEqual(moe(MoE(seed=456))[3],moe(MoE(seed=457))[3])


class AnalysisTests(unittest.TestCase):
    def test_empty_and_corrupted_sidecar(self):
        from evaluation.analyze_traces import analyze
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'moe.csv'
            save(p,moe(MoE(tokens=0)))
            summary,jetties,_,_=analyze(p)
            self.assertEqual(summary['wr_count'],0)
            self.assertEqual(len(jetties),16)
            save(p,moe(MoE(tokens=1)))
            sidecar=Path(str(p)+'.moe.jsonl')
            entries=[json.loads(line) for line in sidecar.read_text().splitlines()]
            entries[0]['sge_lengths'][0]+=1
            sidecar.write_text(''.join(json.dumps(e)+'\n' for e in entries))
            with self.assertRaises(ValueError):analyze(p)


class CLITests(unittest.TestCase):
    def test_standalone_cli_without_systemc(self):
        with tempfile.TemporaryDirectory() as d:
            for module,args in [('synthetic',['--wr-per-jetty','5','--arrival','poisson']),
                                ('moe_dispatch',['--tokens','16','--capacity','32'])]:
                p=Path(d)/(module+'.csv')
                subprocess.run([sys.executable,'-m','workloads.generators.'+module,'--output',str(p),*args],cwd=ROOT,check=True,capture_output=True)
                subprocess.run([sys.executable,'-m','workloads.schema.validate',str(p)],cwd=ROOT,check=True,capture_output=True)


if __name__=='__main__':
    unittest.main()
