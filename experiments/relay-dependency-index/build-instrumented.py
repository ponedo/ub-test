#!/usr/bin/env python3
"""Build diagnostic copy under original resource guards; caller owns serial slot."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw';N=W/'wqe-completion-native'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
assert subprocess.check_output(['git','-C',str(N),'rev-parse','HEAD^{tree}'],text=True).strip()=='c27d1faef570e6da9900a71aa0a37180a58dfba8'
subprocess.run(['git','-C',str(N),'diff','--exit-code'],check=True)
subprocess.run(['git','-C',str(N),'diff','--cached','--exit-code'],check=True)
assert shutil.disk_usage(W).free>=8*1024**3
out=R/'instrumented';out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(H/'generate-instrumented.py'),'--out',str(out)],check=True)
cmd=['c++','-std=c++20','-O3','-g',str(out/'pair-layer.cc'),'-I'+str(N/'build/include'),'-L'+str(N/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(N/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',str(out/'pair-layer')]
r=run(cmd,R/'build-instrumented-host',300,case=R)
assert r['status']=='PASS',r
manifest=json.loads((out/'generation-manifest.json').read_text())
manifest['binary_sha256']=hashlib.sha256((out/'pair-layer').read_bytes()).hexdigest()
manifest['compile_command']=cmd
(out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(H/'instrumentation-source-proof.json').write_text((out/'instrumentation-source-proof.json').read_text())
