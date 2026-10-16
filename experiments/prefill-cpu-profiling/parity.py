#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
from execute import H,REPO,WORK,RAW,env,hashes
from guard import run
results=[]
for mode in ['no-balancing','chunk-streaming']:
 source=REPO/'experiments/multi-npu-relay/evidence/fixed64'/mode;records={}
 for tag in ['baseline','timed-disabled','timed']:
  out=RAW/'small-parity'/mode/tag
  if out.exists():raise RuntimeError('existing parity output')
  out.mkdir(parents=True);en=env();binary=RAW/'baseline-binaries/ns3.44-multi-npu-relay'
  if tag!='baseline':binary=WORK/'prefill-cpu-native/build/scratch/ns3.44-multi-npu-relay';en['LD_LIBRARY_PATH']=str(WORK/'prefill-cpu-native/build/lib')
  if tag=='timed':en.update(NATIVE_CPU_PROFILE='1',NATIVE_CPU_PROFILE_DETAIL='1',NATIVE_CPU_PROFILE_OUT=str(out.parent/'timing.tsv'))
  r=run([binary,'--input='+str(source/'input.txt'),'--out='+str(out)],out.parent/(tag+'-host'),60,case=out,env=en)
  if r['status']!='PASS':raise RuntimeError('parity failed')
  records[tag]=hashes(out)
 results.append(dict(mode=mode,all_files_byte_identical=records['baseline']==records['timed-disabled']==records['timed'],files=records))
 if not results[-1]['all_files_byte_identical']:raise RuntimeError('parity mismatch')
(H/'evidence/small-parity.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS complete small no-balancing and relay timeline/WQE/TA/payload byte parity')
