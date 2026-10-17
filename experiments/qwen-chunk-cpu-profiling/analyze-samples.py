#!/usr/bin/env python3
"""Decode exact retained ELF mappings and deliver compact sampling evidence."""
import argparse,importlib.util,json,shutil,sys
from pathlib import Path
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('accepted_perf_analysis',H.parent/'prefill-cpu-profiling/analyze.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--perf',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--calibration',action='store_true');a=p.parse_args()
s=m.analyze_perf(a.run/'perf.data',a.run/'analysis',a.perf)
a.out.mkdir(parents=True,exist_ok=False)
for name in ['self-top20.csv','inclusive-top20.csv','self-top20.svg','inclusive-top20.svg','summary.json','unknown-ips.csv']:
 shutil.copyfile(a.run/'analysis'/name,a.out/name)
patterns={'initialization_Read':'Layer::Read(', 'online_Audit':'Layer::Audit(', 'terminal_FinalAudit':'Layer::FinalAudit(', 'payload_Validate':'Layer::Validate(', 'submission_Send':'Layer::Send(', 'completion_Ready':'Layer::Ready(', 'native_WQE_Submit':'ns3::UbFunction::SubmitWqe(', 'native_TA':'ns3::UbTransaction::', 'packet':'ns3::Packet::', 'buffer':'ns3::Buffer::', 'simulator':'ns3::DefaultSimulatorImpl::'}
counts=dict.fromkeys(patterns,0);total=0;stacks={}
with (a.run/'analysis/perf-script.txt').open() as f:
 for sample in m.parse_samples(f):
  total+=1;labels=[x['label'] for x in sample['frames']]
  for key,pat in patterns.items():counts[key]+=int(any(pat in x for x in labels))
  stack=';'.join(reversed(labels));stacks[stack]=stacks.get(stack,0)+1
rows=[dict(category=k,samples=v,percent_of_samples=v*100/total if total else 0) for k,v in counts.items()]
m.write_csv(a.out/'observed-subtrees.csv',rows,['category','samples','percent_of_samples'])
(a.out/'callstacks-top20.json').write_text(json.dumps([dict(samples=n,stack=s.split(';')) for s,n in sorted(stacks.items(),key=lambda x:-x[1])[:20]],indent=2)+'\n')
(a.out/'measurement-caveats.json').write_text(json.dumps(dict(total=total,denominator='One captured user CPU-clock SAMPLE record. Inclusive categories overlap; do not sum.',counter_status='Unweighted sample counts; never static complexity-derived CPU percentages.',partial=None if a.calibration else not (a.run/'run/online-summary.json').exists(),workload='calibration' if a.calibration else 'simulator',source_binary='provenance.json and ELF manifest in raw run; no ELF substitution',subtrees=rows),indent=2)+'\n')
print(json.dumps({'sample_count':total,'unknown_self':s['unknown_self_samples'],'out':str(a.out)}))
