#!/usr/bin/env python3
"""Package finalized evidence without deleting originals; exclude build/source copies explicitly."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
from compact import compact,sha
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();raw=a.raw.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);excluded=[];included=[]
def copy_tree(source,dest,filter_copies=False):
 for f in sorted(source.rglob('*')):
  if not f.is_file():continue
  rel=f.relative_to(source)
  if f.is_symlink():raise ValueError(f'symlink {f}')
  reason=None
  if filter_copies and (rel.parts[0] in ['source','aux','home'] or '.git' in rel.parts or '__pycache__' in rel.parts):reason='reconstructible source/build/cache copy'
  with f.open('rb') as h:magic=h.read(4)
  if magic==b'\x7fELF':reason='rebuildable ELF; hash retained'
  if reason:excluded.append({'path':str(f),'reason':reason,'bytes':f.stat().st_size,'sha256':sha(f)});continue
  t=dest/rel;t.parent.mkdir(parents=True,exist_ok=True)
  # Copies can cross /tmp and workspace mounts; originals remain untouched.
  try:os.link(f,t)
  except OSError:shutil.copy2(f,t)
  included.append({'source':str(f),'path':str(t.relative_to(out)),'sha256':sha(f),'bytes':f.stat().st_size})
for f in sorted(raw.iterdir()):
 if f.is_file():shutil.copy2(f,out/f.name)
 elif f.name.startswith('tokens-') or f.name in ['analysis','attempts']:copy_tree(f,out/f.name)
 elif f.name=='build':copy_tree(f,out/f.name,True)
 elif f.name.startswith('regressions'):
  stage=out/('.stage-'+f.name);stage.mkdir();copy_tree(f,stage,True);compact(stage,out/(f.name+'-evidence'))
# Retained old chain writes raw native outputs to recorded temporary roots.
old=raw/'regressions-old-retry/old-evidence/prior-regression'
for name,key,record in [('prior-direct-raw','raw_evidence',old/'execution.json'),('prior-network-raw','raw_network_root',old/'older/environment.json')]:
 source=Path(json.loads(record.read_text())[key]);assert source.is_dir()
 stage=out/('.stage-'+name);stage.mkdir();copy_tree(source,stage,True);compact(stage,out/(name+'-evidence'))
(out/'packaging-exclusions.json').write_text(json.dumps(excluded,indent=2)+'\n')
(out/'packaging-policy.json').write_text(json.dumps({'originals_untouched':True,'excludes':'rebuildable ELF/source snapshot/aux/cache, with exclusion hashes; all run events, payloads, test logs, failed attempts and raw measured resources retained','regression_packages':'nested prior packages retain own manifests; restore outer then inner if needed'},indent=2)+'\n')
print(json.dumps({'files':sum(f.is_file() for f in out.rglob('*')),'bytes':sum(f.stat().st_size for f in out.rglob('*') if f.is_file()),'excluded':len(excluded)}))
