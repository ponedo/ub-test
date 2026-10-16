#!/usr/bin/env python3
import argparse,hashlib,json,subprocess,shutil,sys
from pathlib import Path
from execute import H,WORK,RAW
p=argparse.ArgumentParser();p.add_argument('--variant',choices=['baseline','timed'],required=True);a=p.parse_args()
root=RAW/'baseline-binaries' if a.variant=='baseline' else WORK/'prefill-cpu-native/build'
files=[p for p in root.rglob('*') if p.is_file() and (p.name.endswith('.so') or p.name=='ns3.44-multi-npu-relay')]
data={str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),build_id_notes=subprocess.check_output(['readelf','-n',p],text=True)) for p in files}
(H/f'evidence/{a.variant}-binary-hashes-before.json').write_text(json.dumps(data,indent=2)+'\n')
native=WORK/'prefill-cpu-native';commands=json.loads((native/'cmake-cache/compile_commands.json').read_text());chosen={s:next(x for x in commands if x['file'].endswith(s)) for s in ['scratch/multi-npu-relay.cc','src/unified-bus/model/protocol/ub-function.cc','src/core/model/simulator.cc']}
(H/f'evidence/{a.variant}-compile-audit.json').write_text(json.dumps(dict(commands=chosen,compiler=subprocess.check_output(['g++','--version'],text=True)),indent=2)+'\n')
print('Captured',a.variant,len(files),'ELF hashes')

if a.variant=='baseline':
 for name in ['CMakeCache.txt','compile_commands.json']:shutil.copy2(native/'cmake-cache'/name,H/'evidence'/name)
 (H/'evidence/build-audit.json').write_text(json.dumps(dict(commands=chosen,elf=data,compiler=subprocess.check_output(['g++','--version'],text=True)),indent=2)+'\n')
 (H/'evidence/toolchain.json').write_text(json.dumps(dict(python=sys.version,compiler=subprocess.check_output(['g++','--version'],text=True)),indent=2)+'\n')
else:
 nm=''
 for target in [root/'lib/libns3.44-unified-bus.so',root/'scratch/ns3.44-multi-npu-relay']:
  output=subprocess.check_output(['nm','-D','-C',target],text=True)
  nm+='\n'.join(line for line in output.splitlines() if any(x in line for x in ['ns3::ubcpu::Data()', 'ns3::ubcpu::Top()', 'ns3::ubcpu::Report()']))+'\n'
 (H/'evidence/timer-owner-symbols.txt').write_text(nm)
