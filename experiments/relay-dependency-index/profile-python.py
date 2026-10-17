#!/usr/bin/env python3
"""Serial fixed256 scan/index stages under the unchanged accepted resource guards."""
import argparse, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--mode',choices=('scan','indexed'),required=True);a=p.parse_args();a.raw.mkdir(parents=True,exist_ok=True)
profile=ROOT/'experiments/qwen-chunk-cpu-profiling/python-stages/profile_stage.py'
commands={
'preparation':[ROOT/'experiments/qwen3-model-size/prepare.py','--tokens','256','--out',a.raw/'prepared','--graph-tool',a.graph_tool],
'preflight':[ROOT/'experiments/tiered-logging/preflight.py',a.input,'--graph-tool',a.graph_tool,'--dependency-mode',a.mode,'--out',a.raw/'preflight-result.json']}
env=dict(os.environ,RELAY_DEPENDENCY_MODE=a.mode);ledger={}
for stage,cmd in commands.items():
    ledger[stage]=run([sys.executable,profile,'--out',a.raw/stage]+cmd,a.raw/(stage+'-host'),300,case=a.raw,env=env)
    (a.raw/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    if ledger[stage]['guard'] not in (None,'wall_guard'):break
