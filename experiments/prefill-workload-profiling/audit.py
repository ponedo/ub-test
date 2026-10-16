#!/usr/bin/env python3
"""Read-only source/capacity audit; never runs a planner or simulator."""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def run(out):
 out=Path(out);lock=json.loads((ROOT/'sources.lock.json').read_text())
 paths=['experiments/multi-npu-relay/multi-npu-relay.cc','experiments/multi-npu-relay/verify.py','experiments/direct-weight-forward/adapter.py','planner/quota/planner.py','planner/quota/upstream.py','planner/quota/reference/replication_adapter.cpp']
 sources={p:dict(sha256=hashlib.sha256((REPO/p).read_bytes()).hexdigest(),matches_base=(REPO/p).read_bytes()==subprocess.check_output(['git','show',lock['base_commit']+':'+p],cwd=REPO)) for p in paths}
 assert all(x['matches_base'] for x in sources.values()),'audited executor/planner differs from base'
 old=REPO/'experiments/multi-npu-relay/evidence/fixed64/chunk-streaming';s=json.loads((old/'summary.json').read_text())
 keys=['npus','tokens','assignments','replicas','weight_WQEs','weight_TAs','remote_WQEs','target_segments','weight_bytes','verified_bytes','layer_latency_ps']
 observed={k:s[k] for k in keys};observed['event_rows']=sum(1 for _ in (old/'events.csv').open())-1;observed['artifact_bytes']=sum(p.stat().st_size for p in old.rglob('*') if p.is_file());observed['new_execution']=False
 rows=[]
 for model,h,i in [('scaled',64,128),('qwen3',4096,1536)]:
  w=3*h*i*2
  for k in [2,8]:
   for r in [0,1,2,4,7,8,31,128]:
    remaining=256*1024**2-r*w
    cap=min(100000,100000//k,remaining//(2*k*h*2)) if remaining>=0 else -1
    rows.append(dict(model=model,H=h,I=i,dtype_bytes=2,matrices=3,top_k=k,replicas=r,expert_weight_bytes=w,weight_transfer_bytes=r*w,assignment_token_cap=100000//k,payload_token_cap=remaining//(2*k*h*2),combined_token_cap=cap,configuration_fits_even_at_zero_tokens=remaining>=0,extra_persistent_replica_buffer_bytes=r*w))
 with (out/'capacity-bounds.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
 (out/'executor-audit.json').write_text(json.dumps(dict(base=lock['base_commit'],sources=sources,existing_fixed64_evidence=observed,formula='A=T*k; checked bytes=2*A*H*dtype+R*W; retained payload arrays=2*A*H*dtype+2*R*W, excluding transient/native/Python overhead',limits=dict(assignments=100000,checked_payload_bytes=256*1024**2,expert_weight_bytes=64*1024**2,weight_tasks=20000,planner_assignments=2000000,cpu_reference_threads=128),EP64=dict(max_undirected_pairs=2016,max_directional_TPs=4032,host_plus_switch_nodes=65,ports=128),runtime_estimate=None),indent=2)+'\n')
 print('read-only executor audit: source hashes match base; algebraic capacity table written')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default=str(ROOT/'evidence'));run(p.parse_args().out)
