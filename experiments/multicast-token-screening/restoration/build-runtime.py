"""Restore verified accepted runtime only; no historical control binary substitution.
Uses the accepted commands and resource guard, with private path/provenance glue.
"""
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
W=ROOT/'token-screen-work'; N=ROOT/'token-screen-native'; OUT=ROOT/'token-screen-private/build'
H=W/'experiments/multicast-controlled-ablation'; G=W/'experiments/cloudmatrix-bandwidth/guard.py'
s=importlib.util.spec_from_file_location('restore_guard',G);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def freeze(paths):return {str(p.absolute()):sha(p) for p in sorted(set(paths)) if p.is_file()}
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def check(identity):
 for p,d in identity.items():assert sha(p)==d,'Frozen identity changed: '+p
assert json.loads((ROOT/'token-screen-private/native-build/status.json').read_text())['status']=='PASS'
assert json.loads((ROOT/'token-screen-private/restoration/native-verification.json').read_text())['status']=='PASS'
OUT.mkdir(exist_ok=False)
# Freeze accepted runtime sources only, not concurrently authored screening harness.
accepted_tree=json.loads((ROOT/'token-screen-private/restoration/remote-tree.json').read_text())
assert accepted_tree['sha']=='8f50dc4772debb9b8017d0e4e902a5510525c05e'
paths=[W/entry['path'] for entry in accepted_tree['tree'] if entry['type']=='blob' and (Path(entry['path']).suffix in ('.cc','.cpp','.c','.h','.hpp','.inc','.py','.cmake','.patch') or Path(entry['path']).name=='CMakeLists.txt')]
for p in paths:
 data=p.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
 entry=next(x for x in accepted_tree['tree'] if x['path']==str(p.relative_to(W)))
 assert blob==entry['sha'],'Accepted source changed: '+str(p)
paths += [p for p in (N/'src').rglob('*') if p.is_file()]
paths += [p for p in (N/'build-support').rglob('*') if p.is_file()]
paths += [N/name for name in ['CMakeLists.txt','ns3','.ns3rc','.lock-ns3_linux_build','cmake-cache/CMakeCache.txt','cmake-cache/build.ninja','cmake-cache/compile_commands.json','cmake-cache/ns3config.txt','cmake-cache/ns3Config.cmake','cmake-cache/ns3ConfigVersion.cmake']]
paths += [ROOT/'token-screen-private/restoration'/name for name in ['verification.json','native-verification.json','native-patch-commands.json','native-candidate-source-sha256.json','restore-native.py','build-runtime.py']]
paths += [W/'experiments/multicast-controlled-ablation/native/native-patch-manifest.json',W/'experiments/multicast-reversal-diagnosis/native-diagnostic-manifest.json']
source=freeze(paths);write('source-identity.json',source)
units=[('layer',H/'layer.cc',True),('observer-fifo-test',H/'observer-fifo-test.cc',True),('jetty-window-test',H/'jetty-window-test.cc',True),('jetty-observer-test',H/'jetty-observer-test.cc',True),('graph-tool',W/'experiments/ultraep-multicast-integration/graph-tool.cc',False),('model-probe',W/'experiments/qwen-roofline-compute/model-probe.cc',False)]
commands=[]
for name,src,libs in units:
 cmd=['c++','-std=c++20','-O2','-g',str(src)]
 if libs:cmd+=['-I'+str(N/'build/include'),'-L'+str(N/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(N/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core']
 cmd+=['-o',str(OUT/name)]
 commands.append(dict(name=name,argv=cmd));write('compiler-commands.json',commands)
 result=g.run(cmd,OUT/(name+'-build'),1800,case=OUT)
 assert result['status']=='PASS',name
 check(source)
libs=sorted((N/'build/lib').glob('libns3.44-*.so'));assert libs
binary=freeze([OUT/name for name,_,_ in units]+libs);write('binary-identity.json',binary)
check(source);check(binary)
provenance=dict(status='PASS',application_commit='3521a64fd300938af3af4573a9793c4cde8d9649',native_base='b8375b51a094d3b1217b697989e1ab979f609e64',native_patch_count=6,cpp_compiler=subprocess.check_output(['c++','--version'],text=True),application_flags=['-std=c++20','-O2','-g'],native_build='accepted build-native.py unchanged; release; assertions ON; logging OFF; unified-bus target; -j2',historical_binaries='Unavailable in restored snapshot. No substitution. New source-identical runtime identity recorded.',purpose='NEW256-only screening restoration; no optimization or protocol changes',build_wrapper_adaptations=['Fresh private paths','Skip unavailable historical binary control identity requirements','Recompile accepted graph-tool source instead of copying missing binary','Compile accepted model-probe for minimal unit validation'],source_identity_count=len(source),binary_identity_count=len(binary))
write('provenance.json',provenance)
identity=source|binary|freeze([OUT/name for name in ['source-identity.json','binary-identity.json','compiler-commands.json','provenance.json']])
write('build-identity.json',identity)
write('status.json',dict(status='PASS',identity=str(OUT/'build-identity.json'),binary=str(OUT/'layer'),tests_run=False))
print('PASS restored accepted runtime; tests not yet run',flush=True)
