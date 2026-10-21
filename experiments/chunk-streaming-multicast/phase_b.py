#!/usr/bin/env python3
"""Prepare an immutable, gated, sequential Phase B. Never build or silently rerun."""
import argparse
import csv
import os
import shutil
import types
from collections import Counter, defaultdict
from common import *
import adapter
import fixtures
import preflight


def csv_rows(root,name):
    with (Path(root)/name).open() as stream:return list(csv.DictReader(stream))


def require_no_success(directory, allow_missing_failure=False):
    path=Path(directory)/'validation.json'
    require((allow_missing_failure and not path.exists()) or (path.is_file() and read(path).get('status')=='FAIL'),'Expected rejection lacks explicit failure artifact')
    for name in ('online-summary.json','hybrid-summary.json','hybrid-lifecycle.json'):
        path=Path(directory)/name
        require(not path.exists() or read(path).get('status')!='PASS','Rejected case left a false success artifact: '+name)


def accepted_rejection(result, console, expected_error, allow_payload_abort=False):
    require(result['guard'] is None, 'Resource kill is not an expected rejection')
    if result['returncode'] == 2 and 'ERROR: '+expected_error in console:
        return expected_error
    if allow_payload_abort and result['returncode'] == -6 and 'hybrid same-range native payload differs' in console:
        return 'hybrid same-range native payload differs'
    raise ValueError('Not the exact expected application rejection: '+expected_error)


def negative_stage(command,out,identity,expected_error,allow_payload_abort=False):
    """Same accepted limits as successful runs; crash/timeout is not a rejection."""
    out=Path(out);require(not out.exists(),'No implicit restart: '+str(out));check(identity)
    guard=load('phase_b_negative_guard',E/'cloudmatrix-bandwidth/guard.py')
    heartbeat=load('phase_b_heartbeat',E/'multicast-token-screening/heartbeat.py').Heartbeat(out,command)
    heartbeat.start(); original=guard.m.time; result=None
    def sleep(seconds):original.sleep(seconds);heartbeat.tick()
    guard.m.time=types.SimpleNamespace(monotonic=original.monotonic,sleep=sleep)
    try:result=guard.run(command,out,wall=4800,case=out.parent,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    finally:
        guard.m.time=original
        heartbeat.stop(result['status'] if result else 'STOPPED_OR_UNCERTAIN')
    require(heartbeat.error is None,'Heartbeat failed')
    check(identity)
    result['expected_rejection']=accepted_rejection(result,(out/'console.txt').read_text(),expected_error,allow_payload_abort)
    return result


def copy_inputs(source,dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    for name in INPUTS:shutil.copyfile(Path(source)/name,dest/name)


def prepare(args):
    out=args.out.resolve();require(not out.exists(),'Fresh Phase B preparation required')
    require(sha(args.accepted_binary)==fixtures.ACCEPTED_BINARY_SHA256,'Not the exact accepted token-screen binary')
    identity=read(args.runtime_identity);check(identity)
    accepted=read(args.accepted_identity);check(accepted)
    require(str(args.accepted_binary.resolve()) in accepted,'Accepted binary not identity-pinned')
    require(str(args.binary.resolve()) in identity and str(args.graph_tool.resolve()) in identity,'Candidate binary/graph tool not pinned')
    # Shared library closure must be the SAME accepted native build. Refuse merely
    # matching filenames, an independently rebuilt protocol, or omitted libraries.
    native={k:v for k,v in accepted.items() if '/build/lib/' in k}
    require(native and all(identity.get(k)==v for k,v in native.items()),'Candidate/accepted loaded native library closure differs')
    identity.update(accepted);identity.update(freeze([args.runtime_identity,args.accepted_identity]))
    # Bind the actual Python oracle/adapter/guard/heartbeat closure, including
    # files not yet present when the C++-only build identity was prepared.
    harness=[path for directory in (E,E.parent/'planner') for path in directory.rglob('*.py') if '__pycache__' not in path.parts]
    harness.extend(H.glob('*.md'))
    identity.update(freeze(harness))
    resource_admission(out.parent);out.mkdir(parents=True)
    declaration=fixtures.matrix();write(out/'fixture-manifest.json',declaration)
    base=load('phase_b_accepted_direct',E/'direct-weight-forward/adapter.py')
    os.environ['RELAY_GRAPH_TOOL']=str(args.graph_tool.resolve())
    prepared={};topologies={}
    for name,spec in declaration['fixtures'].items():
        root=out/'fixtures'/name
        base.emit(spec['planner_input'],spec['model'],'ultraep',root/'balanced-base')
        adapter.emit(root/'balanced-base',spec['relay'],'chunk-streaming',root/'chunk-streaming')
        c,plan=adapter.from_cs_control(root/'chunk-streaming',root/HYBRID)
        topologies[name]=fixtures.inspect_topology(c,plan,spec['topology'])
        prepared[name,HYBRID]=root/HYBRID;prepared[name,'chunk-streaming']=root/'chunk-streaming'
        for mode in fixtures.OLD_MODES if name in fixtures.REGRESSION_FIXTURES else ():
            if mode!='chunk-streaming':adapter.emit(root/'balanced-base',spec['relay'],mode,root/mode)
            prepared[name,mode]=root/mode
        for mode in (HYBRID,)+ (fixtures.OLD_MODES if name in fixtures.REGRESSION_FIXTURES else ('chunk-streaming',)):
            path=prepared[name,mode]
            result=preflight.check_directory(path,args.graph_tool,root/'chunk-streaming' if mode==HYBRID else None)
            write(path/'preflight.json',result)
    records=[];all_inputs=[]
    for spec in declaration['rows']:
        row=dict(spec);row['executions']=[]
        for variant in spec.get('executables',['candidate']):
            directory=out/'runs'/spec['id']/variant
            copy_inputs(prepared[spec['fixture'],spec['strategy']],directory)
            binary=args.accepted_binary if variant=='accepted' else args.binary
            extra=['--logLevel='+spec['log_level']]+spec['options']
            command=simulator(binary.resolve(),directory,spec['strategy'],extra)
            require(not any(x=='--logLevel=debug' for x in command),'Full Debug forbidden')
            all_inputs.extend(directory/name for name in INPUTS)
            row['executions'].append(dict(variant=variant,directory=str(directory),command=command))
        row['cs_control']=str(prepared[spec['fixture'],'chunk-streaming'])
        records.append(row)
    for path in (out/'fixtures').rglob('*'):
        if path.is_file():all_inputs.append(path)
    identity.update(freeze(all_inputs+[out/'fixture-manifest.json']))
    write(out/'immutable-identity.json',identity)
    manifest=dict(status='PREPARED',phase='B',base=BASE,fixture_manifest_sha256=sha(out/'fixture-manifest.json'),
        runtime_identity_sha256=sha(args.runtime_identity),immutable_identity_sha256=sha(out/'immutable-identity.json'),
        graph_tool=str(args.graph_tool.resolve()),candidate_binary=str(args.binary.resolve()),
        accepted_binary=str(args.accepted_binary.resolve()),topology=topologies,rows=records,
        budget=fixtures.BUDGET,coverage=fixtures.COVERAGE,unsupported=fixtures.UNSUPPORTED)
    write(out/'prepared-manifest.json',manifest)
    write(out/'ledger.json',dict(status='PREPARED',rows=[]))
    print('PREPARED Phase B; zero simulations. Explicit approval must bind '+sha(out/'prepared-manifest.json'))


def parity(accepted,candidate):
    left,right=read(Path(accepted)/'online-summary.json'),read(Path(candidate)/'online-summary.json')
    for key in fixtures.PARITY_FIELDS:require(left[key]==right[key],'Old-mode exact parity changed: '+key)
    compared=[]
    for name in fixtures.PARITY_FILES:
        a,b=Path(accepted)/name,Path(candidate)/name
        require(a.is_file() and b.is_file(),'Old-mode deterministic artifact missing: '+name)
        require(a.read_bytes()==b.read_bytes(),'Old-mode deterministic artifact drift: '+name)
        compared.append(name)
    for name in INPUTS:require((Path(accepted)/name).read_bytes()==(Path(candidate)/name).read_bytes(),'Old-mode input identity: '+name)
    return dict(status='PASS',fields=list(fixtures.PARITY_FIELDS),byte_identical_files=compared)


def early_group_witness(directory):
    c=read(Path(directory)/'config.json');events=csv_rows(directory,'events.csv')
    attempt=[r for r in events if r['event']=='early_group_attempt'];require(len(attempt)==1,'Missing unique early-group attempt')
    child=c['transfers'][int(attempt[0]['task'])]
    ready={int(r['task']) for r in events if r['event']=='edge_ready' and int(r['time_ps'])<=int(attempt[0]['time_ps'])}
    own=[task for task in child['dependencies'] if c['transfers'][task]['physical']==child['source_physical']]
    require(own and all(task in ready for task in own) and any(task not in ready for task in child['dependencies']),
            'Early-group rejection did not distinguish own-ready from all-main ready')


def aggregate_coverage(rows,required=None):
    required=fixtures.COVERAGE if required is None else required
    found={key for row in rows for key,value in row.get('coverage',{}).items() if value is True}
    missing={category:[key for key in keys if key not in found] for category,keys in required.items()}
    missing={category:keys for category,keys in missing.items() if keys}
    return dict(status='INCOMPLETE' if missing else 'PASS',demonstrated=sorted(found),missing=missing)


def run(args):
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out=args.out.resolve();manifest=read(out/'prepared-manifest.json');ledger=read(out/'ledger.json')
    require(ledger['status'] in ('PREPARED','PAUSED'),'No implicit resume or rerun')
    approval=read(args.approval)
    require(approval.get('status')=='PASS' and approval.get('approved_to_run') is True and approval.get('phase')=='B','Explicit Phase B run approval missing')
    require(approval.get('prepared_manifest_sha256')==sha(out/'prepared-manifest.json'),'Approval does not bind exact Phase B manifest')
    if ledger['status']=='PAUSED':
        require(approval.get('approved_to_continue') is True and approval.get('prior_ledger_sha256')==sha(out/'ledger.json'),'Explicit reviewed prefix continuation missing')
    completed=[row['id'] for row in ledger['rows']]
    all_ids=[row['id'] for row in manifest['rows']]
    require(completed==all_ids[:len(completed)],'Completed rows are not the declared prefix')
    remaining=manifest['rows'][len(completed):]
    approved=approval.get('row_ids',[row['id'] for row in remaining])
    require(approved and approved==[row['id'] for row in remaining[:len(approved)]],'Approval must select the next declared row prefix, not rerun/reorder')
    selected=remaining[:len(approved)]
    prior_result=read(out/'phase-b.json') if ledger['status']=='PAUSED' else None
    require(manifest['immutable_identity_sha256']==sha(out/'immutable-identity.json'),'Phase B identity drift')
    identity=read(out/'immutable-identity.json');identity.update(freeze([out/'prepared-manifest.json',out/'immutable-identity.json',args.approval]));check(identity)
    resource_admission(out,simulation=True)
    ledger['status']='RUNNING';write(out/'ledger.json',ledger)
    regression=read(out/'old-mode-regression.json')['rows'] if (out/'old-mode-regression.json').exists() else []
    result=prior_result or dict(status='RUNNING',phase='B',rows=[],coverage={},unsupported=fixtures.UNSUPPORTED)
    result['status']='RUNNING'
    try:
        for row in selected:
            record=dict(id=row['id'],kind=row['kind'],fixture=row['fixture'],strategy=row['strategy'],status='RUNNING',coverage={})
            result['rows'].append(record);write(out/'phase-b.json',result)
            for execution in row['executions']:
                directory=Path(execution['directory']);resource_admission(out,simulation=True)
                if row['kind']=='negative':
                    record['host']=negative_stage(execution['command'],directory/'simulator-host',identity,row['expected_error'],allow_payload_abort=row['id']=='N02')
                    require_no_success(directory,allow_missing_failure=record['host']['returncode']==-6)
                    if '--fault=early-group' in row['options']:early_group_witness(directory)
                else:
                    stage(execution['command'],directory/'simulator-host',identity)
                    post=preflight.check_directory(directory,Path(manifest['graph_tool']),Path(row['cs_control']) if row['strategy']==HYBRID else None,directory/'online-summary.json')
                    write(directory/'postflight.json',post)
                    command=[sys.executable,str(H/'verify.py'),str(directory),'--out',str(directory/'independent.json')]
                    if row['kind']=='fault':command.append('--fault')
                    stage(command,directory/'independent-host',identity)
                    if row['strategy']==HYBRID:
                        record['coverage'].update(live_witnesses(directory,row))
                        absent=[key for key in row['required_witnesses'] if record['coverage'].get(key) is not True]
                        require(not absent,'Required live witness absent, not PASS: '+','.join(absent))
            if row['id']=='B04':
                record['verifier_mutations']=verifier_mutations(Path(row['executions'][0]['directory']),row)
            if row['id']=='B11':
                reference=out/'runs'/'B04'/'candidate'
                record['duplicate_notify_exact_parity']=parity(reference,Path(row['executions'][0]['directory']))
            if row['kind']=='regression':
                comparison=parity(row['executions'][0]['directory'],row['executions'][1]['directory'])
                regression.append(dict(id=row['id'],**comparison))
                write(out/'old-mode-regression.json',dict(status='PASS' if len(regression)==12 else 'INCOMPLETE',rows=regression))
            record['status']='PASS';ledger['rows'].append(dict(id=row['id'],status='PASS'));write(out/'ledger.json',ledger)
            write(out/'phase-b.json',result)
        if len(selected)<len(remaining):
            result['coverage']=aggregate_coverage(result['rows']);result['status']='INCOMPLETE';ledger['status']='PAUSED'
            result['next_row']=remaining[len(selected)]['id']
            print('Approved Phase B prefix passed; new exact-ledger approval required for '+result['next_row'])
            return
        result.pop('next_row',None)
        if len(regression)==12:result['rows'].append(dict(id='R-coverage',status='PASS',coverage={'original_four_strategy_parity':True}))
        result['coverage']=aggregate_coverage(result['rows']);require(result['coverage']['status']=='PASS','Phase B required runtime coverage missing: '+str(result['coverage']['missing']))
        result['status']='PASS';ledger['status']='PASS'
    except BaseException as exc:
        result['status']='STOPPED';result['error']=str(exc);result['coverage']=aggregate_coverage(result['rows'])
        ledger['status']='STOPPED';ledger['reason']=str(exc)
        if result['rows'] and result['rows'][-1].get('status')=='RUNNING':result['rows'][-1]['status']='FAIL'
        raise
    finally:
        write(out/'phase-b.json',result);write(out/'ledger.json',ledger)
    print('PASS Phase B: actual coverage plus exact original four-strategy parity')


def first_send_contract(groups, events, segment):
    """Validate complete real-dequeue partition; also unit-testable with fabricated rows.

    A pure unit fixture only tests this checker, never claims runtime coverage.
    """
    by_group={g['group']:g for g in groups};segments=defaultdict(list);modes=defaultdict(dict);sequences=defaultdict(list)
    for row in events:
        kind=row['kind']
        if kind=='retry':continue
        require(kind in ('envelope','native_first'),'Unknown first-send trace kind')
        ident=int(row['group']);require(ident in by_group,'Unknown first-send group')
        group=by_group[ident];off,length=int(row['offset']),int(row['bytes'])
        require(0<=off<group['bytes'] and length==min(segment,group['bytes']-off),'First-send wrong TA range')
        members={m['task'] for m in group['members']};task=int(row['task'])
        require(task in members,'First-send cross-group/expert task')
        targets=members if kind=='envelope' else {task}
        require(kind!='envelope' or len(members)>1,'Singleton envelope')
        for target in targets:segments[ident,target].append((off,length))
        mode='E' if kind=='envelope' else 'U'
        require(off not in modes[ident] or modes[ident][off]==mode,'Envelope and unicast duplicate the same offset')
        modes[ident][off]=mode
        if kind=='envelope':sequences[ident].append(int(row['sequence']))
    for group in groups:
        for member in group['members']:
            offset=0
            for start,length in sorted(segments[group['group'],member['task']]):
                require(start==offset,'Missing/duplicate/overlapping actual first-send coverage');offset+=length
            require(offset==group['bytes'],'Incomplete actual member first-send coverage')
        seq=sequences[group['group']];require(seq==list(range(len(seq))),'Envelope sequence must advance only on actual envelopes')
    patterns=[''.join(mode for _,mode in sorted(offsets.items())) for offsets in modes.values()]
    return dict(first_unicast_then_merge=any('E' in p and p.startswith('U') for p in patterns),
                envelope_unicast_envelope=any('U' in p and 'E' in p[:p.index('U')] and 'E' in p[p.index('U')+1:] for p in patterns))


def ordered_route(physical, task, source, target, switch, *, kind='native_write', after=-1, psn=None, offset=None):
    selected=[r for r in physical if r['kind']==kind and int(r['task'])==task and int(r['time_ps'])>=after
              and (psn is None or int(r['psn'])==psn) and (offset is None or int(r['offset'])==offset)]
    # Each native packet instance must traverse both actual links/queues. UID
    # survives native Packet::Copy; never join four unrelated transmissions.
    by_uid=defaultdict(list)
    for r in selected:by_uid[r['uid']].append(r)
    for packets in by_uid.values():
        previous=after;found=[]
        for event,node,port in [('tx_start',source,0),('rx',switch,source),('tx_start',switch,target),('rx',target,0)]:
            times=[int(r['time_ps']) for r in packets if r['event']==event and int(r['node'])==node and int(r['port'])==port and int(r['time_ps'])>=previous]
            if not times:break
            previous=min(times);found.append(previous)
        if len(found)==4:return found
    return None


def trace_witnesses(directory,c,life):
    events=csv_rows(directory,'hybrid-events.csv');physical=csv_rows(directory,'hybrid-physical.csv')
    require(len(events)+len(physical)<=131072,'Bounded hybrid trace capacity')
    coverage=first_send_contract(c['hybrid_groups'],events,c['runtime']['segment_bytes'])
    groups={g['group']:g for g in c['hybrid_groups']};n=c['planner_input']['npus']
    # Actual first-send envelope must cross the source link and generate every
    # fixed target branch on the switch link, with the same exact local range.
    for event in events:
        if event['kind']!='envelope':continue
        group=groups[int(event['group'])];seq=int(event['sequence']);off=int(event['offset'])
        envelopes=[p for p in physical if p['kind']=='envelope' and int(p['group'])==group['group'] and int(p['sequence'])==seq]
        tx=[p for p in envelopes if p['event']=='tx_start' and int(p['node'])==group['source'] and int(p['port'])==0]
        rx=[p for p in envelopes if p['event']=='rx' and int(p['node'])==n and int(p['port'])==group['source']]
        require(len(tx)==len(rx)==1 and tx[0]['uid']==rx[0]['uid'] and int(tx[0]['time_ps'])<=int(rx[0]['time_ps']),'Missing real source envelope TX/RX')
        require(all(int(p['offset'])==off and int(p['payload_bytes'])==int(event['bytes']) for p in tx+rx),'Actual envelope range identity')
        for member in group['members']:
            branches=[p for p in physical if p['kind']=='native_write' and int(p['task'])==member['task'] and int(p['offset'])==off and int(p['time_ps'])>=int(rx[0]['time_ps'])]
            sent=[p for p in branches if p['event']=='tx_start' and int(p['node'])==n and int(p['port'])==member['target']]
            require(sent,'Envelope missing switch native branch')
            require(any(p['event']=='rx' and int(p['node'])==member['target'] and p['uid']==sent[0]['uid'] and int(p['time_ps'])>=int(sent[0]['time_ps']) for p in branches),'Envelope branch missing target physical RX')
    # A physical streaming witness needs the final full-expert RECEIVE, not
    # merely delayed application readiness or a native-pop timestamp.
    actual={int(r['task']):r for r in csv_rows(directory,'hybrid-groups.csv')}
    streaming=[];group_wait=[]
    for group in groups.values():
        if group['graph_role']!='stage2':continue
        parent_times=[int(actual[t]['receiver_ready_ps']) for t in group['dependencies']]
        own=[t for t in group['dependencies'] if c['transfers'][t]['physical']==group['source_physical']]
        require(own,'Stage II lacks its own parent')
        own_ready=max(int(actual[t]['receiver_ready_ps']) for t in own);group_ready=max(parent_times)
        sent=min(int(actual[m['task']]['logical_ready_ps']) for m in group['members'])
        require(sent==group_ready,'Changed all-main GroupChunk readiness')
        if own_ready<group_ready:group_wait.append(dict(group=group['group'],own_ready_ps=own_ready,all_parent_ready_ps=group_ready))
        if group['offset']!=0:continue
        incoming={x['task'] for x in c['transfers'] if x['stage']==2 and x['physical']==group['source_physical']}
        received=[p for p in physical if p['kind']=='native_write' and p['event']=='rx' and int(p['node'])==group['source'] and int(p['task']) in incoming]
        first_rx={}
        for packet in received:
            key=int(packet['task']),int(packet['offset'])
            expected=min(c['runtime']['segment_bytes'],c['transfers'][key[0]]['bytes']-key[1])
            require(int(packet['payload_bytes'])==expected and expected>0,'Physical received range identity')
            first_rx[key]=min(first_rx.get(key,2**64),int(packet['time_ps']))
        expected_ranges={(task,off) for task in incoming for off in range(0,c['transfers'][task]['bytes'],c['runtime']['segment_bytes'])}
        require(set(first_rx)==expected_ranges,'Missing full expert physical first-arrival coverage')
        chunk_rx=[time for (task,off),time in first_rx.items() if task in own]
        child_tx=[int(p['time_ps']) for p in physical if p['event']=='tx_start' and int(p['node'])==group['source'] and int(p['group'])==group['group'] and p['kind'] in ('envelope','native_write')]
        if received and chunk_rx and child_tx:
            final_rx=max(first_rx.values());first_tx=min(child_tx)
            if max(chunk_rx)<=own_ready<=group_ready<=first_tx<final_rx:
                streaming.append(dict(group=group['group'],expert=group['expert'],relay_physical=group['source_physical'],chunk_rx_ps=max(chunk_rx),chunk_ready_ps=own_ready,group_ready_ps=group_ready,downstream_tx_ps=first_tx,full_expert_rx_ps=final_rx))
    relay_intervals=defaultdict(list);expert_intervals=defaultdict(list)
    for packet in physical:
        if packet['event']!='tx_start' or int(packet['group']) not in groups:continue
        group=groups[int(packet['group'])]
        if int(packet['node'])!=group['source'] or packet['kind'] not in ('envelope','native_write'):continue
        time=int(packet['time_ps']);expert_intervals[group['expert']].append(time)
        if group['graph_role']=='stage2':relay_intervals[group['expert'],group['source_physical']].append(time)
    relay_spans={key:(min(value),max(value)) for key,value in relay_intervals.items()}
    expert_spans={key:(min(value),max(value)) for key,value in expert_intervals.items()}
    coverage['multiple_relays']=any(a[0]==b[0] and a!=b and max(x[0],y[0])<min(x[1],y[1]) for a,x in relay_spans.items() for b,y in relay_spans.items())
    coverage['concurrent_experts']=any(a!=b and max(x[0],y[0])<min(x[1],y[1]) for a,x in expert_spans.items() for b,y in expert_spans.items())
    coverage['streaming_physical']=bool(streaming)
    coverage['groupchunk_all_parents']=bool(group_wait)
    coverage['cross_expert_chunk_isolation']=len({g['expert'] for g in groups.values()})>1 and any(g['offset']>0 for g in groups.values())
    write(Path(directory)/'physical-witnesses.json',dict(status='PASS',streaming=streaming,group_wait=group_wait,coverage=coverage,trace_rows=len(events)+len(physical)))
    return coverage,physical


def fault_witness(directory,row,c,physical,life):
    wire=csv_rows(directory,'weight-packets.csv');fault=row['fault']
    injected=[r for r in wire if r['kind']==('duplicate' if fault=='duplicate-once' else 'drop')]
    require(len(injected)==1,'Fault selector did not inject exactly once');drop=injected[0];task=int(drop['task']);x=c['transfers'][task]
    group=next(g for g in c['hybrid_groups'] if any(m['task']==task for m in g['members']))
    require(group['graph_role']==row['fault_role'],'Fault injected on wrong graph hop')
    require(len(group['members'])>1,'Fault requires real multi-target operation')
    n=c['planner_input']['npus'];psn=int(drop['psn']);when=int(drop['time_ps'])
    retries=[r for r in wire if r['kind']=='native_retry']
    if fault=='data-once':
        require(retries,'Dropped native WRITE was not retried')
        require(any(all(retry[k]==drop[k] for k in ('task','src_tpn','dst_tpn','psn','ssn','payload_bytes')) for retry in retries),'Dropped original PSN itself was not retried')
        for retry in retries:
            retry_task=int(retry['task']);child=c['transfers'][retry_task]
            require(child['source']==x['source'] and child['target']==x['target'],'Native GBN retry reached an unaffected target/pair')
            original=[r for r in wire if r['kind']=='first_native' and all(r[k]==retry[k] for k in ('task','src_tpn','dst_tpn','psn','ssn','payload_bytes'))]
            require(len(original)==1,'Retry changed original native TP/PSN/SSN/task/payload identity')
            require(ordered_route(physical,retry_task,child['source'],child['target'],n,after=max(when,int(retry['time_ps'])),psn=int(retry['psn'])),'Native retry missing real source/switch/target physical path')
        require(int(life['weight_retry_packets'])==len(retries),'Native WRITE retry evidence/counter mismatch')
        # This is the tail of one logical CHUNK, not necessarily the last PSN
        # outstanding on the reused native TP. Native GBN may replay its suffix.
    elif fault=='taack-once':
        path=ordered_route(physical,task,x['target'],x['source'],n,kind='taack',after=when,psn=psn)
        require(path,'Missing reverse native TAACK physical retransmission')
        require(any(p['kind']=='taack' and int(p['task'])==task and int(p['psn'])==psn and p['event']=='tx_start' and int(p['node'])==x['target'] and int(p['time_ps'])<when for p in physical),'Missing original reverse TAACK before loss')
    elif fault=='ack-once':
        # TPACK loss may be superseded by cumulative ACK. Require the injected
        # reverse path, and at least native WRITE retry or later native ACK.
        reverse=[p for p in physical if p['kind']=='tpack' and int(p['task'])==task and int(p['psn'])==psn]
        require(ordered_route(reverse,task,x['target'],x['source'],n,kind='tpack',psn=psn),'Missing physical TPACK path')
        progressed=bool(retries) or any(p['kind']=='tpack' and int(p['task'])==task and p['event']=='rx' and int(p['node'])==x['source'] and int(p['time_ps'])>when for p in physical)
        require(progressed,'TPACK-loss recovery has no later native packet evidence')
    else:
        require(int(life.get('injected_duplicates',0))==1,'Native duplicate delivery seam absent')
        require(not retries,'Duplicate delivery unexpectedly generated WRITE retries')
        require(int(life['injected_losses'])==0,'Duplicate delivery mislabeled as drop')
    return {row['required_witnesses'][0]:True}


def live_witnesses(directory,row):
    directory=Path(directory);c=read(directory/'config.json');life=read(directory/'hybrid-lifecycle.json')
    verified=read(directory/'independent.json');require(verified['status']=='PASS','Independent verification missing')
    coverage=dict(verified.get('coverage',{}))
    coverage['direct_fallback']=any(g['graph_role']=='direct-fallback' for g in c['hybrid_groups'])
    coverage['resource_cleanup']=all(life[k]==0 for k in ('pending_associations','pending_members','active_codecs')) and life['allocated_codecs']==life['retired_codecs'] and life['all_native_pairs_safe'] is True
    if (directory/'diagnostic-jetty-status.json').exists():
        status=read(directory/'diagnostic-jetty-status.json');require(status['incomplete'] is False,'Incomplete global Jetty observer')
        require(not status['terminal_nonzero_jetties'] and not status['occupancy_errors'],'Native occupancy observer unsafe')
    physical=[]
    if '--invalidateGrant=1' in row['options']:
        source=c['hybrid_groups'][0]['source'];reference=directory.parents[1]/'B04'/'candidate'
        def rejected(root):
            return sum(int(r['count']) for r in csv_rows(root,'diagnostic-native-aggregates.csv') if int(r['metric'])==8 and int(r['node'])==source and int(r['port'])==0)
        actual_rejected,baseline_rejected=rejected(directory),rejected(reference)
        coverage['stale_grant']=int(life['invalidated_grants'])==1 and actual_rejected>baseline_rejected
        write(directory/'stale-grant-witness.json',dict(status='PASS' if coverage['stale_grant'] else 'INCOMPLETE',source=source,port=0,native_grant_rejections=actual_rejected,baseline_native_grant_rejections=baseline_rejected,all_native_pairs_safe=life['all_native_pairs_safe']))
    else:coverage['stale_grant']=False
    if row['log_level']=='events':
        trace,physical=trace_witnesses(directory,c,life);coverage.update(trace)
        events=csv_rows(directory,'events.csv')
        coverage['duplicate_ready']=any(e['event']=='duplicate_ignored' for e in events)
        ready={int(e['task']):int(e['time_ps']) for e in events if e['event']=='edge_ready'}
        weights=[x for x in c['transfers'] if x['stage']==2 and not x['dependencies']]
        coverage['completion_reorder']=any(x['physical']==y['physical'] and x['offset']<y['offset'] and ready.get(x['task'],-1)>ready.get(y['task'],2**64) for x in weights for y in weights)
    if row['kind']=='fault':coverage.update(fault_witness(directory,row,c,physical,life))
    return coverage


def verifier_mutations(directory,row):
    """Mutate COPIES of a genuine validated run. Never count this as live faults."""
    import tempfile
    verifier=load('phase_b_independent_verifier',H/'verify.py')
    directory=Path(directory);original=freeze(p for p in directory.iterdir() if p.is_file())
    def csv_change(root,name,change):
        values=csv_rows(root,name);fields=list(values[0]);change(values)
        with (root/name).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(values)
    def json_change(root,name,change):
        value=read(root/name);change(value);write(root/name,value)
    mutations=[
      ('actual-member-byte-coverage',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r[0].update(first_send_bytes=str(int(r[0]['first_send_bytes'])-1)))),
      ('wrong-expert',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r[0].update(expert=str(int(r[0]['expert'])+1)))),
      ('wrong-chunk-range',lambda d:csv_change(d,'hybrid-stats.csv',lambda r:r[0].update(offset=str(int(r[0]['offset'])+1)))),
      ('wrong-source',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r[0].update(source=str(int(r[0]['source'])+1)))),
      ('missing-member',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r.pop())),
      ('duplicate-member',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r.append(dict(r[0])))),
      ('delayed-native-submit',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r[0].update(native_submit_ps=str(int(r[0]['native_submit_ps'])+1)))),
      ('premature-sender-complete',lambda d:csv_change(d,'hybrid-groups.csv',lambda r:r[0].update(sender_complete_ps='0'))),
      ('false-native-safe',lambda d:json_change(d,'hybrid-lifecycle.json',lambda v:v.update(all_native_pairs_safe=False))),
      ('undrained-association',lambda d:json_change(d,'hybrid-lifecycle.json',lambda v:v.update(pending_associations=1))),
      ('incorrect-fallback-wire',lambda d:csv_change(d,'hybrid-fallback.csv',lambda r:r[0].update(wire_bytes=str(int(r[0]['wire_bytes'])+1)))),
      ('incorrect-envelope-count',lambda d:json_change(d,'hybrid-summary.json',lambda v:v['totals'].update(envelopes=v['totals']['envelopes']+1))),
    ]
    reports=[]
    for name,mutate in mutations:
        with tempfile.TemporaryDirectory(prefix='verifier-mutation-',dir=directory.parent) as temporary:
            dest=Path(temporary)
            for path in directory.iterdir():
                if path.is_file():shutil.copyfile(path,dest/path.name)
            mutate(dest)
            try:verifier.verify_hybrid(dest,fault=row['kind']=='fault')
            except (ValueError,AssertionError) as exc:reports.append(dict(mutation=name,status='REJECTED',reason=str(exc)))
            else:raise ValueError('Independent hybrid verifier accepted mutation: '+name)
    check(original)
    result=dict(status='PASS',kind='MUTATED_GENUINE_EVIDENCE_NOT_RUNTIME_FAULT',source=str(directory),source_identity=original,tests=reports,
                limitation='Raw byte corruption is covered by live weight-byte/relay-buffer tests; Summary does not store complete payload dumps.')
    write(directory/'verifier-mutations.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='phase',required=True)
    prep=subs.add_parser('prepare')
    for key in ('out','binary','accepted-binary','runtime-identity','accepted-identity','graph-tool'):prep.add_argument('--'+key,type=Path,required=True)
    exe=subs.add_parser('execute');exe.add_argument('--out',type=Path,required=True);exe.add_argument('--approval',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    prepare(args) if args.phase=='prepare' else run(args)

if __name__=='__main__':main()
