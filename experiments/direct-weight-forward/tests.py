#!/usr/bin/env python3
import argparse,copy,csv,json,subprocess,sys,tempfile
from pathlib import Path
from adapter import emit,require
from verify import verify
from cases import cases
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.out).resolve();negative=root/'negative';negative.mkdir(exist_ok=True)
canary=root/'single_replica4/ultraep';records=[]
for fault,message in [('weight-byte','payload byte mismatch'),('premature-ready','ready before target completion coverage'),('duplicate-weight','duplicate forwarding'),('early-compute','compute token/gate dependency')]:
    dest=negative/fault;dest.mkdir(exist_ok=True)
    cmd=[sys.executable,'./ns3','run','--no-build',f'direct-weight-forward --input={canary}/input.txt --out={dest} --fault={fault}']
    with (dest/'console.txt').open('w') as f:r=subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT)
    require(r.returncode!=0 and message in (dest/'console.txt').read_text(),'fault not rejected: '+fault)
    records.append(dict(fault=fault,command=cmd,returncode=r.returncode,expected_error=message))
# Corrupt execution input provenance/quota, proving the C++ reader checks the
# adapter contract even when called without Python validation.
for field,message in [(6,'weight provenance'),(4,'physical quota mismatch')]:
    name='bad-provenance' if field==6 else 'bad-quota';dest=negative/name;dest.mkdir(exist_ok=True)
    lines=(canary/'input.txt').read_text().splitlines();np=int(lines[1].split()[-1])
    for i in range(3,3+np):
        values=list(map(int,lines[i].split()))
        if values[3]==1:
            values[field]=(values[field]+1)%4 if field==6 else values[field]+1
            lines[i]=' '.join(map(str,values));break
    (dest/'input.txt').write_text('\n'.join(lines)+'\n')
    cmd=[sys.executable,'./ns3','run','--no-build',f'direct-weight-forward --input={dest}/input.txt --out={dest}']
    with (dest/'console.txt').open('w') as f:r=subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT)
    require(r.returncode!=0 and message in (dest/'console.txt').read_text(),'bad execution input accepted')
    records.append(dict(fault=name,command=cmd,returncode=r.returncode,expected_error=message))

# Independent verifier rejects changed dependencies, missing assignments and fake ready.
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp)
    for name in ['config.json','plan.json']: (d/name).write_bytes((canary/name).read_bytes())
    original=(canary/'events.csv').read_text().splitlines();header=original[0];rows=list(csv.DictReader(original))
    variants=[]
    v=copy.deepcopy(rows);v=[r for r in v if not(r['event']=='data_ready' and r['task']=='0')];variants.append(v)
    v=copy.deepcopy(rows)
    for r in v:
        if r['event']=='weight_ready':r['time_ps']='201000'
    v.sort(key=lambda r:int(r['time_ps']));variants.append(v)
    v=copy.deepcopy(rows)
    for r in v:
        if r['event']=='expert_end':r['time_ps']=str(int(r['time_ps'])+1);break
    v.sort(key=lambda r:int(r['time_ps']));variants.append(v)
    for v in variants:
        with (d/'events.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(v)
        try:verify(d)
        except ValueError:pass
        else:raise RuntimeError('verifier accepted tampering')
# Unsupported relay strategy must never silently select Direct.
c,params=cases()['single_replica4']
for mode in ['two-stage-relay','chunk-streaming-relay']:
    try:emit(c,dict(params,weight_strategy=mode),'ultraep',negative/'unsupported')
    except ValueError:pass
    else:raise RuntimeError('unsupported relay accepted')
# Requirement-specific real execution checkpoints.
def summary(name):return json.loads((root/name/'ultraep/summary.json').read_text())
require(summary('uniform4')['replicas']==0 and summary('single_replica4')['replicas']==1 and summary('multi_replica4')['replicas']>1,'replica cardinality coverage')
plan=json.loads((root/'multi_expert8/ultraep/plan.json').read_text());require(len({p['expert'] for p in plan['physical'] if p['kind']=='replica'})>1,'multiple logical replica experts missing')
require(summary('slots_zero4')['replicas']==0,'slot-zero bypass')
require(summary('reroute_slow4')['timeline']['weights_end']<summary('reroute_slow4')['timeline']['reroute_end'],'reroute overlap case')
require(summary('target_delay4')['timeline']['reroute_end']<summary('target_delay4')['timeline']['weights_end'],'weight overlap case')
require(summary('single_replica4')['timeline']['dispatch_gate']<summary('single_replica4')['weight_sender_end_ps'],'target-ready gate incorrectly waited for sender WQE completion')
require(summary('fixed64')['npus']==64 and summary('fixed64')['replicas']>0,'EP64 case')
require(summary('nondivisible4')['weight_bytes']%333!=0,'nondivisible weight coverage')
report=dict(status='PASS',live_faults=records,tampered_event_rejections=3,unsupported_strategies=2,coverage='replicas, overlap both directions, target-vs-sender readiness, EP64, nondivisible TA')
(root/'tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
