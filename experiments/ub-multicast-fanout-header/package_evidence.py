#!/usr/bin/env python3
"""Publishable aggregate test evidence, never raw private resource snapshots/logs."""
import argparse,collections,hashlib,json,re,shutil
from pathlib import Path
X=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('private',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=a.private;o=a.out;o.mkdir(parents=True,exist_ok=True)
def load(path):return json.loads((r/path).read_text())
def save(name,value):(o/name).write_text(json.dumps(value,indent=2)+'\n')
def count(path):return dict(collections.Counter(x['status'] for x in load(path)))
for src,dst in [('header-tests/results.json','header-codec-tests.json'),('faults/results.json','fault-tests.json'),('legacy-parity/results.json','legacy-debug-parity.json'),('pressure/results.json','header-pressure-tests.json'),('pressure/source-provenance.json','header-pressure-provenance.json'),('build/binary-hashes.json','binary-hashes.json')]:shutil.copyfile(r/src,o/dst)
text=(r/'final-verifier-tests/console.txt').read_text();m=re.search(r'Ran (\d+) tests in ([\d.]+)s',text);assert m and '\nOK' in text
save('verifier-tests.json',dict(status='PASS',tests=int(m[1]),wall_unittest_seconds=float(m[2]),verifier_sha256=hashlib.sha256((X/'verify.py').read_bytes()).hexdigest(),test_source_sha256=hashlib.sha256((X/'test_verify.py').read_bytes()).hexdigest()))
native=load('regressions/native/summary.json');failed=[x for x in native if x['status']!='PASS'];assert len(native)==49 and [x['suite'] for x in failed]==['unified-bus-examples']
console=(r/'regressions/native/unified-bus-examples/console.txt').read_text();assert 'hasTaskTimes' in console
negative=load('regressions/network-collected/negative.json')
reg=dict(status='PASS_WITH_KNOWN_NATIVE_SUITE_FAILURE',native_suites=native,known_failure=dict(suite='unified-bus-examples',assertion='hasTaskTimes == true',source='src/unified-bus/test/ub-test.cc:36248',absent_dependency='scratch/ns-3-ub-tools/trace_analysis/parse_trace.py',later_child_tests='not claimed passed'),application_parity=load('regressions/application-parity.json'),concurrent=count('regressions/concurrent-results/results.json'),singleton_exact_pairs=len(load('regressions/singleton-results/results.json')),old_multicast=count('regressions/old-multi-results/results.json'),verifier_mutations=count('regressions/old-verifier-mutations/results.json'),network_positive=count('regressions/network-collected/results.json'),network_negative=negative,capacity_rejections=[])
for name in ['capacity','oversize']:
 h=load('regressions/'+name+'-host/resource.json');assert h['returncode']!=0 and h['guard'] is None
 reg['capacity_rejections'].append(dict(case=name,status='EXPECTED_REJECTION',returncode=h['returncode']))
save('regressions-summary.json',reg)
matrices={}
for phase,expected in [('small',25),('main',20),('ideal',5)]:
 rows=load('campaign/'+phase+'-ledger.json');assert len(rows)==expected and all(x['status']=='PASS' for x in rows)
 matrices[phase]=dict(completed=expected,passed=expected,protected_stops=0)
 for row in rows:
  for stage in ['simulator','postflight']:assert row[stage+'_host']['status']=='PASS' and row[stage+'_host']['guard'] is None
save('validation-summary.json',dict(status='PASS_WITH_KNOWN_NATIVE_SUITE_FAILURE',matrix=matrices,header_codec=count('header-tests/results.json'),application_faults=count('faults/results.json'),pressure=count('pressure/results.json'),legacy_debug_pairs=len(load('legacy-parity/results.json')),independent_verifier_tests=int(m[1]),native_pass=48,native_total=49,protocol_source_changed=False,coverage_note='Online validation retains all per-TA checks; Summary independent replay is per-WQE; bounded Debug independently replays TA and wire events.'))
print('AGGREGATE EVIDENCE PACKAGED')
