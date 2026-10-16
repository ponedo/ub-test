#!/usr/bin/env python3
import csv,json
from pathlib import Path
from execute import H,RAW
j=lambda p:json.loads(p.read_text())
summary=j(H/'evidence/analysis/summary.json');ledger=j(H/'evidence/run-ledger.json');checks={}
checks['all_12_formal_runs_succeeded']=all(any(r['assignments']==a and r['variant']==v and r['status']=='success' for r in ledger) for a in [5000,10000,20000,50000] for v in ['baseline','sampled','timed'])
checks['complete_analysis']=summary['complete_matrix']
checks['all_scale_outputs_byte_identical']=all(r['all_output_files_byte_identical'] and r['input_hashes_match'] for r in summary['output_hash_comparisons'])
checks['small_nb_and_relay_parity']=all(r['all_files_byte_identical'] for r in j(H/'evidence/small-parity.json'))
checks['all_native_elf_unchanged_during_measurement']=all(r['all_unchanged'] for r in j(H/'evidence/binary-hashes-after.json').values())
for a in [5000,10000,20000,50000]:
 s=j(H/f'evidence/analysis/{a}-sampled/summary.json')
 checks[f'{a}_sampling_counts_match']=s['sample_count']>0 and s['sample_count']==s['records']['SAMPLE']==s['recorder']['samples']
 checks[f'{a}_one_pid_tid_observed']=len(s['pid_tid_scope'])==1
 checks[f'{a}_no_lost_or_throttle_records']=all(s['records'].get(k,0)==0 for k in ['LOST','LOST_SAMPLES','THROTTLE','UNTHROTTLE'])
 folded=H/f'evidence/analysis/{a}-sampled/stacks-count.folded'
 if not folded.exists():folded=RAW/f'analysis-raw/{a}-sampled/stacks-count.folded'
 checks[f'{a}_folded_counts_match']=sum(int(line.rsplit(' ',1)[1]) for line in folded.read_text().splitlines())==s['sample_count']
 t=j(H/f'evidence/analysis/{a}-timed/summary.json');timers={x['name']:x for x in t['timers']}
 checks[f'{a}_timer_clock_no_errors']=t['counters']['ClockErrors']==0
 checks[f'{a}_shared_timer_owner_worked']=timers['AppRun']['calls_or_count']==1 and timers['AppLayerDestroy']['calls_or_count']==1 and timers['CreateJettyBound']['calls_or_count']>0
 checks[f'{a}_lifecycle_candidate_calls_match']=t['counters']['LifecycleCandidates']==timers['ResolveWqeLifecycleLocalId']['calls_or_count']
 checks[f'{a}_tpn_comparison_counts_consistent']=t['counters']['TpnLookupJettyRecordsScanned']==t['counters']['TpnLookupTransportEntriesCompared']==t['counters']['TpnLookupLiveTransportVectorSlots']
result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks)
(H/'evidence/checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(not all(checks.values()))
