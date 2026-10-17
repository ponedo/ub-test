#!/usr/bin/env python3
"""Guarded complete Read A/B; graph export excluded from the Read phase."""
import csv,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw';N=W/'wqe-completion-native';out=R/'read-timed'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
assert subprocess.check_output(['git','-C',str(N),'rev-parse','HEAD^{tree}'],text=True).strip()=='c27d1faef570e6da9900a71aa0a37180a58dfba8'
subprocess.run(['git','-C',str(N),'diff','--exit-code'],check=True)
subprocess.run(['git','-C',str(N),'diff','--cached','--exit-code'],check=True)
assert shutil.disk_usage(W).free>=8*1024**3
out.mkdir(parents=True,exist_ok=True)
source=R/'instrumented/pair-layer.cc'
cmd=['c++','-std=c++20','-O3','-g','-DRELAY_INSTRUMENTED_SOURCE="'+str(source)+'"',str(H/'read-graph-timed.cc'),'-I'+str(N/'build/include'),'-L'+str(N/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(N/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',str(out/'read-graph-timed')]
r=run(cmd,out/'build-host',300,case=R);assert r['status']=='PASS',r
accepted=W/'qwen-model-size-raw/scan/tokens-256/chunk-streaming/run';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();expected=(accepted/'transfers.csv').read_bytes();rows=[];proof=[]
for mode in ['scan','index']:
 case=out/mode;case.mkdir();graph=case/'executed-transfers.csv'
 env=dict(os.environ,QWEN_CPU_PROFILE='1',QWEN_CPU_PROFILE_OUT=str(case/'timing.json'),QWEN_PROFILE_HISTORY='')
 r=run([out/'read-graph-timed',accepted/'input.txt',graph,mode],case/'host',300,case=case,env=env);assert r['status']=='PASS',r
 d=json.loads((case/'timing.json').read_text());assert d['complete'] and d['terminal'] and not d['failed'];assert graph.read_bytes()==expected
 ph=d['phases'];c=d['counters'];assert ph['Read']['completed_calls']==1 and ph['Read']['active_calls']==0
 rows.append(dict(mode=mode,read_cpu_seconds=ph['Read']['inclusive_cpu_ns']/1e9,dependency_cpu_seconds=ph['Read.dependencies']['inclusive_cpu_ns']/1e9,index_build_cpu_seconds=ph['Read.dependencies.index_build']['inclusive_cpu_ns']/1e9,program_cpu_seconds=ph['program']['inclusive_cpu_ns']/1e9,program_self_cpu_seconds=ph['program']['self_cpu_ns']/1e9,process_cpu_seconds=r['user_cpu_seconds']+r['system_cpu_seconds'],wall_seconds=r['wall_seconds'],peak_rss_kib=r['peak_rss_kib'],dependency_candidates=c['read_dependency_candidates'],dependency_edges=c['read_dependency_edges'],index_build_candidates=c['read_dependency_index_build_candidates'],complete=True))
 proof.append(dict(mode=mode,status='PASS',input_sha256=sha(accepted/'input.txt'),graph_sha256=sha(graph),byte_exact=True,transfers=len(expected.splitlines())-1,timing=d,resource={k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','guard']}))
 with (H/'cpp-read-timings.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 (H/'cpp-read-profile.json').write_text(json.dumps(dict(status='PASS' if len(proof)==2 else 'PARTIAL',binary_sha256=sha(out/'read-graph-timed'),driver_sha256=sha(H/'read-graph-timed.cc'),scope='Read includes index build; graph export excluded; no topology/simulation',generated_source_sha256={name:sha(R/'instrumented'/name) for name in ['pair-layer.cc','online-validation.inc','profile-runtime.h']},generation_manifest_sha256=sha(R/'instrumented/generation-manifest.json'),compile_command=cmd,runs=proof),indent=2)+'\n')
 print(json.dumps(rows[-1]),flush=True)
