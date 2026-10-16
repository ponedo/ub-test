#!/usr/bin/env python3
import hashlib,json,tarfile
from pathlib import Path
from execute import H,RAW
archive=H.parent/'prefill-capacity/evidence/no-balancing-50000-raw.tar.gz'
files=['planner-input.json','measured-plan.json','run/input.txt','run/config.json','run/plan.json','run/assignments.csv','run/transfers.csv','run/graph-input.txt','run/weight-edges.csv'];hashes={};original_router=None
with tarfile.open(archive,'r|gz') as tar:
 for member in tar:
  name=member.name.removeprefix('no-balancing-50000/')
  if name not in files:continue
  f=tar.extractfile(member);data=f.read();hashes[name]=hashlib.sha256(data).hexdigest()
  if name=='planner-input.json':original_router=json.loads(data)
comparisons={name:dict(original_sha256=sha,dot_sha256=hashlib.sha256((RAW/'common-50000'/name).read_bytes()).hexdigest()) for name,sha in hashes.items()}
assert len(comparisons)==len(files),'missing original input artifact'
assert all(v['original_sha256']==v['dot_sha256'] for v in comparisons.values()),'original input differs'
prefix={}
for a in [5000,10000,20000,50000]:
 local=json.loads((RAW/f'common-{a}/planner-input.json').read_text());prefix[a]=local['mapping']==original_router['mapping'][:a//8]
assert all(prefix.values())
result=dict(source_archive=str(archive.relative_to(H.parents[1])),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),all_50k_input_files_identical=True,files=comparisons,router_trace_prefix_identical=prefix,router_seed=20261016,payload_seed=20261015)
(H/'evidence/original-input-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print('Original 50K inputs and all smaller router prefixes exactly match')
