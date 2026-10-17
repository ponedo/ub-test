#!/usr/bin/env python3
"""Run both independent Python profiles serially under the unchanged accepted guards."""
import argparse,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;root=H.parents[2]
sys.path.insert(0,str(root/'experiments/wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args();a.raw.mkdir(parents=True,exist_ok=True)
commands={
'preparation':[root/'experiments/qwen3-model-size/prepare.py','--tokens','256','--out',a.raw/'prepared','--graph-tool',a.graph_tool],
'preflight':[root/'experiments/tiered-logging/preflight.py',a.input,'--graph-tool',a.graph_tool,'--out',a.raw/'preflight-result.json','--input-summary',a.raw/'input-summary.json','--provenance',root/'experiments/qwen3-model-size/fixed-config.json']}
ledger={}
for stage,cmd in commands.items():
 ledger[stage]=run([sys.executable,H/'profile_stage.py','--out',a.raw/stage]+cmd,a.raw/(stage+'-host'),300,case=a.raw)
 (a.raw/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 # A cProfile time-limit is coverage evidence; independent second profile remains useful.
 if ledger[stage]['guard'] not in (None,'wall_guard'):break
