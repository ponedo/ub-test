#!/usr/bin/env python3
"""Attribute shared map leaves by their observed callers, never by symbol name alone."""
import argparse,collections,importlib.util,json
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('analysis',H.parent/'prefill-cpu-profiling/analyze.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
phase=collections.Counter();low=collections.Counter();call=collections.Counter();native=collections.Counter();n=0
with (args.run/'analysis/perf-script.txt').open() as f:
 for sample in a.parse_samples(f):
  n+=1;labels=[x['label'] for x in sample['frames']]
  if not labels:continue
  name=next((x for x in ['Read','FinalAudit','Audit','Validate','Send','Ready'] if any('Layer::'+x+'(' in y for y in labels)),'Other')
  phase[name]+=1
  if '_M_lower_bound(' in labels[0] and 'std::pair<unsigned int const, unsigned int>' in labels[0]:
   low[name]+=1;caller=next((x for x in labels[1:] if x.startswith('Layer::') or x.startswith('ns3::Ub')),'unresolved');call[caller]+=1
  for pat in ['TryContinueJettyTransmission','EnqueueRtpWqe','MakeRtpTxQueueKey','ResolveWqeLifecycleLocalId','SubmitWqe','ProcessEvent']:
   native[pat]+=int(any(pat+'(' in x for x in labels))
obj=dict(samples=n,exclusive_phase_precedence=['Read','FinalAudit','Audit','Validate','Send','Ready','Other'],exclusive_sample_membership=dict(phase),uint32_to_uint32_map_lower_bound_self_samples_by_phase=dict(low),map_nearest_application_or_UB_caller=dict(call),native_inclusive_subtrees=dict(native),caveat='Unchanged-executable sample window. Phases partition by stack-pattern precedence, not timers. Shared map leaves use observed callstacks; native inclusive subtrees overlap callbacks and cannot be summed. Partial runs do not represent completed whole-run shares.')
args.out.write_text(json.dumps(obj,indent=2)+'\n');print(json.dumps(obj,indent=2))
