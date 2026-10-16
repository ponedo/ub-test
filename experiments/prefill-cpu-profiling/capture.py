#!/usr/bin/env python3
import hashlib,json,os,shutil,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent; E=H/'evidence';P=Path('/workspace/prefill-cpu-tools');perf=P/'root/usr/bin/perf';env=os.environ|{'LD_LIBRARY_PATH':str(P/'root/usr/lib/x86_64-linux-gnu')}
def cmd(args,path,env=None):
 r=subprocess.run(args,capture_output=True,env=env);path.write_bytes(('$ '+' '.join(map(str,args))+'\n').encode()+r.stdout+r.stderr);return r.returncode
if __name__=='__main__':
 (E/'perf_event_paranoid.txt').write_text(Path('/proc/sys/kernel/perf_event_paranoid').read_text())
 metadata=json.loads((P/'packages.json').read_text());packages={}
 for deb in P.glob('*.deb'):
  name=subprocess.check_output(['dpkg-deb','-f',str(deb),'Package'],text=True).strip();packages[name]={k:metadata[name][k] for k in ['Version','Filename','SHA256']};packages[name]['actual_sha256']=hashlib.sha256(deb.read_bytes()).hexdigest();assert packages[name]['actual_sha256']==packages[name]['SHA256']
 (E/'perf-packages.json').write_text(json.dumps(packages,indent=2)+'\n')
 cmd([str(perf),'version'],E/'perf-version.txt',env)
 cmd([str(perf),'stat','-e','cycles:u','--','/bin/true'],E/'hardware-probe.txt',env)
 assert cmd([str(perf),'record','-o',str(E/'probe.data'),'-e','cpu-clock:u','-F','99','--call-graph','dwarf,8192','--','python3','-c','sum(i*i for i in range(2000000))'],E/'perf-record-probe.txt',env)==0
 assert cmd([str(perf),'report','--stdio','--no-children','--percent-limit','0','-i',str(E/'probe.data')],E/'perf-report-probe.txt',env)==0
 for name,root in [('original',Path('/workspace/ns-3-ub')),('timed',Path('/workspace/prefill-cpu-native'))]:
  d=E/('build-'+name);d.mkdir(exist_ok=True)
  for f in ['compile_commands.json','CMakeCache.txt']:
   if (root/'cmake-cache'/f).exists():shutil.copyfile(root/'cmake-cache'/f,d/f)
  binaries=[root/'build/scratch/ns3.44-multi-npu-relay',root/'build/lib/libns3.44-unified-bus.so',root/'build/lib/libns3.44-core.so']+([root/'libcpuscopes.so'] if name=='timed' else [])
  for b in binaries:
   if not b.exists():continue
   cmd(['readelf','-n','-S',str(b)],d/(b.name+'.elf.txt'));cmd(['ldd',str(b)],d/(b.name+'.ldd.txt'))
  cmd(['git','-C',str(root),'rev-parse','HEAD'],d/'commit.txt')
  cmd(['git','-C',str(root),'diff','--stat'],d/'diff-stat.txt')
  r=subprocess.run(['/workspace/build-tools/bin/ninja','-C',str(root/'cmake-cache'),'-t','commands'],capture_output=True,env=os.environ|{'PYTHONPATH':'/workspace/build-tools'})
  (d/'executor-link-and-compile.txt').write_text('\n'.join(x for x in r.stdout.decode().splitlines() if 'multi-npu-relay' in x or (' -shared ' in x and ('unified-bus' in x or 'libns3.44-core' in x)))+'\n')
 # Freeze every measured ELF before any regression rebuild.
 paths=[Path('/workspace/ns-3-ub/build/scratch/ns3.44-multi-npu-relay'),*Path('/workspace/ns-3-ub/build/lib').glob('*.so'),Path('/workspace/prefill-cpu-native/build/scratch/ns3.44-multi-npu-relay'),Path('/workspace/prefill-cpu-native/libcpuscopes.so')]
 (E/'binary-sha256.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
 commands=[['uname','-a'],['c++','--version'],['python3.12','--version'],['git','-C','/workspace/ns-3-ub/scratch/ns-3-ub-tools','rev-parse','HEAD']]
 (E/'toolchain.txt').write_text('\n'.join('$ '+' '.join(c)+'\n'+subprocess.check_output(c,text=True) for c in commands))
