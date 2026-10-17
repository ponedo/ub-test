#!/usr/bin/env python3
"""Re-run accepted failure injections against new capacity entry checks."""
import argparse,importlib.util,json,subprocess,sys
from pathlib import Path
h=Path(__file__).resolve().parent;sys.path.insert(0,str(h.parent/'tiered-logging'))
s=importlib.util.spec_from_file_location('logging_regression',h.parent/'tiered-logging/run.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for fault,messages in m.FAULTS.items():
 source=a.inputs/('slow-relay-fault' if fault=='early-group' else 'multichunk-multita')
 dest=a.out/fault
 r=subprocess.run([str(a.binary.resolve()),'--input='+str((source/'input.txt').resolve()),'--out='+str(dest.resolve()),'--logLevel=summary','--fault='+fault],capture_output=True,text=True,timeout=15)
 assert r.returncode>0 and 'ERROR: ' in r.stderr and any(x in r.stderr for x in messages),(fault,r.returncode,r.stderr)
 v=json.loads((dest/'validation.json').read_text());assert v['status']=='FAIL'
 rows.append(dict(fault=fault,status='PASS',returncode=r.returncode,validation=v))
(a.out/'results.json').write_text(json.dumps(dict(status='PASS',tests=rows),indent=2)+'\n');print('PASS',len(rows))
