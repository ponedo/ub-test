#!/usr/bin/env python3
"""Metadata-only exact 30 unexecuted target runs plus one 64KiB paired witness.
No execution, approval, search, retry, or generic resume. Preserve the seven-run stop.
"""
import argparse, copy, csv, os, shutil
from support import *
from target_contract import check_target
STOP='INCOMPLETE mandatory coverage: streaming_physical'
CONTRACT='fixed3136-v04-window-and-v09-only'

def prepare(prior,out,archived_small):
    prior=prior.resolve();out=out.resolve();m=read(prior/'command-manifest.json');l=read(prior/'ledger.json')
    require(not out.exists(),'Fresh output only')
    require(m['executions']==37 and [r['id'] for r in m['rows']]==[r['id'] for r in declaration()['rows']],'Exact original matrix required')
    require(l['status']=='INCOMPLETE' and l['reason']==STOP,'Only preserved V04 streaming stop')
    require([r['id'] for r in l['rows']]==['V01','V02','V03','V04'] and all(r['status']=='PASS' for r in l['rows'][:3]),'Exact successful prefix')
    require([(e['arm'],e['status']) for e in l['rows'][-1]['executions']]==[('v1','INCOMPLETE')],'Exactly seven previous runs')
    e=l['rows'][-1]['executions'][0]
    require([k for k in m['rows'][3]['required_witnesses'] if not e['coverage'].get(k)]==['streaming_physical'],'No other missing witness')
    require(m['identity_sha256']==sha(prior/'identity.json'),'Prior identity drift')
    identity=read(prior/'identity.json');key=str(HERE/'small.py')
    require(identity[key]==sha(archived_small),'Archived executed helper mismatch')
    oldhash=identity.pop(key);check(identity);identity.update(freeze([HERE/'small.py',archived_small,Path(__file__)]))
    rows=copy.deepcopy(m['rows'][3:]);rows[0]['executions']=rows[0]['executions'][1:];rows[0]['arms']=['candidate-on']
    require(sum(len(r['executions']) for r in rows)==30,'Exactly30 original unexecuted runs')
    for row in rows:
        for ex in row['executions']:require(not (Path(ex['directory'])/'simulator-host').exists(),'No rerun permitted')
    out.mkdir(parents=True);os.environ['RELAY_GRAPH_TOOL']=m['graph_tool']
    for row in rows:
        for ex in row['executions']:
            src=Path(ex['directory']);dst=out/'runs'/row['id']/ex['arm'];phase_b.copy_inputs(src,dst)
            require(all(sha(src/n)==sha(dst/n) for n in INPUTS),'Original input delta forbidden');check_target(dst)
            ex['command']=[a.replace(str(src),str(dst)) for a in ex['command']];ex['directory']=str(dst)
    # Reuse the exact Planner output; change only expert weight length in base inputs.
    oldbase=prior/'fixtures/two-hop/balanced-base';base=out/'fixtures/streaming-64k/balanced-base';shutil.copytree(oldbase,base)
    c=read(base/'config.json');require(c['parameters']['weight_bytes']==12288,'Original12KiB required')
    for group in ['parameters','runtime']:c[group]['weight_bytes']=65536
    for t in c['transfers']:
        if t['stage']==2:t['bytes']=65536
    write(base/'config.json',c)
    lines=(base/'input.txt').read_text().splitlines();fields=lines[1].split();require(fields[1]=='12288','Original serialized weight');fields[1]='65536';lines[1]=' '.join(fields);(base/'input.txt').write_text('\n'.join(lines)+'\n')
    with (base/'transfers.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(c['transfers'][0]));w.writeheader();w.writerows(c['transfers'])
    root=base.parent;spec=declaration()['fixtures']['two-hop'];adapter.emit(base,spec['relay'],'chunk-streaming',root/'chunk-streaming');newc,plan=adapter.from_cs_control(root/'chunk-streaming',root/HYBRID)
    oldc=read(prior/'fixtures/two-hop'/HYBRID/'config.json')
    def edges(config):return sorted({(t['source'],t['target'],t['source_physical'],t['physical'],bool(t['dependencies'])) for t in config['transfers'] if t['stage']==2})
    require(edges(newc)==edges(oldc),'Tree edge/role set changed')
    require(sha(base/'plan.json')==sha(oldbase/'plan.json') and sha(base/'assignments.csv')==sha(oldbase/'assignments.csv'),'Planner/placement changed')
    check_target(root/HYBRID);write(root/HYBRID/'preflight.json',preflight.check_directory(root/HYBRID,Path(m['graph_tool']),root/'chunk-streaming'))
    newrow=copy.deepcopy(m['rows'][3]);newrow.update(id='S64',fixture='streaming-64k',cs_control=str(root/'chunk-streaming'),purpose='Single predeclared coverage extension; not a clean performance comparison')
    for ex in newrow['executions']:
        src=Path(ex['directory']);dst=out/'runs/S64'/ex['arm'];phase_b.copy_inputs(root/HYBRID,dst);check_target(dst)
        ex['command']=[a.replace(str(src),str(dst)) for a in ex['command']];ex['directory']=str(dst)
    rows.append(newrow)
    refs=[]
    for ident in ['V01','V04']:
        src=prior/'runs'/ident/'v1';dst=out/'runs'/ident/'v1';dst.parent.mkdir(parents=True,exist_ok=True);dst.symlink_to(src,target_is_directory=True)
        require(read(src/'independent.json')['status']=='PASS','Independent reference failure');pins=freeze(p for p in src.iterdir() if p.is_file());identity.update(pins);refs.append(dict(id=ident,source=str(src),files=pins,purpose='Read-only previous result, not a new execution'))
    receipt=dict(old_small_sha256=oldhash,new_small_sha256=sha(HERE/'small.py'),archive=str(archived_small.resolve()),old_plan_sha256=sha(oldbase/'plan.json'),new_plan_sha256=sha(base/'plan.json'),tree_edge_roles=edges(newc),original_weight_bytes=12288,new_weight_bytes=65536,chunk_bytes=4096,prior_executions=7,new_executions=32)
    write(out/'preparation-receipt.json',receipt)
    identity.update(freeze(p for p in out.rglob('*') if p.is_file()))
    identity.update(freeze([prior/'command-manifest.json',prior/'identity.json',prior/'ledger.json']))
    write(out/'identity.json',identity)
    write(out/'command-manifest.json',dict(base=BASE_V1,rows=rows,graph_tool=m['graph_tool'],identity_sha256=sha(out/'identity.json'),executions=32,continuation_contract=CONTRACT,allowed_missing_witnesses={'V04':{'v1':['streaming_physical'],'candidate-on':['streaming_physical']},'C-V04':{'candidate-off':['streaming_physical']},'V09':{'candidate-on':['stale_grant']}},prior_status='INCOMPLETE_NOT_EXERCISED',overall_admission='NOT_GENERAL_ADMISSION',read_only_references=refs))
    write(out/'ledger.json',dict(status='PREPARED',rows=[],unrun_rows=[r['id'] for r in rows]))
    print('PREPARED32, no simulator or approval: '+sha(out/'command-manifest.json'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['prior','out','archived-small']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();prepare(a.prior,a.out,a.archived_small)
