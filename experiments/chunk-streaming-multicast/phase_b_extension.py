#!/usr/bin/env python3
"""One scoped F03 oracle correction; import old evidence, execute only F04 onward."""
import argparse
import copy
import os
from common import *
import ack_oracle
import phase_b

BASE_MANIFEST_SHA='9df7df70b91b8bc422f978b9a5a950ee8748c852c51a47465d61840cc77fb34c'
OLD_ERROR='TPACK-loss recovery has no later native packet evidence'
IMPORTED_IDS=[f'B{i:02}' for i in range(1,13)]+['F01','F02','F03']


def prepare(args):
    base=args.base.resolve();out=args.out.resolve();receipt=args.receipt.resolve()
    require(not out.exists() and base not in out.parents,'Fresh extension outside preserved base required')
    require(sha(base/'prepared-manifest.json')==BASE_MANIFEST_SHA,'Not reviewed v3 base manifest')
    manifest=read(base/'prepared-manifest.json');ledger=read(base/'ledger.json');result=read(base/'phase-b.json')
    require(ledger['status']=='STOPPED' and ledger['reason']==OLD_ERROR and result['status']=='STOPPED' and result['error']==OLD_ERROR,'Not the specific preserved F03 oracle failure')
    require([row['id'] for row in ledger['rows']]==IMPORTED_IDS[:-1] and all(row['status']=='PASS' for row in ledger['rows']),'Expected exactly fourteen successful original rows')
    require([row['id'] for row in result['rows']]==IMPORTED_IDS and result['rows'][-1]['status']=='FAIL','Expected original F03 failed verdict')
    require(all(row['status']=='PASS' for row in result['rows'][:-1]),'Cannot import a failed previous row')
    identity=read(base/'immutable-identity.json');check(identity)
    base_files=freeze(p for p in base.rglob('*') if p.is_file());identity.update(base_files)
    proof=read(receipt);check(proof['source_identity'])
    actual=ack_oracle.check_directory(base/'runs/F03/candidate')
    require(all(proof.get(k)==v for k,v in actual.items()) and proof['status']=='PASS','Posthoc proof does not reproduce from immutable original outputs')
    require(proof['kind']=='POSTHOC_ORACLE_CORRECTION_NO_SIMULATOR_RERUN','Wrong posthoc receipt type')
    resource_admission(out.parent);out.mkdir()
    imported=copy.deepcopy(result['rows'])
    for row in imported:
        row['provenance']=dict(kind='IMPORTED_ORIGINAL_PASS',base=str(base),original_row_status=row['status'])
    corrected=imported[-1];corrected['status']='PASS';corrected['coverage']=proof['coverage']
    corrected['provenance'].update(kind='EXPLICIT_POSTHOC_ORACLE_REVALIDATION',receipt=str(receipt),receipt_sha256=sha(receipt),original_error=OLD_ERROR,no_simulator_rerun=True)
    prepared=copy.deepcopy(manifest)
    require([row['id'] for row in prepared['rows'][:15]]==IMPORTED_IDS and prepared['rows'][15]['id']=='F04','Unexpected original row order')
    new_inputs=[]
    for row in prepared['rows'][15:]:
        for execution in row['executions']:
            original=Path(execution['directory']);dest=out/'runs'/row['id']/execution['variant']
            require(set(p.name for p in original.iterdir())==set(INPUTS),'Remaining case has already been executed or modified: '+row['id'])
            phase_b.copy_inputs(original,dest)
            command=execution['command'];new_command=[arg.replace(str(original),str(dest)) for arg in command]
            require([arg.replace(str(dest),str(original)) for arg in new_command]==command,'Only output/input location may change')
            execution.update(directory=str(dest),command=new_command)
            new_inputs.extend(dest/name for name in INPUTS)
    source_files=[H/name for name in ('ack_oracle.py','test_ack_oracle.py','phase_b_extension.py','POSTHOC_F03.md')]
    identity.update(freeze(source_files+[receipt]+new_inputs))
    provenance=dict(kind='SCOPED_F03_POSTHOC_CONTINUATION',base=str(base),base_manifest_sha256=BASE_MANIFEST_SHA,
        preserved_stopped_ledger_sha256=sha(base/'ledger.json'),preserved_failed_result_sha256=sha(base/'phase-b.json'),
        prior_artifact_identity=base_files,posthoc_receipt=str(receipt),posthoc_receipt_sha256=sha(receipt),
        imported_rows=imported,remaining_row_ids=[r['id'] for r in prepared['rows'][15:]],
        remaining_simulator_executions=sum(len(r['executions']) for r in prepared['rows'][15:]),
        limitation=proof['limitation'])
    write(out/'import-receipt.json',provenance);identity.update(freeze([out/'import-receipt.json']))
    write(out/'immutable-identity.json',identity)
    prepared.update(status='PREPARED_POSTHOC_CONTINUATION',immutable_identity_sha256=sha(out/'immutable-identity.json'),
        import_receipt_sha256=sha(out/'import-receipt.json'),base_manifest_sha256=BASE_MANIFEST_SHA,
        remaining_row_ids=provenance['remaining_row_ids'])
    write(out/'prepared-manifest.json',prepared)
    write(out/'ledger.json',dict(status='PAUSED',rows=[dict(id=row['id'],status='PASS') for row in imported],
        provenance='Imported evidence, not rerun; original STOPPED ledger preserved',import_receipt_sha256=sha(out/'import-receipt.json')))
    write(out/'phase-b.json',dict(status='INCOMPLETE',phase='B',rows=imported,coverage=phase_b.aggregate_coverage(imported),
        unsupported=manifest['unsupported'],next_row='F04',import_receipt_sha256=sha(out/'import-receipt.json')))
    check(identity)
    print(json.dumps(dict(status='PREPARED',manifest_sha256=sha(out/'prepared-manifest.json'),ledger_sha256=sha(out/'ledger.json'),
        import_receipt_sha256=sha(out/'import-receipt.json'),posthoc_receipt_sha256=sha(receipt),remaining_rows=len(provenance['remaining_row_ids']),
        remaining_simulator_executions=provenance['remaining_simulator_executions']),indent=2))


def execute(args):
    out=args.out.resolve();manifest=read(out/'prepared-manifest.json');provenance=read(out/'import-receipt.json');approval=read(args.approval)
    require(manifest['import_receipt_sha256']==sha(out/'import-receipt.json'),'Import receipt drift')
    require(approval.get('approved_to_import_prior') is True and approval.get('posthoc_receipt_sha256')==provenance['posthoc_receipt_sha256'],'Explicit posthoc evidence-import approval missing')
    require(approval.get('row_ids')==provenance['remaining_row_ids'],'Only all remaining declared F04-onward rows are allowed')
    ledger=read(out/'ledger.json');result=read(out/'phase-b.json')
    require(ledger['status']=='PAUSED' and [r['id'] for r in ledger['rows']]==IMPORTED_IDS,'One-shot fresh import ledger required')
    require(result['rows']==provenance['imported_rows'] and result['status']=='INCOMPLETE','Imported records changed')
    identity=read(out/'immutable-identity.json');check(identity)
    try:phase_b.run(args)  # unchanged approval gates, guards, negative oracles and stop-on-failure
    finally:check(identity)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for key in ('base','out','receipt'):prep.add_argument('--'+key,type=Path,required=True)
    exe=sub.add_parser('execute')
    for key in ('out','approval'):exe.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();os.umask(0o077)
    prepare(args) if args.action=='prepare' else execute(args)

if __name__=='__main__':main()
