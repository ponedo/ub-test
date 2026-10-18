#!/usr/bin/env python3
"""Read-only bounded source inventory/search. Never runs or modifies the simulator."""
import argparse, hashlib, json, pathlib, re, subprocess
p=argparse.ArgumentParser();p.add_argument('--native',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--compare',type=pathlib.Path);p.add_argument('--project',type=pathlib.Path);a=p.parse_args()
r=a.native.resolve(); out=a.out;out.mkdir(parents=True,exist_ok=True)
paths=sorted(x for x in (r/'src/unified-bus').rglob('*') if x.is_file() and x.suffix in ('.cc','.h','.md','.rst','.txt'))
paths += [r/'src/network/model'/name for name in ('packet.cc','packet.h','buffer.h','packet-tag-list.h','byte-tag-list.h')]
paths += [r/'src/core/model/assert.h']
files=[]; hits=[]
pat=re.compile(r'multicast|broadcast|replicat|IsMulticast|IsBroadcast|GetMulticast',re.I)
for f in sorted(set(paths)):
 b=f.read_bytes();rel=str(f.relative_to(r));files.append({'path':rel,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 for n,line in enumerate(b.decode('utf-8',errors='replace').splitlines(),1):
  if pat.search(line):hits.append({'path':rel,'line':n,'text':line.strip()})
def git(*args):return subprocess.check_output(['git','-C',str(r),*args],text=True).strip()
m={'schema_version':1,'base_commit':git('rev-parse','HEAD'),'scope':'src/unified-bus source/docs plus src/network/model/{packet.cc,packet.h,buffer.h,packet-tag-list.h,byte-tag-list.h}; and src/core/model/assert.h; excludes build/generated outputs','files':files,'git_tracked_changes':git('status','--short','--','src/unified-bus','src/network/model/packet.cc','src/network/model/packet.h').splitlines()}
if a.project:
 protected=[]
 for f in sorted(a.project.rglob('*')):
  if not f.is_file() or f.suffix not in ('.py','.cc','.h','.cpp','.hpp','.sh','.patch'):continue
  rel=f.relative_to(a.project)
  if any(t in rel.parts for t in ('.git','__pycache__','build','cmake-cache','ub-multicast-feasibility')):continue
  b=f.read_bytes();protected.append({'path':str(rel),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 m['protected_project_sources']=protected
(out/'source-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(out/'bounded-search.json').write_text(json.dumps({'pattern':pat.pattern,'scope':m['scope'],'file_count':len(files),'match_count':len(hits),'matches':hits,'interpretation':'Lexical evidence only. Absence of a match is not proof of specification absence or semantic impossibility.'},indent=2)+'\n')
res={'files':len(files),'search_matches':len(hits),'base_commit':m['base_commit']}
if a.compare:
 old=json.loads(a.compare.read_text());res['source_bytes_unchanged']=old['files']==files;res['protected_project_sources_unchanged']=old.get('protected_project_sources')==m.get('protected_project_sources');res['git_status_unchanged']=old['git_tracked_changes']==m['git_tracked_changes']
 (out/'comparison.json').write_text(json.dumps(res,indent=2)+'\n')
 if not res['source_bytes_unchanged'] or not res['git_status_unchanged'] or not res['protected_project_sources_unchanged']:raise SystemExit('Source changed during read-only audit')
print(json.dumps(res))
