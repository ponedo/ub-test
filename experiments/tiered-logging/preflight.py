#!/usr/bin/env python3
"""Independent input/plan/graph contract checks, without simulator trace files.

Does not solve/replan, change inputs, or trust executor PASS text. The accepted
weight graph tool reconstructs the graph directly from validated plan metadata.
All assignments and quotas are compared individually, not just aggregate counts.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = ['npus','experts','top_k','tokens','model_dim','ff_dim','dtype_bytes',
        'segment_bytes','peak_gflops','util_permille','setup_ns','seed','link_gbps','link_delay_ns']
FIELDS = ['task','stage','id','source','target','physical','bytes','source_physical','offset','dependencies']
KINDS = {'direct':0,'two-stage':1,'chunk-streaming':2,'multicast':3}

def require(value, message):
    if not value:
        raise ValueError(message)

def canonical_graph(transfers):
    lines = [','.join(FIELDS)]
    for x in transfers:
        lines.append(','.join(';'.join(map(str,x[k])) if k=='dependencies' else str(x[k]) for k in FIELDS))
    return '\n'.join(lines)+'\n'

def fnv1a64(data):
    value=14695981039346656037
    for byte in data:
        value=((value ^ byte)*1099511628211)&0xffffffffffffffff
    return f'{value:016x}'

def reconstruct_dependencies(edges, byid, start, mode='indexed'):
    """Independent reconstruction from graph-tool edges and validated plan.

    Never consumes adapter dependencies. Two append-only indexes encode the
    scan predicates exactly; edge enumeration defines original task/list order.
    """
    require(mode in ('indexed', 'scan'), 'dependency mode')
    if mode == 'scan':
        result = []
        for edge in edges:
            if byid[edge['source_physical']]['kind'] == 'main':
                result.append([])
                continue
            if edge['scope'] == 2:
                deps = [start+i for i, candidate in enumerate(edges)
                        if byid[candidate['source_physical']]['kind'] == 'main'
                        and byid[candidate['physical']]['expert'] == byid[edge['physical']]['expert']
                        and (candidate['offset'], candidate['bytes']) == (edge['offset'], edge['bytes'])]
            else:
                deps = [start+i for i, candidate in enumerate(edges)
                        if candidate['physical'] == edge['source_physical']]
            require(deps, 'missing relay dependency')
            result.append(deps)
        return result
    arrivals = {}
    chunks = {}
    for ordinal, edge in enumerate(edges):
        task = start + ordinal
        arrivals.setdefault(edge['physical'], []).append(task)
        if byid[edge['source_physical']]['kind'] == 'main':
            expert = byid[edge['physical']]['expert']
            chunks.setdefault(expert, {}).setdefault((edge['offset'], edge['bytes']), []).append(task)
    result = []
    for edge in edges:
        if byid[edge['source_physical']]['kind'] == 'main':
            result.append([])
            continue
        if edge['scope'] == 2:
            expected = chunks.get(byid[edge['physical']]['expert'], {}).get((edge['offset'], edge['bytes']), ())
        else:
            expected = arrivals.get(edge['source_physical'], ())
        require(expected, 'missing relay dependency')
        result.append(list(expected))
    return result

def check(directory, graph_tool, execution_summary=None, dependency_mode='indexed'):
    root=Path(directory);c=json.loads((root/'config.json').read_text());plan=json.loads((root/'plan.json').read_text())
    pc=c['planner_input'];p=c['runtime'];n=pc['npus'];e=pc['experts'];k=pc['top_k'];mapping=pc['mapping'];physical=plan['physical'];byid={x['id']:x for x in physical}
    if 'weight_dtype_bytes' in p:
        wd=p['weight_dtype_bytes'];require(type(wd) is int and 1<=wd<=8,'weight dtype bytes')
        formula=p['matrices']*p['model_dim']*p['ff_dim']*wd
        require(p['weight_size_kind']==('matrix_exact' if p['weight_bytes']==formula else 'synthetic_override'),'weight precision formula metadata')
    budget=p.get('payload_budget_bytes',256*1024**2);limit=p.get('weight_task_limit',20000)
    require(type(budget) is int and 0<budget<=8*1024**3,'payload budget range')
    require(type(limit) is int and 0<limit<=1000000,'weight task limit range')
    logical=2*len(mapping)*k*p['model_dim']*p['dtype_bytes']+sum(x['kind']=='replica' for x in physical)*p['weight_bytes']
    require(logical<2**64 and logical<=budget,'payload safety bound')
    require(sum(x['stage']==2 for x in c['transfers'])<=limit,'weight task count bound')
    require(len(c['transfers'])<=2**31-1,'task ID/index range')
    require(sum((x['bytes']+p['segment_bytes']-1)//p['segment_bytes'] for x in c['transfers'])<=2**32-1,'logical SSN/count range')
    require(c['mode'] in ('no-balancing','ultraep'),'mode')
    require(len(byid)==len(physical),'duplicate physical ID')
    require(len({(x['rank'],x['expert']) for x in physical})==len(physical),'duplicate rank/expert')
    require(len(pc['main_placement'])==e,'main placement dimension')
    for x in range(e):
        mains=[ph for ph in physical if ph['expert']==x and ph['kind']=='main']
        require(len(mains)==1 and mains[0]['rank']==pc['main_placement'][x],'main moved or missing')
    replicas=Counter()
    for ph in physical:
        require(0<=ph['rank']<n and 0<=ph['expert']<e and type(ph['quota']) is int and ph['quota']>=0,'physical bounds/quota')
        require(ph['kind'] in ('main','replica'),'physical kind')
        source=byid[ph['weight_source_physical']]
        require(source['kind']=='main' and source['expert']==ph['expert'] and source['rank']==ph['weight_source_rank'],'weight provenance')
        if ph['kind']=='replica':replicas[ph['rank']]+=1
    require(all(replicas[r]<=pc['slots'][r] for r in range(n)),'replica slots exceeded')
    require(len(plan['token_mapping'])==len(mapping),'token mapping count')
    assignments=[];counts=Counter()
    for token,(inp,row) in enumerate(zip(mapping,plan['token_mapping'])):
        require(0<=inp['source']<n and len(inp['experts'])==k and len(set(inp['experts']))==k,'routing top-k/source')
        require(row['token']==token and row['source']==inp['source'] and row['logical_experts']==inp['experts'] and len(row['physical_experts'])==k,'routing identity')
        for rank,(expert,pid) in enumerate(zip(inp['experts'],row['physical_experts'])):
            require(0<=expert<e and byid[pid]['expert']==expert,'logical/physical expert identity')
            assignments.append(dict(assignment=len(assignments),token=token,rank=rank,expert=expert,physical=pid,source=inp['source'],target=byid[pid]['rank']))
            counts[pid]+=1
    require(assignments==c['assignments'],'config assignments differ from token/plan identity')
    require(all(counts[ph['id']]==ph['quota'] for ph in physical),'physical quota mismatch')
    if c['mode']=='ultraep':
        spec=importlib.util.spec_from_file_location('tiered_planner_checker',HERE.parents[1]/'planner/quota/checker.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.check(pc,plan)
    else:
        require(not replicas and not p['planning_ns'] and not p['reroute_ns'],'baseline replication/planning')
    kind=KINDS[c['weight_strategy']]
    order=plan.get('ordinal_physical_order',list(byid)) if kind in (1,2) else list(byid)
    require(len(order)==len(physical) and set(order)==set(byid),'physical ordinal order')
    cut=(p['matrices']-1)*p['model_dim']*p['ff_dim']*p.get('weight_dtype_bytes',p['dtype_bytes']) if p['weight_size_kind']=='matrix_exact' else 0
    opts=[p['chunk_bytes'],p['relay_min_replicas'],p['relay_max_relays'],p['relay_min_fanout_gain'],int(p['force_relay']),cut,p['reorder_ns'],p['slow_relay_rank'],p['slow_relay_ns']]
    physrow=lambda ph:[ph['id'],ph['expert'],ph['rank'],int(ph['kind']=='replica'),ph['quota'],ph['weight_source_physical'],ph['weight_source_rank']]
    head=dict(p,npus=n,experts=e,top_k=k,tokens=len(mapping))
    expected=[head[key] for key in KEYS]+[p['matrices'],p['weight_bytes'],p['planning_ns'],p['reroute_ns'],p['weight_completion_ns'],int(c['mode']=='ultraep'),kind,len(physical)]+pc['main_placement']
    for ph in physical:expected+=physrow(ph)
    for row in plan['token_mapping']:
        expected.append(row['source'])
        for expert,pid in zip(row['logical_experts'],row['physical_experts']):expected.extend((expert,pid))
    expected+=opts+[len(order)]+order
    actual=[int(x) for x in (root/'input.txt').read_text().split()]
    require(actual==expected,'input.txt differs from config/plan execution contract')
    spec=importlib.util.spec_from_file_location('weight_capacity',HERE.parent/'multi-npu-relay/capacity.py');cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    require(cap.weight_task_count(physical,c['weight_strategy'],p['weight_bytes'],c['relay_parameters'],opts[5])<=limit,'weight task count bound')
    graph_input=' '.join(map(str,[kind,p['weight_bytes'],n]+opts[:6]+[len(order)]))+'\n'
    graph_input+=''.join(' '.join(map(str,physrow(byid[pid])))+'\n' for pid in order)
    output=subprocess.run([str(graph_tool)],input=graph_input,text=True,capture_output=True,check=True).stdout
    edges=[{key:int(v) for key,v in row.items()} for row in csv.DictReader(io.StringIO(output))]
    transfers=[]
    for stage in (0,1):
        for a in assignments:
            transfers.append(dict(task=len(transfers),stage=stage,id=a['assignment'],source=a['source'] if stage==0 else a['target'],target=a['target'] if stage==0 else a['source'],physical=a['physical'],bytes=p['model_dim']*p['dtype_bytes'],source_physical=0,offset=0,dependencies=[]))
    start=len(transfers)
    for edge in edges:
        src,dst=byid[edge['source_physical']],byid[edge['physical']]
        transfers.append(dict(task=len(transfers),stage=2,id=dst['id'],source=src['rank'],target=dst['rank'],physical=dst['id'],bytes=edge['bytes'],source_physical=src['id'],offset=edge['offset'],dependencies=[]))
    require(dependency_mode in ('indexed', 'scan'), 'dependency mode')
    if dependency_mode == 'scan':
        for task in range(start,len(transfers)):
            x=transfers[task]
            if byid[x['source_physical']]['kind']=='main':continue
            if edges[task-start]['scope']==2:
                x['dependencies']=[y['task'] for y in transfers[start:] if byid[y['source_physical']]['kind']=='main' and byid[y['physical']]['expert']==byid[x['physical']]['expert'] and (y['offset'],y['bytes'])==(x['offset'],x['bytes'])]
            else:x['dependencies']=[y['task'] for y in transfers[start:] if y['physical']==x['source_physical']]
            require(x['dependencies'],'missing relay dependency')
    else:
        for x, dependencies in zip(transfers[start:], reconstruct_dependencies(edges, byid, start, dependency_mode)):
            x['dependencies'] = dependencies
    require(transfers==c['transfers'],'config transfer graph differs from accepted graph tool')
    if kind==3:
        require(n<=64 and p['segment_bytes']<=4096,'multicast supported dimensions')
        grouped={}
        for x in transfers[start:]:
            ph=byid[x['physical']];expert=ph['expert'];grouped.setdefault(expert,[]).append(dict(task=x['task'],target=ph['rank'],physical=ph['id']))
        expected_groups=[dict(group=expert+1,expert=expert,source=pc['main_placement'][expert],members=members) for expert,members in sorted(grouped.items())]
        require(len(expected_groups)<=128 and c.get('multicast_groups')==expected_groups,'multicast group membership contract')
        if execution_summary:
            actual=list(csv.DictReader((root/'multicast-groups.csv').open()));expected_rows=[]
            for g in expected_groups:
                for m in g['members']:expected_rows.append(dict(group=g['group'],expert=g['expert'],source=g['source'],**m,bytes=p['weight_bytes']))
            require(len(actual)==len(expected_rows),'executed multicast member count')
            complete={}
            summary=json.loads(Path(execution_summary).read_text());planning=summary['timeline']['planning_end']
            debug_events=list(csv.DictReader((root/'events.csv').open())) if summary.get('log_level')=='debug' else None
            for row,want in zip(actual,expected_rows):
                require(all(int(row[key])==value for key,value in want.items()),'executed multicast member identity')
                ready,sender,group_done=map(int,(row['receiver_ready_ps'],row['sender_complete_ps'],row['group_complete_ps']))
                require(planning<=ready<=sender<=group_done,'multicast receiver/sender causal order');
                if debug_events is not None:
                    for name,expected_time in [('edge_ready',ready),('sender_complete',sender)]:
                        times=[int(x['time_ps']) for x in debug_events if x['event']==name and int(x['task'])==want['task']];require(times==[expected_time],'multicast per-child event timestamp')
                complete.setdefault(want['group'],[]).append((sender,group_done))
            for members in complete.values():require(len({x[1] for x in members})==1 and max(x[0] for x in members)==members[0][1],'multicast all-target completion aggregation')
            stats=list(csv.DictReader((root/'multicast-stats.csv').open()));require(len(stats)==len(expected_groups),'multicast statistics count')
            for row,g in zip(stats,expected_groups):
                fanout=len(g['members']);size=p['weight_bytes'];seg=p['segment_bytes'];packets=(size+seg-1)//seg;header=78 if fanout==1 else 32+137*fanout
                require(int(row['envelopes'])==(packets if fanout>1 else 0),'multicast envelope count')
                require(int(row['group'])==g['group'] and int(row['source'])==g['source'] and int(row['fanout'])==fanout and int(row['payload_bytes'])==size and int(row['wire_bytes'])==size+packets*header,'multicast source bytes/fanout')
            summary=json.loads(Path(execution_summary).read_text());require(max((int(x['receiver_ready_ps']) for x in actual),default=summary['timeline']['planning_end'])==summary['timeline']['weights_end'],'multicast weight ready must use receiver completion')
    canonical=canonical_graph(transfers).encode()
    if (root/'executed-transfers.csv').exists():
        require((root/'executed-transfers.csv').read_bytes()==canonical,'actual executed transfer graph mismatch')
    if execution_summary:
        summary=json.loads(Path(execution_summary).read_text())
        require(summary['executed_graph_fnv1a64']==fnv1a64(canonical),'executed graph fingerprint mismatch')
    return dict(status='PASS',tokens=len(mapping),assignments=len(assignments),physical_experts=len(physical),replicas=sum(replicas.values()),transfers=len(transfers),input_sha256=hashlib.sha256((root/'input.txt').read_bytes()).hexdigest(),executed_graph_sha256=hashlib.sha256(canonical).hexdigest(),executed_graph_fnv1a64=fnv1a64(canonical),checks=['individual routing/physical identity','all physical quotas','main placement and weight provenance','replica slot budgets','accepted planner independent checker (UltraEP)','complete integer execution input contract','native weight graph and dependency reconstruction','executed graph when supplied'])

def input_summary(directory, validation, provenance=None):
    root=Path(directory);c=json.loads((root/'config.json').read_text());plan=json.loads((root/'plan.json').read_text())
    pc=c['planner_input'];physical=plan['physical'];loads=[sum(ph['quota'] for ph in physical if ph['rank']==r) for r in range(pc['npus'])]
    expert=[sum(ph['quota'] for ph in physical if ph['expert']==e) for e in range(pc['experts'])]
    jain=lambda values: sum(values)**2/(len(values)*sum(v*v for v in values)) if any(values) else 1.0
    metadata=json.loads(Path(provenance).read_text()) if provenance else {}
    # Do not guess routing RNG seed from payload seed. Existing arbitrary fixtures
    # need not have a stochastic generator; absent provenance is explicitly null.
    return dict(schema_version=1,mode=c['mode'],strategy=c['weight_strategy'],topology='single-switch',npus=pc['npus'],ep_degree=pc['npus'],experts=pc['experts'],top_k=pc['top_k'],tokens=len(pc['mapping']),runtime=c['runtime'],planner_parameters={key:value for key,value in pc.items() if key!='mapping'},physical=physical,replicas=sum(x['kind']=='replica' for x in physical),per_npu_load=loads,max_npu_assignment_load=max(loads,default=0),npu_load_jain=jain(loads),expert_load=expert,expert_load_jain=jain(expert),routing_seed=metadata.get('routing_seed'),popularity=metadata.get('popularity'),versions={key:value for key,value in metadata.items() if 'commit' in key or 'tree' in key},input_hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('input.txt','config.json','plan.json')},validation=validation)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--graph-tool',type=Path,required=True);parser.add_argument('--execution-summary',type=Path);parser.add_argument('--out',type=Path);parser.add_argument('--input-summary',type=Path);parser.add_argument('--provenance',type=Path)
    parser.add_argument('--dependency-mode', choices=('indexed', 'scan'), default='indexed')
    args=parser.parse_args()
    try:result=check(args.directory,args.graph_tool,args.execution_summary,args.dependency_mode)
    except Exception as exc:
        result=dict(status='FAIL',error=str(exc))
        if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),file=sys.stderr);return 2
    if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
    if args.input_summary:args.input_summary.write_text(json.dumps(input_summary(args.directory,result,args.provenance),indent=2)+'\n')
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':sys.exit(main())
