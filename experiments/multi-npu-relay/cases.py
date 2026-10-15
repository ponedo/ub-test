"""Fixed coverage cases; never tune after observing performance."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('direct_adapter',HERE.parent/'direct-weight-forward/adapter.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def loads(n,m,counts,slots=1):
 return dict(schema_version=1,npus=n,experts=n*m,top_k=1,main_placement=[x//m for x in range(n*m)],slots=[slots]*n,mapping=[dict(source=(i+x)%n,experts=[x]) for x,count in enumerate(counts) for i in range(count)],beta='1.01',min_replica_quota=1024)
def cases():
 single=loads(4,1,[8,0,4,4]);multi=loads(4,1,[32,0,0,0]);many=loads(8,2,[40]*4+[0]*12,slots=3)
 ep64=json.loads((HERE.parent/'direct-weight-forward/evidence/fixed64/ultraep/config.json').read_text())['planner_input']
 return {
 'single4':(single,{},{}),
 'multi4_force':(multi,{},dict(force_relay=True)),
 'multi8':(loads(8,1,[64]+[0]*7),{},{}),
 'multi_expert8':(many,{},dict(force_relay=True)),
 'chunk_lt_ta':(multi,{},dict(force_relay=True,chunk_bytes=512)),
 'chunk_eq_ta':(multi,{},dict(force_relay=True,chunk_bytes=1024)),
 'tail4':(multi,dict(model_dim=65,ff_dim=129,segment_bytes=333),dict(force_relay=True,chunk_bytes=2000)),
 'out_of_order4':(multi,{},dict(force_relay=True,reorder_ns=20000)),
 'public_chunk8':(loads(8,1,[64]+[0]*7),{},dict(chunk_bytes=262144)),
 'slots_zero4':(loads(4,1,[32,0,0,0],slots=0),{},{}),
 'fixed64':(ep64,{},{}),
 }
MODES=['no-balancing','direct','two-stage','chunk-streaming']
def package(root):
 rows=[];commands=[]
 for name,(c,p,r) in cases().items():
  for mode in MODES:
   cid=name+'/'+mode;rows.append(dict(case_id=cid,case_dir='evidence/'+cid,block=name,mode=mode,prediction='correctness and dependency invariants hold; no guaranteed speedup',checkpoint='stop correctness failure; retain negative performance'))
   commands.append(dict(case_id=cid,argv=['python3.12','./ns3','run','--no-build','multi-npu-relay --input={evidence}/'+cid+'/input.txt --out={evidence}/'+cid]))
   d=root/'cases'/name/mode;d.mkdir(parents=True,exist_ok=True)
   (d/'experiment-spec.md').write_text('# '+cid+'\n\nSame accepted single-switch network and compute. See experiment-plan.md.\n\n```json\n'+json.dumps(dict(planner_input=c,model_overrides=p,relay_overrides=r),indent=2)+'\n```\n')
 (root/'matrix.yaml').write_text(json.dumps(rows,indent=2)+'\n');(root/'command-manifest.yaml').write_text(json.dumps(commands,indent=2)+'\n')
 (root/'run-ledger.md').write_text('# Run ledger\n\n44 planned runs pending.\n')
if __name__=='__main__':package(HERE)
