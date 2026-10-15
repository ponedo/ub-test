"""Frozen functional coverage matrix; no performance tuning after outcomes."""
import json
from pathlib import Path
from adapter import DEFAULT

def from_loads(n,m,loads,slots=1,**params):
    c=dict(schema_version=1,npus=n,experts=n*m,top_k=1,main_placement=[x//m for x in range(n*m)],slots=[slots]*n,
           mapping=[dict(source=(i+x)%n,experts=[x]) for x,count in enumerate(loads) for i in range(count)],beta='1.01',min_replica_quota=1024)
    return c,params

def cases():
    c={
        'uniform4':from_loads(4,2,[4]*8),
        'single_replica4':from_loads(4,1,[8,0,4,4]),
        'multi_replica4':from_loads(4,1,[32,0,0,0]),
        'multi_expert8':from_loads(8,2,[20]*4+[0]*12,slots=2),
        'slots_zero4':from_loads(4,1,[32,0,0,0],slots=0),
        'nondivisible4':from_loads(4,1,[17,5,2,1],model_dim=65,ff_dim=129,segment_bytes=333),
        'target_delay4':from_loads(4,1,[8,0,4,4],weight_completion_ns=2000),
        'reroute_slow4':from_loads(4,1,[8,0,4,4],reroute_ns=100000),
        'two_matrix4':from_loads(4,1,[8,0,4,4],matrices=2),
        'empty4':from_loads(4,2,[0]*8),
    }
    p,params=from_loads(4,2,[0]*8,slots=2)
    p['top_k']=2;p['mapping']=[dict(source=0 if i<10 else 3,experts=[0,1]) for i in range(12)]
    c['uneven_sources4']=(p,params)
    p,params=from_loads(64,2,[0]*128)
    p['top_k']=2;p['mapping']=[dict(source=i%64,experts=[0,1+i%127]) for i in range(128)]
    c['fixed64']=(p,params)
    c['single_replica4_repeat']=c['single_replica4']
    return c

def write_package(root):
    root=Path(root);rows=[];commands=[]
    for name,(c,p) in cases().items():
        for mode in ['no-balancing','ultraep']:
            cid=name+'/'+mode;rows.append(dict(case_id=cid,block_id=name,role='control' if mode=='no-balancing' else 'treatment',case_dir='evidence/'+cid,changed_variable='balancing policy and its required overhead',fixed_controls='shared logical trace/network/model/per-assignment WQE',prediction='no guaranteed speedup; direct weights can dominate',checkpoint='stop on correctness failure; continue negative speedup'))
            commands.append(dict(case_id=cid,command='python3.12 ./ns3 run --no-build "direct-weight-forward --input={evidence}/'+cid+'/input.txt --out={evidence}/'+cid+'"'))
            d=root/'cases'/name/mode;d.mkdir(parents=True,exist_ok=True)
            (d/'experiment-spec.md').write_text('# '+cid+'\n\nCustom stateful WRITE/Transaction case in experiment-plan.md. Single-switch topology, explicit required-pair TP setup, detailed native/event trace.\n\nPlanner input:\n```json\n'+json.dumps(c,indent=2)+'\n```\n\nParameters (synthetic assumptions):\n```json\n'+json.dumps(dict(DEFAULT,**p),indent=2)+'\n```\n\nArtifacts: input.txt, config.json, plan.json, transfers.csv, assignments.csv, events.csv, summary.json, console.txt, native/runlog/.\n')
    # JSON is valid YAML, avoiding a runtime YAML package dependency.
    (root/'matrix.yaml').write_text(json.dumps(rows,indent=2)+'\n')
    (root/'command-manifest.yaml').write_text(json.dumps(commands,indent=2)+'\n')
    (root/'run-ledger.md').write_text('# Run ledger\n\nAll 26 runs pending. Continue full matrix unless correctness failure. See evidence/run-ledger.json for subsequent exact command/return code updates.\n')
if __name__=='__main__':write_package(Path(__file__).resolve().parent)
