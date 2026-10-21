#!/usr/bin/env python3
"""Prepare only 19 unexecuted independent rows after the exact V09 witness stop.

Metadata only. Never execute, approve, retry, alter an injector, or replace the
preserved incomplete ledger. Existing v1 outputs are pinned parity references.
"""
import argparse
import copy
from support import *

IDS = ['V10','V11','V12','V13','V14','C-V01','C-V04','C-V06','N02','N04','N08']
STOP = 'INCOMPLETE mandatory coverage: stale_grant'

def validate(prior):
    prior=Path(prior).resolve();manifest=read(prior/'command-manifest.json');ledger=read(prior/'ledger.json')
    require(manifest['base']==BASE_V1 and manifest['executions']==37,'Only the declared original37 matrix')
    require([r['id'] for r in manifest['rows']]==[r['id'] for r in declaration()['rows']],'Matrix order/scope drift')
    require(manifest['identity_sha256']==sha(prior/'identity.json'),'Prior identity manifest drift')
    identity=read(prior/'identity.json');check(identity)
    require(ledger['status']=='INCOMPLETE' and ledger.get('reason')==STOP,'Only exact missing V09 stale-grant witness')
    require([r['id'] for r in ledger['rows']]==[f'V{i:02}' for i in range(1,10)],'Unexpected attempted prefix')
    require(all(r['status']=='PASS' for r in ledger['rows'][:8]),'Prior successful prefix required')
    last=ledger['rows'][-1];require(last['status']=='INCOMPLETE','V09 must remain incomplete')
    require([(e['arm'],e['status']) for e in last['executions']]==[('v1','PASS'),('candidate-on','INCOMPLETE')],'Unexpected V09 outcome')
    require(last['executions'][-1].get('reason')==STOP,'Different failure cannot continue')
    require(last['executions'][-1]['coverage'].get('stale_grant') is False,'Do not invent stale-grant coverage')
    rows=[copy.deepcopy(r) for r in manifest['rows'] if r['id'] in IDS]
    require([r['id'] for r in rows]==IDS and sum(len(r['executions']) for r in rows)==19,'Only19 declared remaining executions')
    for row in rows:
        for e in row['executions']:
            require(not (Path(e['directory'])/'simulator-host').exists(),'Remaining execution already started')
    return manifest,ledger,identity,rows

def prepare(prior,out):
    prior=Path(prior).resolve();out=Path(out).resolve()
    manifest,ledger,identity,rows=validate(prior)
    require(not out.exists(),'Fresh output required; never resume or overwrite')
    out.mkdir(parents=True)
    for row in rows:
        for e in row['executions']:
            source=Path(e['directory']);dest=out/'runs'/row['id']/e['arm']
            phase_b.copy_inputs(source,dest)
            e['command']=[arg.replace(str(source),str(dest)) for arg in e['command']]
            e['directory']=str(dest);identity.update(freeze(dest/n for n in INPUTS))
    references=[]
    for ident in ['V01','V04','V06']:
        source=prior/'runs'/ident/'v1';dest=out/'runs'/ident/'v1'
        require(read(source/'independent.json')['status']=='PASS','Parity reference lacks verified v1 result')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(source,target_is_directory=True)
        files=[p for p in source.iterdir() if p.is_file()];pins=freeze(files);identity.update(pins)
        references.append(dict(row=ident,arm='v1',source=str(source),purpose='Pinned existing v1 output for read-only disabled parity; not a new execution',files=pins))
    identity.update(freeze([Path(__file__),prior/'command-manifest.json',prior/'identity.json',prior/'ledger.json']))
    write(out/'identity.json',identity)
    result=dict(base=BASE_V1,rows=rows,graph_tool=manifest['graph_tool'],identity_sha256=sha(out/'identity.json'),executions=19,
        purpose='Explicit remaining independent rows only; no resume or rerun of first18',
        prior_manifest_sha256=sha(prior/'command-manifest.json'),prior_ledger_sha256=sha(prior/'ledger.json'),
        prior_ledger_status='INCOMPLETE',v09_status='NOT_EXERCISED',overall_admission='NOT_GENERAL_ADMISSION',
        read_only_parity_references=references)
    write(out/'command-manifest.json',result);write(out/'ledger.json',dict(status='PREPARED',rows=[],unrun_rows=IDS))
    print('PREPARED19, zero executions, no approval created: '+sha(out/'command-manifest.json'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior',type=Path,required=True)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    if args.check_only:
        validate(args.prior);print('PASS exact preserved V09 stop and19 remaining metadata; no files or executions created')
    else:
        require(args.out is not None,'--out required for preparation');prepare(args.prior,args.out)
if __name__=='__main__':main()
