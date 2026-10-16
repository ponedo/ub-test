#!/usr/bin/env python3
"""Pre-publication check. Reports locations/counts only, never credential bytes.
Primary prevention is a whitelisted recording environment. This scan cannot prove
absence of all secrets and is not permission to publish a flagged artifact.
"""
import argparse,hashlib,json,os,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('roots',nargs='+',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
known=[v.encode() for k,v in os.environ.items() if re.search(r'SECRET|TOKEN|PASSWORD|ACCESS_KEY|API_KEY',k,re.I) and len(v)>=12]
patterns=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{36,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}')]
findings=[];files=0;total=0;overlap=max([512]+[len(x) for x in known]);seen=set()
for root in a.roots:
 for path in ([root] if root.is_file() else sorted(root.rglob('*'))):
  if not path.is_file() or '.git' in path.parts or path==a.out:continue
  resolved=path.resolve()
  if resolved in seen:continue
  seen.add(resolved);files+=1;total+=path.stat().st_size;hits=set();tail=b''
  with path.open('rb') as f:
   while chunk:=f.read(1024*1024):
    data=tail+chunk
    if any(x in data for x in known):hits.add('known-sensitive-environment-value')
    for i,pat in enumerate(patterns):
     if pat.search(data):hits.add('credential-pattern-'+str(i))
    tail=data[-overlap:]
  if hits:findings.append({'path':str(path),'categories':sorted(hits)})
result=dict(status='PASS' if not findings else 'BLOCKED',files_scanned=files,bytes_scanned=total,known_sensitive_value_count=len(known),findings=findings,limitation='Whitelist environment is primary prevention. Pattern/known-value scan cannot establish absence of every possible secret. No values are logged.')
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='findings'}));raise SystemExit(bool(findings))
