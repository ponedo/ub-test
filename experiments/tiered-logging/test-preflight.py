#!/usr/bin/env python3
"""Small input-contract tamper tests; no simulator or protocol changes."""
import argparse,importlib.util,json,tempfile,shutil
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('preflight',H/'preflight.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=argparse.ArgumentParser();a.add_argument('--case',type=Path,required=True);a.add_argument('--graph-tool',type=Path,required=True);a.add_argument('--out',type=Path);args=a.parse_args()
results=[]
with tempfile.TemporaryDirectory(prefix='preflight-test-') as td:
    root=Path(td)
    def reset():
        for name in ('input.txt','config.json','plan.json'):shutil.copy2(args.case/name,root/name)
    reset();m.check(root,args.graph_tool);results.append(dict(case='valid',status='PASS'))
    for case in ['input-seed','assignment-identity','physical-quota','transfer-size','transfer-dependency','token-logical-expert','duplicate-expert','main-placement']:
        reset();c=json.loads((root/'config.json').read_text());p=json.loads((root/'plan.json').read_text())
        if case=='input-seed':
            values=(root/'input.txt').read_text().split();values[11]=str(int(values[11])+1);(root/'input.txt').write_text(' '.join(values))
        elif case=='assignment-identity':c['assignments'][0]['source']=(c['assignments'][0]['source']+1)%c['planner_input']['npus']
        elif case=='physical-quota':p['physical'][0]['quota']+=1
        elif case=='transfer-size':c['transfers'][0]['bytes']+=1
        elif case=='transfer-dependency':c['transfers'][-1]['dependencies']=[0]
        elif case=='token-logical-expert':p['token_mapping'][0]['logical_experts'][0]=(p['token_mapping'][0]['logical_experts'][0]+1)%c['planner_input']['experts']
        elif case=='duplicate-expert':p['physical'].append(dict(p['physical'][0]))
        elif case=='main-placement':c['planner_input']['main_placement'][0]=(c['planner_input']['main_placement'][0]+1)%c['planner_input']['npus']
        (root/'config.json').write_text(json.dumps(c));(root/'plan.json').write_text(json.dumps(p))
        try:m.check(root,args.graph_tool)
        except (ValueError,KeyError) as ex:results.append(dict(case=case,status='PASS',detected=str(ex)))
        else:raise AssertionError('tamper accepted: '+case)
report=dict(status='PASS',cases=results)
if args.out:args.out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
