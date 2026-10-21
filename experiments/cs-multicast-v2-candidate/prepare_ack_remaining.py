#!/usr/bin/env python3
"""Metadata only: exact16 unexecuted rows after the reviewed V12 ACK oracle stop."""
import argparse,copy
from support import *
from target_contract import check_target
STOP='No later same-TP cumulative ACK with observed covering PSNs and complete physical path'
def prepare(prior,out,archive):
    prior=prior.resolve();out=out.resolve();require(not out.exists(),'Fresh output only')
    m=read(prior/'command-manifest.json');l=read(prior/'ledger.json')
    require(m['executions']==32 and m['continuation_contract']=='fixed3136-v04-window-and-v09-only','Exact prior32 scope')
    require(l['status']=='STOPPED' and l['reason']==STOP,'Only reviewed ACK oracle stop')
    require([r['id'] for r in l['rows']]==[f'V{i:02}' for i in range(4,13)],'Exact attempted prefix')
    require(sum(len(r['executions']) for r in l['rows'])==16,'Exactly16 executions')
    require([(e['arm'],e['status']) for e in l['rows'][-1]['executions']]==[('v1','STOPPED')],'V12 control only')
    for r in l['rows'][:-1]:
        require(r['status']==('INCOMPLETE_NOT_EXERCISED' if r['id'] in ['V04','V09'] else 'PASS'),'Unexpected earlier failure')
    require(sha(prior/'identity.json')==m['identity_sha256'],'Prior identity drift');identity=read(prior/'identity.json');key=str(HERE/'small.py')
    require(identity[key]==sha(archive),'Executed helper archive mismatch');oldhash=identity.pop(key);check(identity)
    receipt=prior/'v12-v1-posthoc-inflight-ack.json';proof=read(receipt)
    require(proof['status']=='PASS' and proof['lost_wire_psn']==9 and proof['terminal_send_nxt']==12,'Reviewed posthoc proof missing');check(proof['source_identity'])
    rows=copy.deepcopy(m['rows'][next(i for i,r in enumerate(m['rows']) if r['id']=='V12'):]);rows[0]['arms']=['candidate-on'];rows[0]['executions']=rows[0]['executions'][1:]
    require([r['id'] for r in rows]==['V12','V13','V14','C-V01','C-V04','C-V06','N02','N04','N08','S64'] and sum(len(r['executions']) for r in rows)==16,'Exact remaining16')
    for row in rows:
        for e in row['executions']:require(not (Path(e['directory'])/'simulator-host').exists(),'No repeated simulation')
    out.mkdir(parents=True)
    for row in rows:
        for e in row['executions']:
            src=Path(e['directory']);dst=out/'runs'/row['id']/e['arm'];phase_b.copy_inputs(src,dst);check_target(dst)
            require(all(sha(src/n)==sha(dst/n) for n in INPUTS),'Input drift')
            e['command']=[x.replace(str(src),str(dst)) for x in e['command']];e['directory']=str(dst);identity.update(freeze(dst/n for n in INPUTS))
    refs=[]
    for ident in ['V01','V04','V06','V12']:
        src=(prior/'runs'/ident/'v1').resolve();dst=out/'runs'/ident/'v1';dst.parent.mkdir(parents=True,exist_ok=True);dst.symlink_to(src,target_is_directory=True)
        require(read(src/'independent.json')['status']=='PASS','Independent reference failure');pins=freeze(p for p in src.iterdir() if p.is_file());identity.update(pins);refs.append(dict(id=ident,source=str(src),purpose='Read-only completed reference, not execution',files=pins))
    identity.update(freeze([archive,HERE/'small.py',HERE/'candidate_ack_oracle.py',HERE/'test_candidate_ack.py',Path(__file__),receipt,prior/'command-manifest.json',prior/'identity.json',prior/'ledger.json']))
    write(out/'identity.json',identity)
    write(out/'command-manifest.json',dict(base=BASE_V1,rows=rows,executions=16,graph_tool=m['graph_tool'],identity_sha256=sha(out/'identity.json'),continuation_contract=m['continuation_contract'],allowed_missing_witnesses=m['allowed_missing_witnesses'],overall_admission='NOT_GENERAL_ADMISSION',read_only_references=refs,posthoc_control_ack_proof=str(receipt),old_small_sha256=oldhash,new_small_sha256=sha(HERE/'small.py'),new_ack_oracle_sha256=sha(HERE/'candidate_ack_oracle.py'),prior_stop_preserved=True))
    write(out/'ledger.json',dict(status='PREPARED',rows=[],unrun_rows=[r['id'] for r in rows]));print('PREPARED16, no simulator/approval: '+sha(out/'command-manifest.json'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['prior','out','archive']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();prepare(a.prior,a.out,a.archive)
