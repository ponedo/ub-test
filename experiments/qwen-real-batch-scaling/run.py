#!/usr/bin/env python3
"""Strict ascending size gates; no advancement without all nine verified cases."""
import argparse,json,os,sys,subprocess
from pathlib import Path
X=Path(__file__).resolve().parent
sys.path.insert(0,str(X.parent/'wqe-completion-fix'))
from guard import run
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--lib',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--frozen-counts',type=Path,required=True);a=p.parse_args()
root=a.private.resolve();root.mkdir(parents=True,exist_ok=True)
if (root/'scaling-status.json').exists():raise RuntimeError('refuse restart/overwrite existing run')
status={'status':'RUNNING','completed_sizes':[]}
def save():(root/'scaling-status.json').write_text(json.dumps(status,indent=2)+'\n')
save()
try:
 for n in [512,1024,2048]:
  status['current_size']=n;save();out=root/f'tokens-{n}';out.mkdir();(out/'routing').mkdir()
  for layer in [0,37,52]:
   cmd=[sys.executable,X.parent/'qwen-real-minimal/extract_routing.py','--manifest',a.source_manifest,'--frozen-counts',a.frozen_counts,'--layer',layer,'--tokens',n,'--out',out/'routing'/f'layer_{layer}.json','--audit-out',out/'source-audits'/f'layer-{layer}']
   result=run(cmd,out/'extraction-host'/f'layer-{layer}',3600,case=root)
   if result['status']!='PASS':raise RuntimeError('protected extraction stop')
  cmd=[sys.executable,X/'run_size.py','--private',out,'--tokens',n,'--binary',a.binary,'--lib',a.lib,'--graph-tool',a.graph_tool,'--source-manifest',a.source_manifest,'--frozen-counts',a.frozen_counts]
  with (out/'driver.log').open('w') as f:r=subprocess.run([str(v) for v in cmd],stdout=f,stderr=subprocess.STDOUT)
  if r.returncode and not (r.returncode==3 and n==2048 and (out/'scope-boundary.json').exists()):raise RuntimeError(f'size {n} stopped; see driver.log and resource evidence')
  rows=json.loads((out/'runs.json').read_text());expected={(l,s) for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming']}
  assert len(rows)==9 and {(r['layer'],r['strategy']) for r in rows}==expected
  assert all(r['status']=='PASS' and r['validation']['status']=='PASS' and all(r[k]['status']=='PASS' for k in ['preparation_host','preflight_host','simulator_host','postflight_host']) for r in rows)
  for l in [0,37,52]:assert len({r['routing_sha256'] for r in rows if r['layer']==l})==1
  status['completed_sizes'].append(n);save();print('SIZE VERIFIED',n,flush=True)
 status['status']='PASS'
except Exception as e:status.update(status='STOPPED',reason=str(e));raise
finally:save()
