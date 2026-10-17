#!/usr/bin/env python3
"""One serialized Qwen256 measurement, exact accepted input and original guards."""
import argparse,json,os,sys,hashlib,shutil
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[2];R=W/'relay-dependency-index-raw'
sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--binary',type=Path,default=R/'build/pair-layer');p.add_argument('--dependency-mode',choices=['scan','index'],default='index');p.add_argument('--online-mode',choices=['scan','index'],default='index');p.add_argument('--timed',action='store_true');p.add_argument('--sampled',action='store_true');a=p.parse_args()
out=R/'runtime'/a.name;assert not out.exists();assert shutil.disk_usage(R).free>=8*1024**3
(out/'run').mkdir(parents=True);inp=W/'qwen-model-size-raw/scan/tokens-256/chunk-streaming/run/input.txt'
cmd=[str(a.binary),'--input='+str(inp),'--out='+str(out/'run'),'--capacityMetrics='+str(out/'run/simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000','--dependencyMode='+a.dependency_mode,'--onlineMembershipMode='+a.online_mode]
env=dict(os.environ,LC_ALL='C.UTF-8')
if a.timed:env.update(QWEN_CPU_PROFILE='1',QWEN_CPU_PROFILE_OUT=str(out/'timing.json'),QWEN_PROFILE_HISTORY=str(out/'timing-history.jsonl'))
if a.sampled:cmd=[str(W/'qwen-chunk-profile-raw/aux/record'),str(out/'perf.data'),'19','--']+cmd
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'provenance.json').write_text(json.dumps(dict(input=str(inp),input_sha256=sha(inp),binary=str(a.binary),binary_sha256=sha(a.binary),dependency_mode=a.dependency_mode,online_mode=a.online_mode,timed=a.timed,sampled=a.sampled,command=cmd),indent=2)+'\n')
r=run(cmd,out/'host',300,cwd=W,case=out,env=env)
(out/'status.json').write_text(json.dumps(dict(status=r['status'],guard=r['guard'],complete=(out/'run/online-summary.json').exists()),indent=2)+'\n')
