#!/usr/bin/env python3
"""Execute exactly one bounded Qwen256 simulator measurement on materialized inputs.
Never prepares inputs, changes runtime/model settings, or weakens guards.
"""
import argparse, hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path
H=Path(__file__).resolve().parent; REPO=H.parents[1]; WORK=REPO.parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--case',choices=['chunk-streaming','direct','no-balancing'],required=True);p.add_argument('--variant',choices=['control','sampled','timed'],required=True);p.add_argument('--binary',type=Path);p.add_argument('--input-dir',type=Path);p.add_argument('--hz',type=int,default=19);a=p.parse_args()
 a.raw=a.raw.resolve(); out=a.raw/'runtime'/f'{a.case}-{a.variant}'
 if out.exists():raise RuntimeError('Refusing existing run directory '+str(out))
 if shutil.disk_usage(a.raw).free<8*1024**3:raise RuntimeError('disk guard before launch')
 inp=a.input_dir or (WORK/'qwen-model-size-raw/scan/tokens-256/chunk-streaming/run' if a.case=='chunk-streaming' else a.raw/'inputs'/a.case)
 binary=(a.binary or WORK/'qwen-model-size-raw/build-capacity-v2/pair-layer').resolve()
 out.mkdir(parents=True);(out/'run').mkdir();env=dict(os.environ,LC_ALL='C.UTF-8')
 cmd=[str(binary),'--input='+str(inp/'input.txt'),'--out='+str(out/'run'),'--capacityMetrics='+str(out/'run/simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary','--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000']
 if a.variant=='sampled':cmd=[str(a.raw/'aux/record'),str(out/'perf.data'),str(a.hz),'--']+cmd
 if a.variant=='timed':env.update(QWEN_CPU_PROFILE='1',QWEN_CPU_PROFILE_OUT=str(out/'timing.json'),QWEN_PROFILE_HISTORY=str(out/'timing-history.jsonl'))
 provenance=dict(case=a.case,variant=a.variant,input_directory=str(inp),input_sha256=sha(inp/'input.txt'),binary=str(binary),binary_sha256=sha(binary),command=cmd,settings='accepted summary/pair full validation; no input regeneration',sampling_hz=a.hz if a.variant=='sampled' else None)
 (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 r=run(cmd,out/'host',300,cwd=WORK,case=out,env=env)
 (out/'status.json').write_text(json.dumps(dict(status=r['status'],guard=r['guard'],complete=(out/'run/online-summary.json').exists()),indent=2)+'\n')
 # Timeout is deliberately retained as partial evidence, not promoted to PASS.
 print(json.dumps({'run':str(out),'status':r['status'],'guard':r['guard']}))
if __name__=='__main__':main()
