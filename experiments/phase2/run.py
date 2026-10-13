"""Reproduce generic Trace -> SystemC -> measured evaluation; no workload logic in backend."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from simulators.nano_ub.run import prepare
from evaluation.analyze import analyze, common_backlogged_window

# Chosen for this fixed finite experiment, shared by all policies, never policy-tuned.
SCENARIOS={'synthetic_mixed':(2000,6000),'synthetic_equal':(2000,6000),
           'synthetic_burst':(2000,6000),'synthetic_poisson':(2000,6000),
           'moe_low':(2000,6000),'moe_high':(100000,500000),'moe_skew':(50000,200000)}
POLICIES=('fifo','rr','drr')

def run(binary,trace,directory,policy):
    inp=prepare(trace,directory,policy)
    with (directory/'systemc.log').open('w') as f:
        subprocess.run([str(binary),policy,str(inp),str(directory/'systemc')],stdout=f,stderr=subprocess.STDOUT,check=True)

def compare_baseline(directory,legacy,policy,load):
    with (legacy/f'{policy}_{load}.events.csv').open() as f:old=list(csv.DictReader(f))
    with (directory/'systemc.events.csv').open() as f:new=[r for r in csv.DictReader(f) if r['event'] not in ('ready','eligible')]
    assert old==[{k:r[k] for k in old[0]} for r in new],('raw event regression',policy,load)
    with (legacy/f'{policy}_{load}.wr.csv').open() as f:old_wr=list(csv.DictReader(f))
    with (directory/'systemc.wr.csv').open() as f:new_wr=list(csv.DictReader(f))
    assert old_wr==[{k:r['jetty_id' if k=='jetty' else k] for k in old_wr[0]} for r in new_wr],('WR regression',policy,load)
    return {'policy':policy,'load':load,'matched_events':len(old),'matched_wr':len(old_wr),'exact':True}

def generate(traces,output):
    traces.mkdir(parents=True,exist_ok=True)
    records=[]
    common=['--hidden-size','1024','--top-k','4','--experts','64','--ranks','8','--aivs','16','--seed','42']
    for name in SCENARIOS:
        if name.startswith('synthetic_'):
            args=['--seed','42']
            if name=='synthetic_equal':args+=['--sizes','256']
            if name in ('synthetic_burst','synthetic_poisson'):args+=['--arrival',name.removeprefix('synthetic_')]
            module='workloads.generators.synthetic'
        else:
            module='workloads.generators.moe_dispatch'
            size='32' if name=='moe_low' else '4096'
            args=common+['--tokens',size,'--capacity',size]
            if name=='moe_skew':args+=['--score-factor','2','--hot-rank','1']
        path=traces/(name+'.csv')
        subprocess.run([sys.executable,'-m',module,'--output',str(path),*args],check=True,capture_output=True,text=True)
        for suffix in ('','.meta.json')+ (('.moe.jsonl','.routes.jsonl') if name.startswith('moe_') else ()):
            data=Path(str(path)+suffix).read_bytes()
            assert data==Path('experiments/phase1/output/traces/'+name+'.csv'+suffix).read_bytes(),('generator drift',name,suffix)
            records.append({'file':path.name+suffix,'sha256':hashlib.sha256(data).hexdigest(),'matches_phase1':True})
    (output/'generator_comparison.json').write_text(json.dumps(records,indent=2)+'\n')
    print('PASS 7 regenerated traces and sidecars exactly match Phase1',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',default='build-phase2/trace_e2e');p.add_argument('--output',default='experiments/phase2/output');a=p.parse_args()
    binary=Path(a.binary).resolve();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    traces=out/'traces';generate(traces,out)
    all_results=[];baseline=[];repeats=[]
    for scenario,window in SCENARIOS.items():
        results=[]
        for policy in POLICIES:
            directory=out/scenario/policy
            run(binary,traces/(scenario+'.csv'),directory,policy)
            result=analyze(directory,*window);result['scenario']=scenario;results.append(result)
            if scenario in ('synthetic_mixed','synthetic_equal'):
                baseline.append(compare_baseline(directory,Path('eval/e2e'),policy,scenario.removeprefix('synthetic_')))
            print('PASS',scenario,policy,result['wr_count'],flush=True)
        if scenario.startswith('moe_'):
            common_window=common_backlogged_window([out/scenario/p for p in POLICIES])
            if common_window:
                results=[]
                for policy in POLICIES:
                    result=analyze(out/scenario/policy,*common_window)
                    result['scenario']=scenario
                    result['fairness']['selection']='longest common all-Jetty queued interval; inward integer-ns rounding'
                    result['fairness']['initial_diagnostic_window_ns']=list(window)
                    results.append(result)
            else:
                for result in results:result['fairness']['selection']='no common all-Jetty queued interval exists'
        common=all(r['fairness']['valid_all_jetties_backlogged'] for r in results)
        for r in results:
            r['fairness']['valid_common_policy_window']=common
            if not common:
                r['fairness']['wire_jain']=r['fairness']['payload_jain']=None
                r['fairness']['invalid_reason']='not continuously backlogged for every active Jetty under every compared policy'
            (out/scenario/r['policy']/'metrics.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
        all_results.extend(results)
    # Re-run the high case for every policy; hash exact raw event and WR output.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for policy in POLICIES:
            d=Path(tmp)/policy;run(binary,traces/'moe_high.csv',d,policy)
            for name in ('systemc.events.csv','systemc.wr.csv'):
                def sha(path):
                    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
                h=sha(d/name);assert h==sha(out/'moe_high'/policy/name)
                repeats.append({'scenario':'moe_high','policy':policy,'file':name,'sha256':h})
    (out/'summary.json').write_text(json.dumps(all_results,indent=2,sort_keys=True)+'\n')
    (out/'baseline_comparison.json').write_text(json.dumps(baseline,indent=2)+'\n')
    (out/'determinism.json').write_text(json.dumps(repeats,indent=2)+'\n')
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['scenario','policy','wr_count','payload_bytes','makespan_ns','payload_gbps','ready_p50_ns','ready_p99_ns','queue_wait_p50_ns','queue_wait_p99_ns','common_backlogged_window','wire_jain','payload_jain'])
        for r in all_results:
            w.writerow([r['scenario'],r['policy'],r['wr_count'],r['payload_bytes'],r['makespan_ns'],r['payload_throughput_gbps'],
                       r['ready_to_complete_ns']['p50'],r['ready_to_complete_ns']['p99'],r['queue_wait_ns']['p50'],r['queue_wait_ns']['p99'],
                       r['fairness']['valid_common_policy_window'],r['fairness']['wire_jain'],r['fairness']['payload_jain']])
    with (out/'per_jetty.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['scenario','policy','jetty','wr_count','payload_bytes','payload_gbps','ready_p50_ns','ready_p99_ns','queue_p50_ns','queue_p99_ns'])
        for r in all_results:
            for j,m in r['per_jetty'].items():w.writerow([r['scenario'],r['policy'],j,m['wr_count'],m['payload_bytes'],m['payload_throughput_gbps'],m['ready_to_complete_ns']['p50'],m['ready_to_complete_ns']['p99'],m['queue_wait_ns']['p50'],m['queue_wait_ns']['p99']])
    print('PASS 21 trace simulations, 6 exact legacy comparisons, 3 high-trace repeat checks')
if __name__=='__main__':main()
