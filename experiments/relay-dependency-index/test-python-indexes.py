#!/usr/bin/env python3
"""Independent scan/index equality, ordering, isolation and tamper regressions."""
import argparse, copy, hashlib, importlib.util, json, random, shutil, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
adapter=load('adapter_under_test',ROOT/'experiments/multi-npu-relay/adapter.py')
preflight=load('preflight_under_test',ROOT/'experiments/tiered-logging/preflight.py')
def run_random():
    rng=random.Random(20261017); checked=0; rejected=0
    for trial in range(160):
        physical={i:dict(id=i,expert=i//6,kind='main' if i%6==0 else 'replica',rank=i) for i in range(18)}
        edges=[]
        # Interleaved experts, repeated chunks, distinct same-offset lengths, and
        # duplicate edges stress exact keys and preserve multiplicity and order.
        for i in range(rng.randrange(0,90)):
            expert=rng.randrange(3); dst=expert*6+rng.randrange(1,6)
            src=expert*6 if rng.random()<.6 else expert*6+rng.randrange(1,6)
            edges.append(dict(physical=dst,source_physical=src,offset=rng.choice([0,4,8]),bytes=rng.choice([1,3,4]),scope=rng.choice([0,1,2])))
        if trial < 80:
            # Guaranteed valid trials exercise complete vectors rather than only
            # failure parity: every replica/chunk has main-origin arrivals.
            edges += [dict(physical=expert*6+replica,source_physical=expert*6,
                           offset=offset,bytes=size,scope=2)
                      for expert in range(3) for replica in range(1,6)
                      for offset in (0,4,8) for size in (1,3,4)]
        rng.shuffle(edges); start=rng.randrange(0,20)
        base=[dict(task=i,dependencies=[]) for i in range(start)]
        base += [dict(edge,task=start+i,dependencies=[]) for i,edge in enumerate(edges)]
        outcomes=[]
        for mode in ('scan','indexed'):
            transfers=copy.deepcopy(base)
            try:adapter.compile_dependencies(transfers,edges,physical,start,mode); outcomes.append([x['dependencies'] for x in transfers[start:]])
            except ValueError:outcomes.append('missing')
            try:outcomes.append(preflight.reconstruct_dependencies(edges,physical,start,mode))
            except ValueError:outcomes.append('missing')
        assert all(x==outcomes[0] for x in outcomes), trial
        rejected+=outcomes[0]=='missing';checked+=1
    # Non-monotonic task IDs prove the adapter preserves list order, not sorting.
    ph={0:dict(kind='main',expert=7),1:dict(kind='replica',expert=7),2:dict(kind='replica',expert=7)}
    edges=[dict(source_physical=0,physical=1,offset=0,bytes=3,scope=2),dict(source_physical=0,physical=2,offset=0,bytes=3,scope=2),dict(source_physical=1,physical=2,offset=0,bytes=3,scope=2),dict(source_physical=1,physical=2,offset=0,bytes=3,scope=2)]
    transfers=[dict(e,task=t,dependencies=[]) for e,t in zip(edges,[11,4,9,2])]
    adapter.compile_dependencies(transfers,edges,ph,0)
    assert transfers[2]['dependencies']==[11,4]
    transfers[2]['dependencies'].append(99)
    assert transfers[3]['dependencies']==[11,4], 'dependency lists aliased'
    return dict(cases=checked,missing_dependency_cases=rejected,order_and_list_isolation='PASS')
def run_fixture(case, tool):
    results=[]
    for mode in ('scan','indexed'):
        result=preflight.check(case,tool,dependency_mode=mode)
        results.append(dict(mode=mode,graph_sha256=result['executed_graph_sha256']))
    assert results[0]['graph_sha256']==results[1]['graph_sha256']
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        for name in ('input.txt','plan.json'):shutil.copyfile(case/name,root/name)
        original=json.loads((case/'config.json').read_text())
        withdeps=[i for i,x in enumerate(original['transfers']) if len(x['dependencies'])>1]
        assert withdeps, 'fixture must cover multi-dependency ordering'
        for fault in ('missing-dependency','duplicate-dependency','dependency-order','wrong-group','wrong-offset','wrong-length','source','target','missing-transfer','transfer-order','physical-expert','replica-kind','group-parameters'):
            c=copy.deepcopy(original);i=withdeps[0];x=c['transfers'][i]
            if fault=='missing-dependency':x['dependencies'].pop()
            elif fault=='duplicate-dependency':x['dependencies'].append(x['dependencies'][0])
            elif fault=='dependency-order':x['dependencies'].reverse()
            elif fault=='wrong-group':x['dependencies'][0]=0
            elif fault=='wrong-offset':x['offset']+=1
            elif fault=='wrong-length':x['bytes']+=1
            elif fault=='source':x['source']=(x['source']+1)%c['planner_input']['npus']
            elif fault=='target':x['target']=(x['target']+1)%c['planner_input']['npus']
            elif fault=='missing-transfer':c['transfers'].pop(i)
            elif fault=='transfer-order':c['transfers'][i],c['transfers'][i+1]=c['transfers'][i+1],c['transfers'][i]
            elif fault=='group-parameters':c['runtime']['relay_max_relays']+=1
            else:
                plan=json.loads((case/'plan.json').read_text());pid=x['source_physical'];p=next(p for p in plan['physical'] if p['id']==pid)
                if fault=='physical-expert':p['expert']=(p['expert']+1)%c['planner_input']['experts']
                else:p['kind']='main'
                (root/'plan.json').write_text(json.dumps(plan))
            (root/'config.json').write_text(json.dumps(c))
            for mode in ('scan','indexed'):
                try:preflight.check(root,tool,dependency_mode=mode)
                except (ValueError,KeyError):pass
                else:raise AssertionError((fault,mode,'accepted'))
            shutil.copyfile(case/'plan.json',root/'plan.json')
            results.append(dict(fault=fault,status='REJECTED_BOTH'))
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args()
    result=dict(status='PASS',random=run_random(),fixture=run_fixture(a.case,a.graph_tool))
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
