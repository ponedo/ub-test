#!/usr/bin/env python3
"""Explicit 37-run small manifest and single sequential pass. No resume/search."""
import argparse, os, shutil, resource
from support import *
from target_contract import check_target, reuse_balanced_base

def prepare(args):
    out=args.out.resolve();require(not out.exists(),'Fresh output required')
    identity=read(args.identity);check(identity)
    require(sha(args.control)==CONTROL_SHA256,'Formal control must be accepted v1 APP binary')
    require(identity.get(str(args.binary.resolve()))==sha(args.binary),'Candidate executable unpinned')
    require(identity.get(str(args.control.resolve()))==CONTROL_SHA256,'v1 control unpinned')
    require(identity.get(str(args.graph_tool.resolve()))==sha(args.graph_tool),'Graph tool unpinned')
    native=[k for k in identity if '/token-screen-native/build/lib/' in k]
    require(native,'Accepted native library closure required')
    resource_admission(out.parent);out.mkdir(parents=True)
    d=declaration();write(out/'matrix.json',d)
    os.environ['RELAY_GRAPH_TOOL']=str(args.graph_tool.resolve())
    direct=load('candidate_direct_adapter',E/'direct-weight-forward/adapter.py')
    prepared={}
    for name,spec in d['fixtures'].items():
        root=out/'fixtures'/name
        if args.reuse_fixtures:
            reuse_balanced_base(args.reuse_fixtures/name/'balanced-base',root/'balanced-base')
        else:
            direct.emit(spec['planner_input'],spec['model'],'ultraep',root/'balanced-base')
        adapter.emit(root/'balanced-base',spec['relay'],'chunk-streaming',root/'chunk-streaming')
        c,p=adapter.from_cs_control(root/'chunk-streaming',root/HYBRID)
        fixtures.inspect_topology(c,p,spec['topology'])
        check_target(root/HYBRID)
        check_target(root/'chunk-streaming')
        write(root/HYBRID/'preflight.json',preflight.check_directory(root/HYBRID,args.graph_tool,root/'chunk-streaming'))
        prepared[name]=root
    rows=[]
    for spec in d['rows']:
        row=dict(spec,executions=[],cs_control=str(prepared[spec['fixture']]/'chunk-streaming'))
        for arm in spec['arms']:
            target=out/'runs'/spec['id']/arm
            phase_b.copy_inputs(prepared[spec['fixture']]/HYBRID,target)
            check_target(target)
            binary=args.control if arm=='v1' else args.binary
            flags=['--logLevel='+spec['log_level']]+spec['options']
            if arm!='v1':flags.append('--cs-mc-align-hold='+str(int(arm=='candidate-on')))
            row['executions'].append(dict(arm=arm,directory=str(target),command=simulator(binary.resolve(),target,HYBRID,flags)))
        rows.append(row)
    # Pin only concrete implementation/oracle/planner and generated inputs, not results.
    harness=[p for root in (E,E.parent/'planner') for p in root.rglob('*.py') if '__pycache__' not in p.parts]
    identity.update(freeze(harness+[out/'matrix.json']))
    identity.update(freeze(p for p in (out/'fixtures').rglob('*') if p.is_file()))
    identity.update(freeze(out/'runs'/r['id']/a/n for r in rows for a in r['arms'] for n in INPUTS))
    write(out/'identity.json',identity)
    write(out/'command-manifest.json',dict(base=BASE_V1,rows=rows,graph_tool=str(args.graph_tool.resolve()),identity_sha256=sha(out/'identity.json'),executions=37))
    write(out/'ledger.json',dict(status='PREPARED',rows=[],unrun_rows=[r['id'] for r in rows]))
    print('PREPARED; no simulator ran; manifest '+sha(out/'command-manifest.json'))

def witnesses(directory,row,out,arm):
    # Existing fault F03 oracle remains explicitly bound to its original fixture ID.
    old=dict(row,id=row['retained_id'])
    old['options']=[x for x in old['options'] if x!='--invalidateGrant=1']
    original=phase_b.fault_witness
    import candidate_ack_oracle
    original_ack=phase_b_reproduce.ack_oracle
    phase_b_reproduce.ack_oracle=candidate_ack_oracle
    phase_b.fault_witness=phase_b_reproduce.fault_witness
    try: coverage=phase_b.live_witnesses(directory,old)
    finally:
        phase_b.fault_witness=original
        phase_b_reproduce.ack_oracle=original_ack
    if '--invalidateGrant=1' in row['options']:
        config=read(directory/'config.json');source=config['hybrid_groups'][0]['source']
        def rejected(path):
            return sum(int(r['count']) for r in phase_b.csv_rows(path,'diagnostic-native-aggregates.csv') if int(r['metric'])==8 and int(r['node'])==source and int(r['port'])==0)
        coverage['stale_grant']=read(directory/'hybrid-lifecycle.json')['invalidated_grants']==1 and rejected(directory)>rejected(out/'runs'/'V04'/arm)
    return coverage

def allowed_missing(row,arm,missing,manifest):
    # Only this explicitly approved target continuation may retain these gaps.
    if manifest.get('continuation_contract')!='fixed3136-v04-window-and-v09-only':return False
    return ((row['id']=='V04' and arm in ('v1','candidate-on') and missing==['streaming_physical'])
        or (row['id']=='C-V04' and arm=='candidate-off' and missing==['streaming_physical'])
        or (row['id']=='V09' and arm=='candidate-on' and missing==['stale_grant']))

def execute(args):
    from candidate_verify import check_candidate
    from evidence import native_accounting, disabled_parity
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out=args.out.resolve();m=read(out/'command-manifest.json');ledger=read(out/'ledger.json')
    approval=read(args.approval)
    require(approval.get('approved_to_run') is True and approval.get('manifest_sha256')==sha(out/'command-manifest.json'),'Exact manifest approval required')
    require(ledger['status']=='PREPARED','No implicit resume or retry')
    require(m['identity_sha256']==sha(out/'identity.json'),'Identity manifest drift')
    identity=read(out/'identity.json');check(identity)
    identity.update(freeze([out/'command-manifest.json',out/'identity.json',args.approval]))
    ledger['status']='RUNNING';write(out/'ledger.json',ledger)
    try:
        for row in m['rows']:
            record=dict(id=row['id'],status='RUNNING',executions=[]);ledger['rows'].append(record);ledger['unrun_rows'].remove(row['id']);write(out/'ledger.json',ledger)
            for execution in row['executions']:
                arm=execution['arm'];directory=Path(execution['directory']);check_target(directory);resource_admission(out,simulation=True)
                result=dict(arm=arm,command=execution['command'],status='RUNNING');record['executions'].append(result);write(out/'ledger.json',ledger)
                if row['kind']=='negative':
                    result['host']=phase_b.negative_stage(execution['command'],directory/'simulator-host',identity,row['expected_error'],allow_payload_abort=row['id']=='N02')
                    phase_b.require_no_success(directory,allow_missing_failure=result['host']['returncode']==-6)
                    if row['id']=='N04':phase_b.early_group_witness(directory)
                else:
                    result['host']=stage(execution['command'],directory/'simulator-host',identity)
                    write(directory/'postflight.json',preflight.check_directory(directory,Path(m['graph_tool']),Path(row['cs_control']),directory/'online-summary.json'))
                    command=[sys.executable,str(V1/'verify.py'),str(directory),'--out',str(directory/'independent.json')]
                    if row['kind']=='fault':command.append('--fault')
                    stage(command,directory/'independent-host',identity)
                    result['target_contract']=check_target(directory,executed=True)
                    result['native_accounting']=native_accounting(directory)
                    result['coverage']=witnesses(directory,row,out,arm)
                    missing=[k for k in row['required_witnesses'] if not result['coverage'].get(k)]
                    if arm!='v1':result['hold_verifier']=check_candidate(directory,arm=='candidate-on')
                    if row['kind']=='parity':result['parity']=disabled_parity(out/'runs'/row['reference']/'v1',directory)
                    if missing:
                        require(allowed_missing(row,arm,missing,m),'INCOMPLETE mandatory coverage: '+','.join(missing))
                        result.update(status='INCOMPLETE_NOT_EXERCISED',missing_witnesses=missing)
                if result['status']=='RUNNING':result['status']='PASS'
                write(out/'ledger.json',ledger)
            record['status']='INCOMPLETE_NOT_EXERCISED' if any(e['status']!='PASS' for e in record['executions']) else 'PASS'
            write(out/'ledger.json',ledger)
        ledger['status']='SMALL_EXECUTIONS_COMPLETE_NOT_GENERAL_ADMISSION'
    except BaseException as exc:
        ledger['status']='INCOMPLETE' if 'INCOMPLETE' in str(exc) else 'STOPPED';ledger['reason']=str(exc)
        if ledger['rows'] and ledger['rows'][-1]['status']=='RUNNING':
            ledger['rows'][-1]['status']=ledger['status']
            for result in ledger['rows'][-1]['executions']:
                if result['status']=='RUNNING':result['status']=ledger['status'];result['reason']=str(exc)
        raise
    finally:write(out/'ledger.json',ledger)

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='phase',required=True)
    q=s.add_parser('prepare')
    for key in ['out','identity','binary','control','graph-tool']:q.add_argument('--'+key,type=Path,required=True)
    q.add_argument('--reuse-fixtures',type=Path)
    q=s.add_parser('execute')
    for key in ['out','approval']:q.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();os.umask(0o077)
    prepare(args) if args.phase=='prepare' else execute(args)
if __name__=='__main__':main()
