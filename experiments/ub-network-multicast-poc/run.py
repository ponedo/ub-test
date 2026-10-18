#!/usr/bin/env python3
"""Sequential protected network PoC matrix; raw receiver bytes stay in private work directory."""
import argparse,csv,json,os,sys,resource,shutil
from pathlib import Path
X=Path(__file__).resolve().parent
sys.path.insert(0,str(X.parent/'wqe-completion-fix'))
from guard import run
from verify import verify,rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--private',type=Path,required=True);ap.add_argument('--public',type=Path,required=True);a=ap.parse_args()
 a.private.mkdir(parents=True,exist_ok=False);a.public.mkdir(parents=True,exist_ok=True)
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 matrix=[]
 for s in ['basic','multipart','dynamic','competition','pressure']:
  for d in [False,True]:matrix.append((s+('-direct' if d else '-multicast'),[f'--scenario={s}',f'--direct={int(d)}']))
 matrix += [('cell156',['--basicBytes=156']),('cell157',['--basicBytes=157']),('dwrr-pressure',['--scenario=pressure','--dwrr=1'])]
 results=[]
 for name,args in matrix:
  out=a.private/name;out.mkdir();r=run([a.binary.resolve(),*args,'--out='+str(out.resolve())],out/'host',3600,case=a.private)
  if r['status']!='PASS':raise RuntimeError(f'{name} failed; see {out}/host/console.txt')
  v=verify(out);v.update(case=name,wall_seconds=r['wall_seconds'],cpu_seconds=r['user_cpu_seconds']+r['system_cpu_seconds'],peak_rss_kib=r['peak_rss_kib']);results.append(v)
  dst=a.public/name;dst.mkdir(exist_ok=True)
  for f in ['summary.csv','ports.csv','targets.csv','arbitration.csv']:shutil.copyfile(out/f,dst/f)
  (dst/'verification.json').write_text(json.dumps(v,indent=2)+'\n')
  (a.public/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 negative=[]
 for kind,message in [('empty','Invalid network PoC submission'),('reflected','Unknown or reflected destination'),('unknown','Unknown or reflected destination'),('oversize','payload exceeds 4096')]:
  out=a.private/('negative-'+kind);out.mkdir();r=run([a.binary.resolve(),'--negative='+kind,'--out='+str(out.resolve())],out/'host',3600,case=a.private)
  text=(out/'host/console.txt').read_text();assert r['returncode']!=0 and message in text,(kind,r,text)
  negative.append(dict(case=kind,status='EXPECTED_REJECTION',returncode=r['returncode'],matched_error=message))
 (a.public/'negative.json').write_text(json.dumps(negative,indent=2)+'\n')
 print('NETWORK MATRIX PASS',len(results),'positive',len(negative),'negative')
if __name__=='__main__':main()
