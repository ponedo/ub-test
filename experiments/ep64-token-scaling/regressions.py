#!/usr/bin/env python3
"""Run retained Pair and original UltraEP regressions sequentially, no model edits."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;REPO=H.parents[1]
sys.path.insert(0,str(H.parent/'wqe-completion-fix'))
from guard import run
from compact import compact,sha
p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--only-old',action='store_true');a=p.parse_args();out=a.raw.resolve();out.mkdir(parents=True,exist_ok=False);ledger=[]
env={'PATH':str(a.tools.resolve()/'bin')+':'+str(Path(sys.executable).parent)+':/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','HOME':str(out/'home'),'PYTHONPATH':str(a.tools.resolve()),'NS3_ROOT':str(a.native.resolve()),'NATIVE':str(a.native.resolve()),'BUILD_TOOLS':str(a.tools.resolve()),'BUILD_JOBS':'4','LD_LIBRARY_PATH':str(a.native.resolve()/'build/lib')}
def execute(name,cmd,extra=None,cwd=None):
 if shutil.disk_usage(out).free<8*1024**3:raise RuntimeError('disk_free_guard regression preflight')
 r=run(cmd,out/(name+'-host'),300,cwd=cwd,case=out,env=dict(env,**(extra or {})));ledger.append({'name':name,'resource':r});(out/'results.json').write_text(json.dumps(ledger,indent=2)+'\n')
 if r['status']!='PASS':raise RuntimeError('regression '+name+' failed')
if not a.only_old:
 execute('build-native-test',['c++','-std=c++20','-O3','-g',a.native.resolve()/'utils/test-runner.cc','-I'+str(a.native.resolve()/'build/include'),'-L'+str(a.native.resolve()/'build/lib'),'-Wl,--no-as-needed','-lns3.44-unified-bus-test','-lns3.44-core','-Wl,-rpath,'+str(a.native.resolve()/'build/lib'),'-o',out/'native-test-runner'])
 execute('native-tests',[sys.executable,H.parent/'jetty-resource-mapping/run-native-tests.py','--native',a.native.resolve(),'--runner',out/'native-test-runner','--out',out/'native-tests'])
 execute('pair-basic',[sys.executable,H.parent/'pair-jetty/run-basic-probe.py','--binary',a.build.resolve()/'pair-probe','--out',out/'pair-basic'])
 # Original nested wrapper sets AS8GiB; outer retained hardlimit is7GiB.
 # Tighten only the copied bootstrap limit so the child does not raise hardlimit.
 lifecycle=out/'lifecycle-bootstrap';lifecycle.mkdir()
 for name in ['pair-lifecycle-probe.cc','pair-jetty-manager.h','run-pair-lifecycle.sh']:shutil.copy2(H.parent/'pair-jetty'/name,lifecycle/name)
 f=lifecycle/'run-pair-lifecycle.sh';old=f.read_text();assert '(8*1024**3, 8*1024**3)' in old;new=old.replace('(8*1024**3, 8*1024**3)','(7*1024**3, 7*1024**3)');f.write_text(new)
 (out/'lifecycle-limit-adaptation.json').write_text(json.dumps({'reason':'nested8GiB exceeds retained outer7GiB hardlimit','original_script_sha256':sha(H.parent/'pair-jetty/run-pair-lifecycle.sh'),'adapted_script_sha256':sha(f),'only_change':'inner AS8GiB to7GiB'},indent=2)+'\n')
 execute('pair-lifecycle',['bash',f],{'OUT':str(out/'pair-lifecycle')})
 for group in ['nb','weights']:
  execute('pair-'+group,[sys.executable,H.parent/'pair-jetty/run-cases.py','--binary',a.build.resolve()/'pair-layer','--lib',a.native.resolve()/'build/lib','--inputs',a.fixtures.resolve(),'--group',group,'--out',out/('pair-'+group)])
  if group=='weights':execute('pair-negative',[sys.executable,H.parent/'pair-jetty/run-negative-tests.py','--binary',a.build.resolve()/'pair-layer','--lib',a.native.resolve()/'build/lib','--gate-c',out/'pair-weights','--out',out/'pair-negative'])
  compact(out/('pair-'+group),out/('pair-'+group+'-evidence'))
# Snapshot code only, without copying old raw/log payload evidence.
snapshot=out/'source';shutil.copytree(REPO,snapshot,ignore=shutil.ignore_patterns('.git','evidence','raw','results','__pycache__','ep64-token-scaling'))
# Old tests use git archive for an accepted historical planner. Give the isolated
# source snapshot its own tiny Git metadata and read-only shared object lookup.
subprocess.run(['git','init','--quiet',str(snapshot)],check=True)
common=subprocess.check_output(['git','-C',str(REPO),'rev-parse','--path-format=absolute','--git-common-dir'],text=True).strip()
(snapshot/'.git/objects/info/alternates').write_text(str(Path(common)/'objects')+'\n')
# The old suite reads required accepted config and summary JSON fixtures from tracked evidence.
fixtures=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','--name-only','HEAD','experiments/direct-weight-forward/evidence'],text=True).splitlines()
restored={}
for fixture in fixtures:
 if not fixture.endswith('.json'):continue
 f=snapshot/fixture;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(subprocess.check_output(['git','-C',str(REPO),'show','HEAD:'+fixture]));restored[fixture]=sha(f)
(out/'restored-fixtures.json').write_text(json.dumps({'files':restored,'source':'accepted HEAD git objects'},indent=2)+'\n')
base='d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b';head=subprocess.check_output(['git','-C',str(a.native),'rev-parse','HEAD'],text=True).strip();changes={}
for name in ['experiments/multi-npu-relay/build.sh','experiments/direct-weight-forward/build.sh','poc/chunk-relay/run.sh']:
 f=snapshot/name;old=f.read_text();assert base in old;new=old.replace(base,head)
 if name=='poc/chunk-relay/run.sh':new=new.replace('[[ ! -d "$NS3_ROOT/.git" ]]','! git -C "$NS3_ROOT" rev-parse --git-dir >/dev/null 2>&1')
 f.write_text(new);changes[name]={'old':old,'new':new}
(out/'bootstrap-adaptations.json').write_text(json.dumps(changes,indent=2)+'\n')
execute('old-ultraep',['bash',snapshot/'experiments/multi-npu-relay/run.sh'],{'EVIDENCE':str(out/'old-evidence'),'RELAY_GRAPH_TOOL':str(out/'aux/graph-tool')},snapshot)
(out/'source-hashes.json').write_text(json.dumps({str(f.relative_to(snapshot)):sha(f) for f in snapshot.rglob('*') if f.is_file() and '.git' not in f.relative_to(snapshot).parts},indent=2)+'\n')
# Source snapshot is reproducible; retained untouched until packaging policy excludes it.
compact(out/'old-evidence',out/'old-evidence-packed')
print('PASS Pair and retained UltraEP regressions')
