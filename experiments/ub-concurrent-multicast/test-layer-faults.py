#!/usr/bin/env python3
import argparse,sys,json,shutil,subprocess,importlib.util
from pathlib import Path
X=Path(__file__).resolve().parent;E=X.parent;sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--graph-tool',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for fault in ['weight-byte','early-final-ready','early-wqe','missing-wqe','duplicate-completion']:
 out=a.out/fault;r=run([a.binary,'--input='+str(a.input/'input.txt'),'--out='+str(out),'--logLevel=summary','--jettyMode=pair','--fault='+fault],a.out/(fault+'-host'),3600,case=a.out)
 assert r['returncode']!=0 and not r['guard'];v=json.loads((out/'validation.json').read_text());assert v['status']=='FAIL';rows.append(dict(case=fault,status='EXPECTED_REJECTION',error=v['error'],returncode=r['returncode']))
# Duplicate target notifications remain idempotent rather than adding coverage.
out=a.out/'duplicate-notify';r=run([a.binary,'--input='+str(a.input/'input.txt'),'--out='+str(out),'--logLevel=summary','--jettyMode=pair','--fault=duplicate-notify'],a.out/'duplicate-notify-host',3600,case=a.out);assert r['status']=='PASS';rows.append(dict(case='duplicate-notify',status='PASS_IDEMPOTENT'))
# Mutate only input/output evidence; independent preflight must reject.
spec=importlib.util.spec_from_file_location('pre',E/'tiered-logging/preflight.py');pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(pre)
for name in ['missing-member','wrong-member','wrong-envelope-count','early-receiver']:
 dest=a.out/name;dest.mkdir()
 for file in ['config.json','plan.json','assignments.csv','input.txt','online-summary.json','multicast-groups.csv','multicast-stats.csv']:
  shutil.copy2(a.input/file,dest/file)
 if name in ('missing-member','wrong-member'):
  c=json.loads((dest/'config.json').read_text())
  if name=='missing-member':c['multicast_groups'][0]['members'].pop()
  else:c['multicast_groups'][0]['members'][0]['target']=0
  (dest/'config.json').write_text(json.dumps(c))
 else:
  import csv
  file='multicast-stats.csv' if name=='wrong-envelope-count' else 'multicast-groups.csv';lines=list(csv.DictReader((dest/file).open()));key='envelopes' if name=='wrong-envelope-count' else 'receiver_ready_ps';lines[0][key]=str(int(lines[0][key])+1) if name=='wrong-envelope-count' else '0'
  with (dest/file).open('w') as f:w=csv.DictWriter(f,fieldnames=list(lines[0]));w.writeheader();w.writerows(lines)
 try:pre.check(dest,a.graph_tool,dest/'online-summary.json')
 except ValueError as e:rows.append(dict(case=name,status='EXPECTED_REJECTION',error=str(e)))
 else:raise AssertionError('mutation accepted: '+name)
(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print('PASS E2E faults and independent mutations')
