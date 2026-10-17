"""Explicit single-file CLI acquisition; credential management remains outside this script."""
import argparse,csv,json,shutil,subprocess
from pathlib import Path
from inspect_samples import inspect
p=argparse.ArgumentParser();p.add_argument('--cli',required=True);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--initial-tokens',type=int,required=True);a=p.parse_args()
rows=list(csv.DictReader(a.candidates.open())); assert len(rows)<=3
results=[];total=a.initial_tokens
for r in rows:
    if total>=4096:break
    if shutil.disk_usage(a.input_root).free-2*int(r['bytes'])-100*1024**2<8*1024**3:raise RuntimeError('8GiB guard plus 100MiB analysis reserve')
    print('Exact download starts: '+r['path'],flush=True)
    subprocess.run([a.cli,'download','core12345/MoE_expert_selection_trace',r['path'],'--repo-type','dataset','--revision','27febb7b2d24169560a9f6f83d38eb53f94916cf','--local-dir',str(a.input_root)],check=True,timeout=300)
    result=inspect(a.input_root/r['path'],int(r['bytes']),r['git_blob']);result.update(source_path=r['path'],revision='27febb7b2d24169560a9f6f83d38eb53f94916cf',access='authorized exact single-file CLI')
    total+=result['tokens_per_layer'];results.append(result)
    a.output.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(dict(path=r['path'],N=result['tokens_per_layer'],cumulative_tokens=total,sha256=result['sha256'])),flush=True)
print(json.dumps(dict(status='STOPPED',cumulative_tokens=total,acquired_files=len(results))),flush=True)
