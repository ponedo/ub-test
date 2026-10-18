import sys,os,json,importlib.util
from pathlib import Path
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--private',type=Path,required=True);parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--lib',type=Path,required=True);parser.add_argument('--graph-tool',type=Path,required=True);args=parser.parse_args()
E=Path(__file__).resolve().parent.parent;root=args.private.resolve();root.mkdir(exist_ok=False,parents=True)
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
sys.path.insert(0,str(E/'multi-npu-relay'));import cases;import adapter as relay
base=cases.base;env=dict(os.environ,LD_LIBRARY_PATH=str(args.lib.resolve()),RELAY_GRAPH_TOOL=str(args.graph_tool.resolve()));os.environ.update(env);rows=[]
prepared=root/'prepared'
r=run([sys.executable,E/'ep64-token-scaling/prepare.py','--tokens',256,'--out',prepared,'--graph-tool',args.graph_tool],root/'preparation-host',3600,case=root,env=env);assert r['status']=='PASS'
for mode in ['no-balancing','direct','chunk-streaming']:
 case=root/mode;case.mkdir();dest=prepared/mode
 cmd=[sys.executable,E/'tiered-logging/preflight.py',dest,'--graph-tool',args.graph_tool,'--out',case/'pre.json','--input-summary',dest/'input-summary.json']
 r=run(cmd,case/'pre-host',3600,case=root,env=env);assert r['status']=='PASS'
 r=run([args.binary,'--input='+str(dest/'input.txt'),'--out='+str(dest),'--capacityMetrics='+str(dest/'simulator-metrics.json'),'--jettyMode=pair','--logLevel=summary'],case/'sim-host',3600,case=root,env=env);assert r['status']=='PASS'
 r=run(cmd+['--execution-summary',dest/'online-summary.json'],case/'post-host',3600,case=root,env=env);assert r['status']=='PASS'
 v=json.loads((dest/'validation.json').read_text());s=json.loads((dest/'online-summary.json').read_text());assert v['status']=='PASS'
 rows.append(dict(strategy=mode,status='PASS',validation=v,summary=s));(root/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print('ZIPF N256 THREE STRATEGY PASS')
