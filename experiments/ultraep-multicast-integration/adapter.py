"""Reuse the accepted planner and direct edge emitter; add strategy identity only."""
import importlib.util,json
from pathlib import Path
H=Path(__file__).resolve().parent;E=H.parent
spec=importlib.util.spec_from_file_location('accepted_relay_adapter',E/'multi-npu-relay/adapter.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def emit(source,parameters,strategy,out):
 if strategy!='multicast-v2':return old.emit(source,parameters,strategy,out)
 c,plan=old.emit(source,parameters,'direct',out);out=Path(out);physical={p['id']:p for p in plan['physical']};groups={}
 for x in c['transfers']:
  if x['stage']!=2:continue
  e=physical[x['physical']]['expert'];g=groups.setdefault(e,dict(group=e+1,expert=e,source=x['source'],members=[]));g['members'].append(dict(task=x['task'],target=x['target'],physical=x['physical']))
 assert len(groups)<=128 and c['planner_input']['npus']<=64 and c['runtime']['segment_bytes']<=4096
 c['multicast_groups']=[groups[e] for e in sorted(groups)];c['weight_strategy']='multicast-v2'
 for key in ['runtime','parameters']:c[key]['weight_strategy']='multicast-v2'
 (out/'config.json').write_text(json.dumps(c,indent=2)+'\n')
 lines=(out/'input.txt').read_text().splitlines();z=lines[1].split();assert z[6]=='0';z[6]='4';lines[1]=' '.join(z);(out/'input.txt').write_text('\n'.join(lines)+'\n')
 lines=(out/'graph-input.txt').read_text().splitlines();z=lines[0].split();z[0]='4';lines[0]=' '.join(z);(out/'graph-input.txt').write_text('\n'.join(lines)+'\n')
 return c,plan

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--strategy',choices=['direct','chunk-streaming','multicast-v2'],required=True);a=p.parse_args()
 emit(a.source,json.loads((E/'qwen-prefill-token-scaling/fixed-config.json').read_text())['relay_parameters'],a.strategy,a.out)
