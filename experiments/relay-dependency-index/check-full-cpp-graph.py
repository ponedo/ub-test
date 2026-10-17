#!/usr/bin/env python3
"""Build/run a Read-only graph export and compare the accepted full Qwen graph."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw';N=W/'wqe-completion-native'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
assert subprocess.check_output(['git','-C',str(N),'rev-parse','HEAD^{tree}'],text=True).strip()=='c27d1faef570e6da9900a71aa0a37180a58dfba8'
subprocess.run(['git','-C',str(N),'diff','--exit-code'],check=True)
subprocess.run(['git','-C',str(N),'diff','--cached','--exit-code'],check=True)
assert shutil.disk_usage(W).free>=8*1024**3
out=R/'full-cpp-graph';out.mkdir(parents=True,exist_ok=True)
cmd=['c++','-std=c++20','-O3','-g',str(H/'read-graph.cc'),'-I'+str(N/'build/include'),'-L'+str(N/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(N/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',str(out/'read-graph')]
r=run(cmd,out/'build-host',300,case=R);assert r['status']=='PASS',r
accepted=W/'qwen-model-size-raw/scan/tokens-256/chunk-streaming/run';graph=out/'executed-transfers.csv'
r=run([out/'read-graph',accepted/'input.txt',graph,'index'],out/'read-host',300,case=R);assert r['status']=='PASS',r
expected=(accepted/'transfers.csv').read_bytes();actual=graph.read_bytes();assert actual==expected,'full ordered C++ graph mismatch'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(status='PASS',scope='Full production C++ Read indexed graph; no topology or simulator run',dependency_mode='index',input_sha256=sha(accepted/'input.txt'),accepted_graph_sha256=sha(accepted/'transfers.csv'),cpp_graph_sha256=sha(graph),byte_exact=True,transfers=len(actual.splitlines())-1,source_sha256={n:sha(H.parent/'pair-jetty'/n) for n in ['pair-layer.cc','online-validation.inc']},driver_sha256=sha(H/'read-graph.cc'),binary_sha256=sha(out/'read-graph'),resource={k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes','guard']})
(H/'cpp-full-graph-equality.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
