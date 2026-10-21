"""Build only the diagnostic application; never rebuild accepted executables."""
import argparse, shutil
from common import *
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();n=a.native.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
before=source_identity(n);write(o/'source-identity.json',before)
accepted=freeze([ACCEPTED/'build/layer',ACCEPTED/'build/graph-tool',*list((ROOT/'bandwidth-native/build/lib').glob('*.so'))]);write(o/'accepted-identity.json',accepted)
cmd=['c++','-std=c++20','-O2','-g',H/'layer.cc','-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-internet','-lns3.44-network','-lns3.44-core','-o',o/'layer']
assert run(cmd,o/'layer-build',1800,case=o)['status']=='PASS'
unit=[str(x) for x in cmd];unit[unit.index(str(H/'layer.cc'))]=str(H/'observer-fifo-test.cc');unit[-1]=str(o/'observer-fifo-test')
assert run(unit,o/'observer-fifo-test-build',1800,case=o)['status']=='PASS'
shutil.copyfile(ACCEPTED/'build/graph-tool',o/'graph-tool');(o/'graph-tool').chmod(0o755)
check(before);check(accepted);write(o/'binary-identity.json',binaries(o,n));write(o/'status.json',dict(status='PASS',native=str(n)))
