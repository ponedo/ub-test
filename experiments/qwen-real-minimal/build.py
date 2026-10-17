#!/usr/bin/env python3
"""Compile unchanged C++ executor, Release optimization and existing native libs."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
if shutil.disk_usage(a.out).free<8*1024**3 or shutil.disk_usage('/tmp').free<2*1024**3 or psutil.virtual_memory().available<1536*1024**2:raise RuntimeError('resource precheck failed')
n=a.native.resolve();binary=a.out/'pair-layer';source=H.parent/'pair-jetty/pair-layer.cc'
cmd=['c++','-std=c++20','-O3','-g',source,'-I'+str(n/'build/include'),'-L'+str(n/'build/lib'),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(n/'build/lib'),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',binary]
r=run(cmd,a.out/'host',3600,case=a.out)
if r['status']!='PASS':sys.exit(2)
(a.out/'build-proof.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),flags=['-std=c++20','-O3','-g']),indent=2)+'\n')
