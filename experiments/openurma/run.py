# SPDX-License-Identifier: Apache-2.0
"""Run generated native/fixed-RR/DRR modules and retain upstream failure evidence."""
import argparse,json,subprocess,tempfile,hashlib
from pathlib import Path
from experiments.openurma.analyze import analyze

def run(binary,policy,scenario,order,d):
    d.mkdir(parents=True,exist_ok=True)
    with (d/'run.txt').open('w') as f:
        r=subprocess.run([str(binary),policy,scenario,order,str(d/'component')],stdout=f,stderr=subprocess.STDOUT,timeout=30)
    return r.returncode

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',required=True);p.add_argument('--patched',required=True);p.add_argument('--output',default='experiments/openurma/results');a=p.parse_args();root=Path(a.output);records=[]
    native_expected_failures={'overflow','stall','equal','mixed'}
    for variant,binary,policies in [('native',Path(a.native),['rr']),('patched',Path(a.patched),['rr','drr'])]:
        for policy in policies:
            for scenario in ['smoke','fence','overflow','large','delayed_ext','stall','equal','mixed']:
                for order in (['forward','reverse'] if scenario in ['equal','mixed'] else ['forward']):
                    d=root/variant/policy/scenario/order;rc=run(binary,policy,scenario,order,d)
                    expected=variant=='native' and scenario in native_expected_failures
                    assert (rc!=0)==expected,(variant,policy,scenario,order,rc)
                    if expected:assert 'FAIL:' in (d/'run.txt').read_text()
                    records.append({'variant':variant,'policy':policy,'scenario':scenario,'order':order,'returncode':rc,'expected_native_failure':expected})
                    print('EXPECTED NATIVE FAILURE' if expected else 'PASS',variant,policy,scenario,order,flush=True)
    comparisons=[]
    for scenario in ['smoke','fence','large','delayed_ext']:
        for name in ['events.csv','wr.csv','queues.csv']:
            left=root/'native/rr'/scenario/'forward'/('component.'+name);right=root/'patched/rr'/scenario/'forward'/('component.'+name)
            assert left.read_bytes()==right.read_bytes();comparisons.append({'scenario':scenario,'file':name,'exact':True})
    repeats=[]
    with tempfile.TemporaryDirectory() as tmp:
        for policy in ['rr','drr']:
            d=Path(tmp)/policy;assert run(Path(a.patched),policy,'mixed','forward',d)==0
            for name in ['events.csv','wr.csv','queues.csv']:
                path=d/('component.'+name);old=root/'patched'/policy/'mixed/forward'/path.name
                assert path.read_bytes()==old.read_bytes();repeats.append({'policy':policy,'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for name,obj in [('runs.json',records),('native_rr_comparison.json',comparisons),('determinism.json',repeats)]:
        (root/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    analyze(root)
    print('PASS: 4 native checks; 6 expected native failure reproductions; 20 patched RR/DRR checks; 12 byte-identical RR comparisons; 2 deterministic repeats')
if __name__=='__main__':main()
