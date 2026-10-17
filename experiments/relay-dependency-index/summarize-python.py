#!/usr/bin/env python3
"""Small timing/source manifest; raw profiles and configs stay local."""
import argparse,csv,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--scan',type=Path,required=True);p.add_argument('--indexed',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[];sources={}
for mode,root in (('scan',a.scan),('indexed',a.indexed)):
    ledger=json.loads((root/'ledger.json').read_text())
    for stage in ('preparation','preflight'):
        host=ledger[stage];coverage=json.loads((root/stage/'coverage.json').read_text());spans=list(csv.DictReader((root/stage/'stages.csv').open()))
        if stage=='preparation':chosen=[x for x in spans if 'multi-npu-relay/adapter.py::emit:' in x['stage'] and 'compile_dependencies(' in x['stage']]
        else:chosen=[x for x in spans if 'tiered-logging/preflight.py::check:' in x['stage'] and "if dependency_mode == 'scan':" in x['stage']]
        dependency=max(chosen,key=lambda x:float(x['wall_seconds']))
        rows.append(dict(mode=mode,stage=stage,status=host['status'],guard=host['guard'],wall_seconds=host['wall_seconds'],cpu_seconds=host['user_cpu_seconds']+host['system_cpu_seconds'],peak_rss_kib=host['peak_rss_kib'],sampled_peak_tree_rss_bytes=host['sampled_peak_tree_rss_bytes'],dependency_wall_seconds=dependency['wall_seconds'],dependency_cpu_seconds=dependency['cpu_seconds'],input_sha256='f420e4874c55ec90f9c8bc22420e57ec04648ab7fd053bbc8e122f66bee54d9b'))
        sources[f'{mode}/{stage}']=coverage['source_sha256']
a.out.mkdir(parents=True,exist_ok=True)
with (a.out/'python-timings.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(a.out/'python-profile-sources.json').write_text(json.dumps(dict(sources=sources,notes=['cProfile runs use existing statement instrumentation in both modes','Dependency span is max chunk-streaming adapter call; trivial direct calls excluded','Wall is full guarded process including profiler output; CPU and peak RSS from wait4','Both modes retain complete configuration, dependency materialization and validation']),indent=2)+'\n')
print(json.dumps(rows,indent=2))
# Preserve compact, reproducible attribution without publishing raw pstats.
import pstats
statements=[];hot=[]
for mode,root in (('scan',a.scan),('indexed',a.indexed)):
    for stage in ('preparation','preflight'):
        for row in csv.DictReader((root/stage/'stages.csv').open()):statements.append(dict(mode=mode,profile=stage,**row))
        stats=pstats.Stats(str(root/stage/'profile.pstats'))
        for (filename,line,function),(primitive,total,selftime,cumulative,callers) in sorted(stats.stats.items(),key=lambda x:x[1][3],reverse=True)[:25]:
            hot.append(dict(mode=mode,stage=stage,file=filename,line=line,function=function,primitive_calls=primitive,total_calls=total,self_seconds=selftime,cumulative_seconds=cumulative))
for name,data in [('python-statements.csv',statements),('python-profile-top.csv',hot)]:
    with (a.out/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
