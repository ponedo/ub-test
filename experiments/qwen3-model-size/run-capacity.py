#!/usr/bin/env python3
"""Run smallest unchanged-guard capacity gate; never overrides safety checks."""
import argparse,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--lib',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args()
raw=a.raw.resolve();dest=raw/'tokens-256/prepared/no-balancing';env=dict(os.environ,LD_LIBRARY_PATH=str(a.lib.resolve()),RELAY_GRAPH_TOOL=str(a.graph_tool.resolve()))
preflight=[sys.executable,str(H.parent/'tiered-logging/preflight.py'),str(dest),'--graph-tool',str(a.graph_tool.resolve()),'--out',str(raw/'preflight.json'),'--input-summary',str(dest/'input-summary.json'),'--provenance',str(H/'fixed-config.json')]
ledger={}
for label,cmd in [('preflight',preflight),('simulator',[str(a.binary.resolve()),'--input='+str(dest/'input.txt'),'--out='+str(dest),'--logLevel=summary','--jettyMode=pair','--capacityMetrics='+str(dest/'simulator-metrics.json')]),('postflight',preflight+['--execution-summary',str(dest/'online-summary.json')])]:
 ledger[label]=run(cmd,raw/(label+'-host'),300,case=raw,env=env)
 (raw/'capacity-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 if ledger[label]['status']!='PASS':sys.exit(1)
assert json.loads((dest/'validation.json').read_text())['status']=='PASS'
print('NB CAPACITY PASS')
