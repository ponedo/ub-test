#!/usr/bin/env python3
"""ABI-matched real-network probes; preserve every failure and original source."""
import argparse,json,os,subprocess,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--a-root',type=Path,required=True);p.add_argument('--b-root',type=Path,required=True);p.add_argument('--c-root',type=Path,required=True);p.add_argument('--a-lib',type=Path,required=True);p.add_argument('--b-lib',type=Path,required=True);p.add_argument('--c-lib',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();H=Path(__file__).resolve().parent
a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);rows=[]
cases=[('single-single',['--mode=singleonesegment']),('single-multi',['--mode=single']),('multi-single',['--mode=onesegment']),('original-multi',['--checkpointNs=70310']),('late-overlap',['--lateNs=25000']),('staggered',['--delayedLastNs=20000']),('duplicate',['--duplicateDone=1']),('pressure',['--count=16','--segments=32','--lateNs=25000','--duplicateDone=1']),('small-segments',['--segmentBytes=64','--count=8','--lateNs=25000'])]
for arm in 'ABC':
 root=getattr(a,arm.lower()+'_root').resolve();lib=getattr(a,arm.lower()+'_lib').resolve()
 env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(a.out),'LD_LIBRARY_PATH':str(lib)}
 provenance={'native_head':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'native_diff':subprocess.check_output(['git','-C',str(root),'diff','HEAD'],text=True),'libraries':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(lib.glob('libns3.*.so'))},'sources':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(H.glob('*.cc'))}}
 (a.out/f'{arm}-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 for kind,src in [('original','original-shared-jetty-probe.cc'),('expanded','shared-jetty-probe.cc'),('cancel','cancel-hole.cc'),('wake','cancel-wakeup.cc')]:
  binary=a.out/f'{arm}-{kind}';cmd=['c++','-std=c++20','-O2','-g',str(H/src),'-I'+str(root/'build/include'),'-L'+str(lib),'-Wl,--disable-new-dtags','-Wl,-rpath,'+str(lib),'-lns3.44-unified-bus','-lns3.44-network','-lns3.44-core','-o',str(binary)]
  (a.out/f'{arm}-{kind}-build-command.json').write_text(json.dumps(cmd)+'\n')
  with (a.out/f'{arm}-{kind}-build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
  ldd=subprocess.check_output(['ldd',str(binary)],text=True,env=env);(a.out/f'{arm}-{kind}-ldd.txt').write_text(ldd)
  assert 'not found' not in ldd
  for line in ldd.splitlines():
   if 'libns3.' in line:assert Path(line.split()[2]).resolve().parent==lib
  runs=[('original',[])] if kind=='original' else cases if kind=='expanded' else [('cancel-hole',[])] if kind=='cancel' else [('cancel-wakeup',[]),('failure-wakeup',['--fail=1'])]
  for name,args in runs:
   prefix=a.out/f'{arm}-{kind}-{name}';cmd=[str(binary)]+args+([] if kind in ('cancel','wake') else ['--output='+str(prefix)])
   with Path(str(prefix)+'.stdout').open('w') as out,Path(str(prefix)+'.stderr').open('w') as err:
    t=time.monotonic()
    try:rc=subprocess.run(cmd,stdout=out,stderr=err,env=env,timeout=30).returncode
    except subprocess.TimeoutExpired:rc=124
   rows.append(dict(arm=arm,kind=kind,case=name,rc=rc,wall_s=time.monotonic()-t,command=cmd));(a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
# Original A/B must reproduce, C must pass. Expanded A/B are characterizations.
assert all(r['rc']==1 for r in rows if r['arm'] in 'AB' and r['kind']=='original')
assert all(r['rc']==0 for r in rows if r['arm']=='C')
assert 'hole_observed=0,errors=0' in (a.out/'C-cancel-cancel-hole.stdout').read_text()
assert all(r['rc']==1 for r in rows if r['arm'] in 'AB' and r['kind']=='wake')
