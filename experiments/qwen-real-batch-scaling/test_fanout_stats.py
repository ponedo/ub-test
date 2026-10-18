import os
import copy
import csv
import io
import random
import subprocess
import unittest
from pathlib import Path
from fanout_stats import audit, eligibility, expected_graph

HERE = Path(__file__).parent


def case(counts=(4,), strategy='chunk-streaming', force=False):
    p = dict(weight_bytes=101, chunk_bytes=17, segment_bytes=8, matrices=3, model_dim=1, ff_dim=1, dtype_bytes=1, weight_size_kind='synthetic_override', relay_min_replicas=4, relay_max_relays=8, relay_min_fanout_gain=2, force_relay=force)
    rows=[]
    for e, count in enumerate(counts):
        mid=len(rows); rank=e%16
        rows.append(dict(id=mid, expert=e, rank=rank, kind='main', quota=1, weight_source_physical=mid, weight_source_rank=rank))
        for j in range(count):
            rows.append(dict(id=len(rows), expert=e, rank=(rank+j+1)%16 if (rank+j+1)%16 != rank else (rank+1)%16, kind='replica', quota=1, weight_source_physical=mid, weight_source_rank=rank))
    plan=dict(physical=rows, ordinal_physical_order=[x['id'] for x in rows])
    return dict(runtime=p, planner_input=dict(npus=16), weight_strategy=strategy, transfers=[]), plan


def native(c, plan):
    p=c['runtime']; kind={'direct':0,'two-stage':1,'chunk-streaming':2}[c['weight_strategy']]
    cut=(p['matrices']-1)*p['model_dim']*p['ff_dim']*p.get('weight_dtype_bytes',p['dtype_bytes']) if p['weight_size_kind']=='matrix_exact' else 0
    order=plan['ordinal_physical_order'] if kind else [x['id'] for x in plan['physical']]
    byid={x['id']:x for x in plan['physical']}
    head=[kind,p['weight_bytes'],c['planner_input']['npus'],p['chunk_bytes'],p['relay_min_replicas'],p['relay_max_relays'],p['relay_min_fanout_gain'],int(p['force_relay']),cut,len(order)]
    lines=[' '.join(map(str,head))]
    for pid in order:
        x=byid[pid]; lines.append(' '.join(map(str,[pid,x['expert'],x['rank'],int(x['kind']=='replica'),x['quota'],x['weight_source_physical'],x['weight_source_rank']])))
    output=subprocess.check_output([os.environ.get('RELAY_GRAPH_TOOL',str(HERE/'graph-tool'))],input='\n'.join(lines)+'\n',text=True)
    return [{k:int(v) for k,v in x.items()} for x in csv.DictReader(io.StringIO(output))]


def add_transfers(c, plan, edges):
    byid={x['id']:x for x in plan['physical']}
    ts=[]
    for i,x in enumerate(edges):
        ts.append(dict(task=i,stage=2,source_physical=x['source_physical'],physical=x['physical'],offset=x['offset'],bytes=x['bytes'],source=byid[x['source_physical']]['rank'],target=byid[x['physical']]['rank'],dependencies=[]))
    for t,x in zip(ts,edges):
        if byid[t['source_physical']]['kind']=='main':continue
        if x['scope']==2:
            t['dependencies']=[y['task'] for y in ts if byid[y['source_physical']]['kind']=='main' and byid[y['physical']]['expert']==byid[t['physical']]['expert'] and (y['offset'],y['bytes'])==(t['offset'],t['bytes'])]
        else:t['dependencies']=[y['task'] for y in ts if y['physical']==t['source_physical']]
    c['transfers']=ts


class Tests(unittest.TestCase):
    def test_thresholds(self):
        c,_=case();p=c['runtime']
        self.assertEqual([eligibility(r,p)['eligible'] for r in range(6)],[False,False,False,False,True,True])
        p['force_relay']=True
        self.assertEqual([eligibility(r,p)['eligible'] for r in range(4)],[False,False,True,True])
        p['force_relay']=False;p['relay_min_fanout_gain']=3
        self.assertFalse(eligibility(4,p)['eligible'])
    def test_native_graphs(self):
        rng=random.Random(523)
        for i in range(120):
            c,plan=case(tuple(rng.randrange(0,19) for _ in range(4)),['direct','two-stage','chunk-streaming'][i%3],i%5==0)
            rng.shuffle(plan['ordinal_physical_order'])
            c['runtime']['relay_max_relays']=1+i%8
            c['runtime']['relay_min_fanout_gain']=i%5
            if i%2:
                c['runtime'].update(weight_size_kind='matrix_exact',weight_bytes=120,model_dim=4,ff_dim=5,weight_dtype_bytes=2)
            edges=native(c,plan);add_transfers(c,plan,edges)
            result=audit(c,plan,edges)
            self.assertEqual(result['totals']['weight_tasks'],len(edges))
            self.assertEqual(result['totals']['weight_bytes'],sum(x['kind']=='replica' for x in plan['physical'])*c['runtime']['weight_bytes'])
    def test_counts(self):
        c,plan=case((3,4));edges=native(c,plan);add_transfers(c,plan,edges);r=audit(c,plan,edges)
        self.assertEqual(r['totals']['physical_instances_including_main'],9)
        self.assertEqual(r['totals']['new_replicas_excluding_main'],7)
        self.assertEqual(r['totals']['eligible_experts'],1)
        self.assertEqual(r['totals']['actual_relay_experts'],1)
        self.assertEqual(r['totals']['main_outgoing_copies'],5)
        self.assertEqual(r['totals']['forwarded_tasks'],12)
        self.assertEqual(r['totals']['weight_tasks'],27)
        self.assertEqual(r['totals']['weight_tas'],107)
    def test_eligible_not_actual_direct(self):
        c,plan=case(strategy='direct');edges=native(c,plan);add_transfers(c,plan,edges);r=audit(c,plan,edges)
        self.assertEqual(r['totals']['eligible_experts'],1);self.assertEqual(r['totals']['actual_relay_experts'],0)
    def test_mutations_rejected(self):
        c,plan=case();edges=native(c,plan);add_transfers(c,plan,edges)
        for field in ('source_physical','physical','offset','bytes','scope'):
            bad=copy.deepcopy(edges);bad[-1][field]+=100
            with self.assertRaises(ValueError):audit(c,plan,bad)
        for bad in (edges[:-1],edges+[edges[0]],list(reversed(edges))):
            with self.assertRaises(ValueError):audit(c,plan,bad)
        c['transfers'][-1]['dependencies']=[]
        with self.assertRaises(ValueError):audit(c,plan,edges)
    def test_invalid_graph_inputs(self):
        for field,value in [('chunk_bytes',0),('relay_max_relays',0),('domain',[0,1])]:
            c,plan=case();c['runtime'][field]=value
            with self.assertRaises(ValueError):expected_graph(c,plan)
        c,plan=case();plan['physical'][-1]['weight_source_rank']=15
        with self.assertRaises(ValueError):expected_graph(c,plan)

if __name__=='__main__':unittest.main()
