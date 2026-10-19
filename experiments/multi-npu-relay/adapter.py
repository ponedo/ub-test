"""Reuse accepted execution plans verbatim; compile only weight edges/dependencies."""
import csv,io,json,os,shutil,subprocess
from pathlib import Path

KINDS={'direct':0,'two-stage':1,'chunk-streaming':2,'multicast':3}
DEFAULT_RELAY=dict(chunk_bytes=4096,relay_min_replicas=4,relay_max_relays=8,relay_min_fanout_gain=2,force_relay=False,reorder_ns=0,slow_relay_rank=4294967295,slow_relay_ns=0)

def compile_dependencies(transfers, edges, physical, start, mode='indexed'):
    """Exact old predicates, with append-only vectors in transfer order.

    Scope 2 means all main-origin edges of the same expert/chunk, not just
    the selected relay. Do not add a group/source key absent from that predicate.
    Each task receives its own list, as with the scan implementation.
    """
    if mode not in ('indexed', 'scan'):raise ValueError('dependency mode')
    if mode == 'indexed':
        main_chunks = {}
        incoming = {}
        for y in transfers[start:]:
            incoming.setdefault(y['physical'], []).append(y['task'])
            if physical[y['source_physical']]['kind'] == 'main':
                key = (physical[y['physical']]['expert'], y['offset'], y['bytes'])
                main_chunks.setdefault(key, []).append(y['task'])
    for task in range(start,len(transfers)):
        x=transfers[task];edge=edges[task-start]
        if physical[x['source_physical']]['kind']=='main':continue
        if mode == 'indexed':
            if edge['scope'] == 2:
                key = (physical[x['physical']]['expert'], x['offset'], x['bytes'])
                x['dependencies'] = list(main_chunks.get(key, ()))
            else:
                x['dependencies'] = list(incoming.get(x['source_physical'], ()))
        elif edge['scope']==2:
            x['dependencies']=[y['task'] for y in transfers[start:] if physical[y['source_physical']]['kind']=='main' and physical[y['physical']]['expert']==physical[x['physical']]['expert'] and (y['offset'],y['bytes'])==(x['offset'],x['bytes'])]
        else:
            x['dependencies']=[y['task'] for y in transfers[start:] if y['physical']==x['source_physical']]
        if not x['dependencies']:raise ValueError('missing relay dependencies')

def emit(source,parameters,strategy,out,dependency_mode=None):
    source,out=Path(source),Path(out);out.mkdir(parents=True,exist_ok=True)
    for name in ['plan.json','assignments.csv']:shutil.copyfile(source/name,out/name)
    c=json.loads((source/'config.json').read_text());plan=json.loads((source/'plan.json').read_text())
    p=dict(DEFAULT_RELAY,**parameters);kind=KINDS[strategy]
    for key in DEFAULT_RELAY:
        if key!='force_relay' and (type(p[key]) is not int or p[key]<0):raise ValueError('relay parameter '+key)
    if not 1<=p['chunk_bytes']<=64*1024*1024 or not 1<=p['relay_max_relays']<=72 or p['reorder_ns']>100000000 or p['slow_relay_ns']>100000000 or (p['slow_relay_rank']!=4294967295 and p['slow_relay_rank']>=c['planner_input']['npus']):raise ValueError('relay parameter bounds')
    physical={x['id']:x for x in plan['physical']};order=plan.get('ordinal_physical_order',list(physical)) if kind in (1,2) else list(physical)
    runtime=c['runtime'];cut=(runtime['matrices']-1)*runtime['model_dim']*runtime['ff_dim']*runtime.get('weight_dtype_bytes',runtime['dtype_bytes'])
    if runtime['weight_size_kind']!='matrix_exact':cut=0
    import importlib.util
    spec=importlib.util.spec_from_file_location('weight_capacity',Path(__file__).with_name('capacity.py'));cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    limit=runtime.get('weight_task_limit',20000)
    if type(limit) is not int or not 0<limit<=1000000 or cap.weight_task_count(plan['physical'],strategy,runtime['weight_bytes'],p,cut)>limit:raise ValueError('weight task count bound')
    options=[p['chunk_bytes'],p['relay_min_replicas'],p['relay_max_relays'],p['relay_min_fanout_gain'],int(p['force_relay']),cut,p['reorder_ns'],p['slow_relay_rank'],p['slow_relay_ns']]
    header=[kind,runtime['weight_bytes'],c['planner_input']['npus']]+options[:6]+[len(order)]
    lines=[' '.join(map(str,header))]
    for pid in order:
        x=physical[pid];lines.append(' '.join(map(str,[pid,x['expert'],x['rank'],int(x['kind']=='replica'),x['quota'],x['weight_source_physical'],x['weight_source_rank']])))
    graph_input='\n'.join(lines)+'\n';(out/'graph-input.txt').write_text(graph_input)
    binary=os.environ.get('RELAY_GRAPH_TOOL','/tmp/ub-relay-build/graph-tool')
    graph=subprocess.check_output([binary],input=graph_input,text=True);(out/'weight-edges.csv').write_text(graph)
    edges=[{k:int(v) for k,v in row.items()} for row in csv.DictReader(io.StringIO(graph))]
    limit=c['runtime'].get('weight_task_limit',20000)
    if type(limit) is not int or not 0<limit<=1000000 or len(edges)>limit:raise ValueError('weight task count bound')
    transfers=[dict(x,source_physical=0,offset=0,dependencies=[]) for x in c['transfers'] if x['stage']!=2]
    for edge in edges:
        src,dst=physical[edge['source_physical']],physical[edge['physical']]
        transfers.append(dict(task=len(transfers),stage=2,id=dst['id'],source=src['rank'],target=dst['rank'],physical=dst['id'],bytes=edge['bytes'],source_physical=src['id'],offset=edge['offset'],dependencies=[]))
    start=2*len(c['assignments'])
    compile_dependencies(transfers, edges, physical, start, dependency_mode or os.environ.get('RELAY_DEPENDENCY_MODE', 'indexed'))
    c.update(transfers=transfers,weight_strategy=strategy,relay_parameters=p,readiness='upstream-group-chunk' if kind==2 else 'whole-expert')
    c['runtime'].update(p,weight_strategy=strategy);c['parameters'].update(p,weight_strategy=strategy)
    c.pop('multicast_groups',None)
    if kind==3:
        if c['planner_input']['npus']>64 or runtime['segment_bytes']>4096:raise ValueError('multicast dimensions/segment bound')
        groups={}
        for x in transfers[start:]:
            expert=physical[x['physical']]['expert'];g=groups.setdefault(expert,dict(group=expert+1,expert=expert,source=x['source'],members=[]))
            g['members'].append(dict(task=x['task'],target=x['target'],physical=x['physical']))
        if len(groups)>128:raise ValueError('multicast lifetime group capacity')
        c['multicast_groups']=[groups[x] for x in sorted(groups)]

    (out/'config.json').write_text(json.dumps(c,indent=2)+'\n')
    with (out/'transfers.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(transfers[0]) if transfers else ['task'],lineterminator='\n');w.writeheader()
        for row in transfers:w.writerow(dict(row,dependencies=';'.join(map(str,row['dependencies']))))
    lines=(source/'input.txt').read_text().splitlines();fields=lines[1].split();fields[6]=str(kind);lines[1]=' '.join(fields)
    lines+=[' '.join(map(str,options)),str(len(order))+' '+' '.join(map(str,order))]
    (out/'input.txt').write_text('\n'.join(lines)+'\n')
    return c,plan
