"""Fixed ingress/permutation experiment; all reported performance is measured."""
import argparse
import csv
import hashlib
import itertools
import json
import lzma
import subprocess
import tempfile
from collections import Counter,defaultdict,deque
from pathlib import Path
from workloads.schema.trace import read_trace,write_trace
from simulators.nano_ub.run import prepare
from evaluation.analyze import analyze,common_backlogged_window,jain

POLICIES=('fifo','rr','drr')
MODES=('csv','epoch-rr')
PERMUTATIONS=('original','reverse_groups','round_robin')
SCENARIOS=('moe_high','moe_skew')

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def read_csv(path):
    if path.exists():f=path.open()
    else:f=lzma.open(str(path)+'.xz','rt')
    with f:yield from csv.DictReader(f)
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def permute(rows,kind):
    result=[]
    for _,group in itertools.groupby(rows,key=lambda r:r['ready_ns']):
        group=list(group)
        if kind=='original':result+=group;continue
        jets=defaultdict(deque)
        for row in group:jets[row['jetty_id']].append(row)
        if kind=='reverse_groups':
            for j in sorted(jets,reverse=True):result.extend(jets[j])
        elif kind=='round_robin':
            while any(jets.values()):
                for j in sorted(jets):
                    if jets[j]:result.append(jets[j].popleft())
        else:raise ValueError(kind)
    assert {r['wr_id']:r for r in result}=={r['wr_id']:r for r in rows}
    for j in {r['jetty_id'] for r in rows}:
        assert [r['wr_id'] for r in result if r['jetty_id']==j]==[r['wr_id'] for r in rows if r['jetty_id']==j]
    assert [r['ready_ns'] for r in result]==sorted(r['ready_ns'] for r in result)
    return result

def simulate(binary,trace,directory,policy,mode):
    prepared=prepare(trace,directory,policy,mode)
    with (directory/'simulation.txt').open('w') as f:
        subprocess.run([str(binary),policy,str(prepared),str(directory/'systemc'),mode],stdout=f,stderr=subprocess.STDOUT,check=True)

def inspect_run(directory,mode):
    wr={int(r['wr_id']):{k:v if k=='phase' else int(v) for k,v in r.items()} for r in read_csv(directory/'systemc.wr.csv')}
    queues={i:deque() for i in range(12)};maximum=dict.fromkeys(queues,0)
    counts=defaultdict(Counter);stages={};selected=set();snapshot={};epochs={};last=(-1,-1,-1)
    first_enqueue={};first_dequeue=None
    for e in read_csv(directory/'systemc.timeline.csv'):
        t=int(e['time_ps']);delta=int(e['delta']);seq=int(e['event_seq']);id=int(e['wr_id']);event=e['event'];j=int(e['jetty'])
        assert seq==last[2]+1 and t>=last[0] and delta>=last[1];last=t,delta,seq
        counts[id][event]+=1
        if t>100000 and not snapshot:snapshot=dict(stages)
        if event=='dequeue':
            assert e['gate_held']=='0'
            selected.add(id);stages[id]='scheduler'
            if first_dequeue is None:first_dequeue={'time_ps':t,'delta':delta,'event_seq':seq,'wr_id':id}
        if event=='enqueue':first_enqueue.setdefault(j,{'time_ps':t,'delta':delta,'event_seq':seq,'wr_id':id})
        if event.startswith('q'):
            q=int(event.split('_')[0][1:]);action=event[len(str(q))+2:]
            if action=='write_accept':
                queues[q].append(id);maximum[q]=max(maximum[q],len(queues[q]));assert len(queues[q])<=1
                if q and id in selected:stages[id]='q'+str(q)
            if action=='read':
                assert queues[q].popleft()==id
                names={1:'order',2:'ordered_tap',3:'btah',4:'tpg',5:'tp',6:'congestion',7:'retransmit',8:'rtph',9:'nth',10:'encap',11:'link'}
                if q and id in selected:stages[id]=names[q]
        if mode=='epoch-rr':
            epoch=int(e['epoch'])
            if event=='epoch_begin':epochs[epoch]={'begin_ps':t,'begin_seq':seq,'submit':[],'enqueue':[]}
            if event=='submit':epochs[epoch]['submit'].append((id,j,seq))
            if event=='enqueue':epochs[epoch]['enqueue'].append((id,seq))
            if event=='epoch_release':
                group=epochs[epoch];group['release_ps']=t;group['release_seq']=seq
                assert {x[0] for x in group['submit']}=={x[0] for x in group['enqueue']}
                assert len({x[1] for x in group['submit']})==len(group['submit'])<=64
                assert max(x[1] for x in group['enqueue'])<seq
    assert all(not q for q in queues.values())
    for id in wr:
        assert counts[id]['input_read']==1
        for q in range(12):
            for action in ('write_offer','write_accept','read'):assert counts[id][f'q{q}_{action}']==1
    ack_start={};ack_total=Counter();last_event_time=-1
    for e in read_csv(directory/'systemc.events.csv'):
        id=int(e['wr_id']);r=wr[id];event=e['event'];t=int(e['time_ps']);assert t>=last_event_time;last_event_time=t
        if event in ('tx_start','tx_chunk','tx_end','rx_wire','memory_commit','ack_tx_start','ack_chunk','ack_tx_end','ack_rx_wire','complete'):
            assert int(e['psn'])==r['psn']
        if event=='rx_wire':assert t==r['tx_end_ps']+50000
        if event=='ack_tx_start':ack_start[id]=t
        if event=='ack_chunk':
            offset=int(e['offset']);n=int(e['bytes']);assert offset==ack_total[id]
            ack_total[id]+=n;assert t==ack_start[id]+(offset+n)*80
        if event=='ack_tx_end':assert ack_total[id]==64 and t==ack_start[id]+5120
        if event=='ack_rx_wire':assert t==ack_start[id]+5120+50000 and t<r['complete_ps']
    by_wire=sorted(wr.values(),key=lambda r:r['tx_start_ps']);by_dispatch=sorted(wr.values(),key=lambda r:r['dispatch_ps'])
    assert [r['wr_id'] for r in by_wire]==[r['wr_id'] for r in by_dispatch]
    initial=next((i for i,r in enumerate(by_wire) if r['jetty_id']!=by_wire[0]['jetty_id']),len(by_wire))
    result={'first_enqueue_per_jetty':first_enqueue,'first_dequeue':first_dequeue,'initial_wire_jetty':by_wire[0]['jetty_id'],
            'initial_same_jetty_wire_count':initial,'maximum_forward_fifo_occupancy':maximum,
            'selected_stage_snapshot_100ns':snapshot,'epoch_count':len(epochs),
            'admission_gate_closed_ns':sum((e['release_ps']-e['begin_ps'])/1000 for e in epochs.values()),
            'timeline_observations':last[2]+1,'causal_checks':'PSN, ACK byte timing, propagation, FIFO conservation/capacity, epoch admission, dispatch/wire order'}
    dump(directory/'timeline_checks.json',result)
    with (directory/'orders.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['dispatch_rank','wire_rank','wr_id','jetty_id','sequence','enqueue_ps','dispatch_ps','tx_start_ps','dispatch_to_wire_ns'])
        for i,r in enumerate(by_wire):w.writerow([i,i,r['wr_id'],r['jetty_id'],r['sequence'],r['enqueue_ps'],r['dispatch_ps'],r['tx_start_ps'],(r['tx_start_ps']-r['dispatch_ps'])/1000])
    return result,wr

def compress(path):
    import shutil
    with path.open('rb') as src,lzma.open(str(path)+'.xz','wb',preset=6) as dst:shutil.copyfileobj(src,dst)
    path.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',default='build-ingress/trace_e2e');p.add_argument('--output',default='experiments/ingress/output');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);binary=Path(a.binary).resolve();cases=[];permutation_checks=[]
    traces=out/'traces';traces.mkdir(exist_ok=True)
    for scenario in SCENARIOS:
        original=Path('experiments/phase1/output/traces')/(scenario+'.csv');rows=read_trace(original)
        for permutation in PERMUTATIONS:
            trace=traces/(scenario+'_'+permutation+'.csv');write_trace(trace,permute(rows,permutation))
            if permutation=='original':assert trace.read_bytes()==original.read_bytes()
            permutation_checks.append({'scenario':scenario,'permutation':permutation,'trace_sha256':digest(trace),'wr_fields_and_local_sequence_unchanged':True})
            for mode in MODES:
                for policy in POLICIES:
                    directory=out/scenario/permutation/mode/policy
                    simulate(binary,trace,directory,policy,mode)
                    if permutation=='original' and mode=='csv':
                        for name in ('systemc.events.csv','systemc.wr.csv'):
                            assert digest(directory/name)==digest(Path('experiments/phase2/output')/scenario/policy/name)
                    info,wr=inspect_run(directory,mode)
                    cases.append({'scenario':scenario,'permutation':permutation,'mode':mode,'policy':policy,'directory':directory,'inspection':info,'wr':wr})
                    print('PASS simulation + causal checks:',scenario,permutation,mode,policy,flush=True)
    dump(out/'permutation_checks.json',permutation_checks)
    # Predeclared primary rule: longest all-Jetty queued interval common to ALL
    # 36 cases, across both workloads, all permutations, policies and modes.
    window=common_backlogged_window([c['directory'] for c in cases])
    dump(out/'window.json',{'rule':'longest intersection across all 36 runs of strictly positive per-Jetty scheduler queues; inward ns rounding; earliest tie',
                          'primary_window_ns':window,'valid':window is not None,'cases':len(cases),
                          'phase2_diagnostic_windows_ns':{'moe_high':[1938,104637],'moe_skew':[947,38738]}})
    results=[]
    for case in cases:
        d=case['directory'];r=analyze(d,*(window or (0,1)));r.update({k:case[k] for k in ['scenario','permutation','mode','policy']})
        if window is None:r['fairness'].update(wire_jain=None,payload_jain=None,valid_all_jetties_backlogged=False)
        else:assert r['fairness']['valid_all_jetties_backlogged']
        r['fairness']['scope']='same single window across all 36 runs'
        full_wire=defaultdict(int);full_payload=defaultdict(int)
        for row in case['wr'].values():full_wire[row['jetty_id']]+=64+row['payload_bytes'];full_payload[row['jetty_id']]+=row['payload_bytes']
        r['full_run']={'wire_bytes':dict(full_wire),'payload_bytes':dict(full_payload),'wire_jain':jain(list(full_wire.values())),
                       'payload_jain':jain(list(full_payload.values())),'wire_share':{j:v/sum(full_wire.values()) for j,v in full_wire.items()},
                       'payload_share':{j:v/sum(full_payload.values()) for j,v in full_payload.items()},
                       'meaning':'complete finite offered volume; all WRs finish, so full-run share cannot diagnose transient service imbalance'}
        r['timeline']=case['inspection'];dump(d/'metrics.json',r);results.append(r)
        print('PASS unified metrics:',case['scenario'],case['permutation'],case['mode'],case['policy'],flush=True)
    # The controlled mode must be invariant per WR across all three permutations.
    for scenario in SCENARIOS:
        for policy in POLICIES:
            selected=[c for c in cases if c['scenario']==scenario and c['policy']==policy and c['mode']=='epoch-rr']
            assert all(c['wr']==selected[0]['wr'] for c in selected)
    repeats=[]
    with tempfile.TemporaryDirectory() as tmp:
        for case in [c for c in cases if c['scenario']=='moe_high' and c['permutation']=='original' and c['mode']=='epoch-rr']:
            d=Path(tmp)/case['policy'];simulate(binary,traces/'moe_high_original.csv',d,case['policy'],'epoch-rr')
            for name in ('systemc.events.csv','systemc.wr.csv','systemc.timeline.csv'):
                h=digest(d/name);assert h==digest(case['directory']/name)
                repeats.append({'policy':case['policy'],'file':name,'sha256':h})
    dump(out/'determinism.json',repeats);dump(out/'summary.json',results)
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['scenario','permutation','mode','policy','wire_jain','payload_jain','full_wire_jain','payload_gbps','makespan_ns','p50_ns','p99_ns','scheduler_wait_p50_ns','scheduler_wait_p99_ns','initial_wire_jetty','initial_same_jetty_wire_count'])
        for r in results:w.writerow([r['scenario'],r['permutation'],r['mode'],r['policy'],r['fairness']['wire_jain'],r['fairness']['payload_jain'],r['full_run']['wire_jain'],r['payload_throughput_gbps'],r['makespan_ns'],r['ready_to_complete_ns']['p50'],r['ready_to_complete_ns']['p99'],r['scheduler_wait_ns']['p50'],r['scheduler_wait_ns']['p99'],r['timeline']['initial_wire_jetty'],r['timeline']['initial_same_jetty_wire_count']])
    with (out/'per_jetty.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['scenario','permutation','mode','policy','jetty','window_wire_share','window_payload_share','full_wire_share','full_payload_share','p50_ns','p99_ns','scheduler_wait_p50_ns','scheduler_wait_p99_ns'])
        for r in results:
            for j,m in r['per_jetty'].items():
                jet=int(j);wire=r['fairness']['wire_bytes'];payload=r['fairness']['payload_bytes']
                w.writerow([r['scenario'],r['permutation'],r['mode'],r['policy'],j,wire[jet]/sum(wire.values()) if window else '',payload[jet]/sum(payload.values()) if window else '',r['full_run']['wire_share'][jet],r['full_run']['payload_share'][jet],m['ready_to_complete_ns']['p50'],m['ready_to_complete_ns']['p99'],m['scheduler_wait_ns']['p50'],m['scheduler_wait_ns']['p99']])
    manifest=[]
    for c in cases:
        for name in ('systemc.events.csv','systemc.timeline.csv'):
            path=c['directory']/name;record={'path':str(path.relative_to(out))+'.xz','uncompressed_sha256':digest(path)}
            compress(path);record['compressed_sha256']=digest(Path(str(path)+'.xz'));manifest.append(record)
        print('Saved lossless raw events:',c['scenario'],c['permutation'],c['mode'],c['policy'],flush=True)
    dump(out/'raw_events_manifest.json',manifest)
    print('PASS: 36 simulations, exact default Phase2 projection, permutation invariance, three deterministic repeats; common window',window,flush=True)
if __name__=='__main__':main()
