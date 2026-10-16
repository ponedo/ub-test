#!/usr/bin/env python3
"""Check capacity accounting and honest stop states; reuse unchanged strict verifier."""
import hashlib,json,subprocess,sys,tempfile,tarfile
from pathlib import Path
from guard import run
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1];OUT=ROOT/'evidence'
rows=json.loads((OUT/'capacity.json').read_text());ledger=json.loads((OUT/'run-ledger.json').read_text());checks=[]
for r in rows:
 assert r['requested_tokens']*8==r['requested_assignments']
 if r['input_tokens'] is not None:assert r['input_tokens']==r['requested_tokens'] and r['input_top_k']==8 and r['actual_generated_assignments']==r['requested_assignments']
 if r['strictly_verified']:
  d=OUT/'runs'/r['case_id'];s=json.loads((d/'summary.json').read_text());m=json.loads((d/'simulator-metrics.json').read_text())
  assert s['assignments']==r['requested_assignments'] and s['tokens']==r['requested_tokens']
  assert m['completed_tokens']==s['tokens']==r['unique_completed_tokens']
  assert m['sender_completions']==m['remote_WQEs']==r['actual_sender_completed_WQEs']==r['generated_remote_WQEs']
  assert r['actual_target_received_TAs']==r['expected_request_TAs']==s['target_segments']
  assert r['layer_latency_ps']==s['layer_latency_ps']
  assert s['verified_bytes'][0]==s['verified_bytes'][1]==s['assignments']*64*2
  assert s['verified_bytes'][2]==s['replicas']*49152
  assert r['max_task_id']<2**20 and r['partial_csv_rows_ignored']==0
  if r['mode']=='ultraep':assert s['readiness']=='upstream-group-chunk' and s['replicas']>0
  checks.append(r['case_id']+' strict verdict and independent scalar accounting consistent')
 elif r['status']=='failed':assert not r['strictly_verified'];checks.append(r['case_id']+' retained as failure, not counted as completed')
 else:assert r['ns3_wall_s'] is None;checks.append(r['case_id']+' unrun metrics unavailable')
paired={}
for r in rows:
 if r['strictly_verified']:
  summary=json.loads((OUT/'runs'/r['case_id']/'summary.json').read_text());key=r['requested_assignments']
  if key in paired:assert paired[key]==summary['combine_sha256']
  paired[key]=summary['combine_sha256']
for x in ledger:
 if x['status']=='failed' and x.get('failed_stage')=='ns3':assert 'verify' not in x['stages']
assert all(x['all_generated_files_byte_identical'] for x in json.loads((OUT/'parity-instrumented.json').read_text()))
reg=json.loads((OUT/'regression-resource.json').read_text());assert reg['status']=='PASS' and reg['returncode']==0
assert 'PASS: multi-NPU relay and all accepted regressions.' in (OUT/'regression-console.txt').read_text()
# Prove the host timeout path kills and records an actual live child without expensive work.
print('Expected timeout self-test follows; FAIL/wall_guard is the required child outcome')
with tempfile.TemporaryDirectory(prefix='capacity-guard-check-',dir='/tmp') as t:
 stopped=run([sys.executable,'-c','import time; time.sleep(5)'],t,wall=.2)
 assert stopped['status']=='FAIL' and stopped['guard']=='wall_guard' and stopped['returncode']<0
 (OUT/'guard-selftest.json').write_text(json.dumps(stopped,indent=2)+'\n')
for row in rows:
 archive=OUT/(row['case_id']+'-raw.tar.gz')
 if not archive.exists():continue
 expected=json.loads((OUT/'runs'/row['case_id']/'raw-artifacts.json').read_text());seen=set()
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar:
   if not member.isfile():continue
   prefix,relative=member.name.split('/',1);assert prefix==row['case_id'] and relative in expected
   stream=tar.extractfile(member);h=hashlib.sha256()
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
   assert member.size==expected[relative]['bytes'] and h.hexdigest()==expected[relative]['sha256'];seen.add(relative)
 assert seen==set(expected)
checks.append('all lossless raw archives match every original file hash, including failed run')
checks+=['byte-exact small parity','full old regression process succeeded','live child timeout path']
# No cap/algorithm/native edits: only this module and the optional executor counters.
changed=subprocess.check_output(['git','diff','555f2a591d7537b35fb507078dd686a50fb3400e','--name-only'],cwd=REPO,text=True).splitlines()
assert all(p.startswith('experiments/prefill-capacity/') or p=='experiments/multi-npu-relay/multi-npu-relay.cc' for p in changed)
assert 'uint64_t(t)*k<=100000' in (REPO/'experiments/multi-npu-relay/multi-npu-relay.cc').read_text()
(OUT/'checks.json').write_text(json.dumps(dict(success=True,checks=checks),indent=2)+'\n');print('PASS',len(checks),'capacity/stop/parity/regression checks')
