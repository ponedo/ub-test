import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
n=root/'token-screen-native'; w=root/'token-screen-work'; out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj): (out/name).write_text(json.dumps(obj,indent=2)+'\n')
def inv():return {str(p.relative_to(n)):sha(p) for p in sorted((n/'src').rglob('*')) if p.is_file()}
def verify(expected,label):
 mismatch=[p for p,d in expected.items() if not (n/p).is_file() or sha(n/p)!=d]
 assert not mismatch,(label,mismatch)
 return dict(name=label,file_count=len(expected),status='PASS')
assert subprocess.check_output(['git','-C',str(n),'rev-parse','HEAD'],text=True).strip()=='b8375b51a094d3b1217b697989e1ab979f609e64'
assert not subprocess.check_output(['git','-C',str(n),'status','--porcelain'],text=True).strip()
base=inv();write('native-base-source-sha256.json',base)
patches=['ub-multicast-v2/patches/native-write-v2.patch','ub-multicast-retransmission/patches/transport-fault-seam.patch','ultraep-multicast-integration/patches/peek-original-head.patch','ultraep-multicast-integration/patches/allocator-revalidation.patch','multicast-reversal-diagnosis/patches/native-diagnostics.patch','multicast-controlled-ablation/native/ub-jetty-controlled-ablation.patch']
records=[];checks=[]
for index,rel in enumerate(patches):
 p=w/'experiments'/rel
 for command in (['git','apply','--check',str(p)],['git','apply',str(p)]):
  run=subprocess.run(command,cwd=n,capture_output=True,text=True)
  records.append(dict(argv=command,cwd=str(n),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,patch_sha256=sha(p)))
  write('native-patch-commands.json',records)
  assert run.returncode==0,records[-1]
 if index==3:
  expected=json.loads((w/'experiments/ultraep-multicast-integration/candidate-native-source-sha256.json').read_text())
  checks.append(verify(expected,'accepted integration native source inventory'))
 if index==4:
  m=json.loads((w/'experiments/multicast-reversal-diagnosis/native-diagnostic-manifest.json').read_text())
  assert sha(p)==m['patch_sha256']
  checks.append(verify({x['path']:x['diagnostic_sha256'] for x in m['files']},'diagnostic patch native manifest'))
  diagnosis=inv();write('native-diagnostic-source-sha256.json',diagnosis)
 if index==5:
  m=json.loads((w/'experiments/multicast-controlled-ablation/native/native-patch-manifest.json').read_text())
  assert sha(p)==m['patch_sha256']
  checks.append(verify({x['path']:x['candidate_sha256'] for x in m['files']}|m['unchanged_controls'],'controlled ablation native manifest'))
  candidate=inv();delta=sorted(p for p in set(diagnosis)|set(candidate) if diagnosis.get(p)!=candidate.get(p))
  assert delta==sorted(x['path'] for x in m['files'])
  assert len(candidate)==m['complete_native_src_inventory_file_count']
  assert all(diagnosis[x['path']]==x['accepted_sha256'] for x in m['files'])
  write('native-candidate-source-sha256.json',candidate)
write('native-verification.json',dict(status='PASS',base_commit='b8375b51a094d3b1217b697989e1ab979f609e64',application_commit='3521a64fd300938af3af4573a9793c4cde8d9649',base_file_count=len(base),candidate_file_count=len(candidate),patch_count=len(patches),checks=checks,controlled_ablation_delta=delta,allocator_sha256=candidate['src/unified-bus/model/ub-switch-allocator.cc'],allocator_unchanged_from_diagnosis=True))
print('PASS: exact six patch chain, accepted manifests, all 3430 native source files accounted for')
