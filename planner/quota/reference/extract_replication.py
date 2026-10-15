#!/usr/bin/env python3
"""Extract pinned placement solver; emulate CUDA collectives with CPU threads.
No replacement replication algorithm. See replication_adapter.cpp for boundaries.
"""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'placement.cu').read_text()
expected='195637d9d9b0ce37656dcccbd7f487202699fbda0f11c41c431f71b38f01983f'
if hashlib.sha256(s.encode()).hexdigest()!=expected:raise RuntimeError('placement source hash mismatch')
helpers=s[s.index('static constexpr int MAX_EXPERTS_PER_NVL'):s.index('__device__ __noinline__ void build_rank_quota_prefix_slow')]
search=s[s.index('    const bool do_binary_search ='):s.index('    if (can_use_tma) {',s.index('    const int32_t* final_export_sum'))]
shared=s[s.index('    __shared__ int32_t smem_loads'):s.index('    for (int i = tid; i < E;',s.index('    __shared__ int32_t smem_loads'))]
shared='\n'.join(line for line in shared.splitlines() if 'ptx::' not in line)
# Observability only: log each oracle invocation, before its original body.
anchor='int batch_k = 1) {'
if helpers.count(anchor)!=1:raise RuntimeError('instrumentation anchor changed')
observed=helpers.replace(anchor,anchor+'\n    if (lane_id == 0) record_probe(threshold, use_dynamic_q_floor, STORE_PLAN);')
floor_line='effective_min_tokens = max(1, (need + feasible_slots - 1) / feasible_slots);'
if observed.count(floor_line)!=2:raise RuntimeError('dynamic floor anchors changed')
observed=observed.replace(floor_line,floor_line+'\n                        if (lane_id == 0) record_floor(threshold, min_tokens_per_replica, effective_min_tokens, need, feasible_slots);')
template=(R/'replication_adapter.cpp').read_text()
for marker,value in [('/*HELPERS*/',observed),('/*SHARED*/',shared),('/*SEARCH*/',search)]:
 if template.count(marker)!=1:raise RuntimeError('adapter marker')
 template=template.replace(marker,value)
(R/'generated_replication.cpp').write_text(template)
subprocess.run(['g++','-std=c++20','-O2','-pthread',str(R/'generated_replication.cpp'),'-o',str(R/'replication_cpu')],check=True)
manifest=dict(commit='94cab099b44fffa99a82fea99e7c12d89cf65e4f',source_sha256=expected,blocks={k:hashlib.sha256(v.encode()).hexdigest() for k,v in [('helpers',helpers),('search_and_materialization',search),('shared_without_ptx',shared)]},adapter_sha256=hashlib.sha256((R/'replication_adapter.cpp').read_bytes()).hexdigest(),adaptations=['CUDA attributes become empty macros','warp shuffle/sync and block sync use C++20 barriers, 128 CPU threads','single-domain contiguous-main input setup on host','lane-0 logging at oracle entry and both dynamic-floor assignments; no decision changes','search and X/U materialization body unchanged'],gpu_execution=False)
(R/'replication-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
