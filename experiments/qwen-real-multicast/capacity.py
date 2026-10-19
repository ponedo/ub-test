#!/usr/bin/env python3
"""Static admission for this fixed experiment, pinned native sources and actual prepared plans."""
import argparse,json,hashlib,math
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--native',type=Path,required=True);a=p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in json.loads((E/'ub-concurrent-multicast/native-source-sha256.json').read_text()).items():assert sha(a.native/name)==digest,name
layers={}
for l in [0,37,52]:
 case=a.private/f'L{l}'/'multicast';d=case/'prepared/multicast-run';c=json.loads((d/'config.json').read_text());rt=c['runtime'];plan=json.loads((d/'plan.json').read_text());pre=json.loads((case/'preflight.json').read_text());assert pre['status']=='PASS'
 assert (rt['model_dim'],rt['ff_dim'],rt['dtype_bytes'],rt['weight_dtype_bytes'],rt['weight_bytes'],rt['segment_bytes'])==(4096,1536,2,1,18874368,1024)
 assert c['planner_input']['npus']==64 and c['planner_input']['experts']==128 and c['planner_input']['top_k']==8 and len(c['planner_input']['mapping'])==2048
 groups=c['multicast_groups'];weights=[t for t in c['transfers'] if t['stage']==2];assert len(groups)<=128 and len(weights)<=1000000
 assert len(c['assignments'])==16384 and len(c['transfers'])<2**31
 assert sorted(m['task'] for g in groups for m in g['members'])==sorted(t['task'] for t in weights)
 frame=0;hist={};max_tpn=0;max_jetty=0
 for g in groups:
  f=len(g['members']);assert 1<=f<=63 and len({m['target'] for m in g['members']})==f
  assert all(0<=m['target']<64 and m['target']!=g['source'] for m in g['members'])
  hist[str(f)]=hist.get(str(f),0)+1;frame=max(frame,1102 if f==1 else 32+137*f+1024)
 for t in weights:
  assert t['bytes']==18874368 and t['offset']==0
  max_tpn=max(max_tpn,64*64+2+2*t['task']);max_jetty=max(max_jetty,64*64+1+t['task'])
 logical=sum(t['bytes'] for t in c['transfers']);tas=sum((t['bytes']+1023)//1024 for t in c['transfers'])
 assert logical<=8*1024**3 and tas<2**32 and max_tpn<2**24 and max_jetty<2**24
 assert frame<=1048576 and frame<=524288 and (frame+159)//160<=6553
 layers[str(l)]=dict(groups=len(groups),replicas=len(weights),fanout_histogram=hist,max_frame_bytes=frame,max_frame_cells=(frame+159)//160,max_child_tpn=max_tpn,max_jetty=max_jetty,logical_payload_bytes=logical,logical_tas=tas,input_sha256=sha(d/'input.txt'),config_sha256=sha(d/'config.json'))
result=dict(status='PASS',scope='fixed configuration static admission; not a measured RSS or event-time result',layers=layers,native_source_files_verified=108,unchanged_limits=dict(groups=128,ingress_reserve_bytes=1048576,egress_bytes=524288,initial_credit_cells=6553,payload_budget_bytes=8*1024**3,weight_tasks=1000000))
(a.private/'capacity-approved.json').write_text(json.dumps(result,indent=2)+'\n');print('Static capacity PASS for all three layers')
