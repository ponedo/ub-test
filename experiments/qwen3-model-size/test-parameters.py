#!/usr/bin/env python3
"""Official-shape and unchanged-input tests; no weights or inference needed."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent
c=json.loads((H/'config.json').read_text());f=json.loads((H/'fixed-config.json').read_text());p=f['application_parameters']
assert (c['hidden_size'],c['moe_intermediate_size'],c['num_experts'],c['num_experts_per_tok'])==(2048,768,128,8)
assert c['torch_dtype']=='bfloat16'
params=3*p['model_dim']*p['ff_dim'];weight=params*p['dtype_bytes'];payload=p['model_dim']*p['dtype_bytes'];flops=2*params
assert (params,weight,payload,flops)==(4718592,9437184,4096,9437184)
old=json.loads((H.parent/'ep64-token-scaling/fixed-config.json').read_text())
for key in ['npus','experts','top_k','jetty_mode','routing_seed','popularity','main_placement','slots','beta','min_replica_quota','planner_mode','relay_parameters','guards','normalized_planner_parameters']:
 assert f[key]==old[key],key
assert {k:v for k,v in p.items() if k not in ['model_dim','ff_dim','payload_budget_bytes','weight_task_limit']}=={k:v for k,v in old['application_parameters'].items() if k not in ['model_dim','ff_dim','payload_budget_bytes','weight_task_limit']}
# Executor uses integer picoseconds, including 100 ns setup per nonempty physical expert.
assert (flops*1000000)//(p['peak_gflops']*p['util_permille'])==18874368
assert weight//(3*64*128*2)==192 and payload//(64*2)==32
print(json.dumps({'status':'PASS','parameters_per_expert':params,'bf16_weight_bytes':weight,'assignment_payload_bytes_each_direction':payload,'gemm_flops_per_assignment':flops,'compute_ps_per_assignment':18874368,'compute_setup_ps':p['setup_ns']*1000,'unchanged_control_variables':True},indent=2))
