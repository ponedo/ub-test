#!/usr/bin/env python3
"""Boundary tests at real executor entry and allocation-free graph prediction."""
import argparse,importlib.util,json,os,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--relay-input',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
rows=[]
for name,args,diagnostic in [('payload-zero',['--payloadBudgetBytes=0'],'payload budget range'),('payload-over',['--payloadBudgetBytes=8589934593'],'payload budget range'),('tasks-zero',['--weightTaskLimit=0'],'weight task limit range'),('tasks-over',['--weightTaskLimit=1000001'],'weight task limit range'),('payload-low',['--payloadBudgetBytes=1'],'payload bound'),('payload-negative',['--payloadBudgetBytes=-1'],'payload budget range'),('tasks-negative',['--weightTaskLimit=-1'],'weight task limit range'),('payload-uint64-overflow',['--payloadBudgetBytes=18446744073709551616'],'Invalid command-line argument')]:
 out=a.out/name;cmd=[str(a.binary.resolve()),'--input='+str(a.input.resolve()),'--out='+str(out),'--logLevel=summary']+args
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=10);assert r.returncode!=0 and diagnostic in r.stderr,(name,r.returncode,r.stderr)
 rows.append({'name':name,'status':'PASS','returncode':r.returncode,'diagnostic':diagnostic});(a.out/(name+'.txt')).write_text(r.stdout+r.stderr)
# Maxima are accepted for a small demand and produce identical simulated output.
stable=[]
for name,flags in [('default',[]),('max',['--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'])]:
 out=a.out/name
 r=subprocess.run([str(a.binary.resolve()),'--input='+str(a.input.resolve()),'--out='+str(out),'--logLevel=summary']+flags,capture_output=True,text=True,timeout=10)
 assert r.returncode==0,r.stderr
 j=json.loads((out/'online-summary.json').read_text());j.pop('verification_wall_ns');stable.append(j)
assert stable[0]==stable[1]
rows.append({'name':'maximum-ceilings-small-demand-parity','status':'PASS'})
spec=importlib.util.spec_from_file_location('capacity',H.parent/'multi-npu-relay/capacity.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
physical=[dict(expert=0,kind='replica') for _ in range(10)];o=dict(relay_max_relays=8,force_relay=True,relay_min_replicas=4,relay_min_fanout_gain=2,chunk_bytes=1)
assert m.weight_task_count(physical,'chunk-streaming',64*1024**2,o,0)==671088640
rows.append({'name':'huge-edge-count-without-allocation','status':'PASS','predicted':671088640})
# Exercise native rejection before allocating huge chunk ranges or payload buffers.
lines=a.relay_input.read_text().splitlines();fields=lines[1].split();fields[1]=str(64*1024**2);fields[6]='2';lines[1]=' '.join(fields)
opts=lines[-2].split();opts[0]='1';opts[4]='1';lines[-2]=' '.join(opts)
fi=a.out/'huge-native-input.txt';fi.write_text('\n'.join(lines)+'\n')
import time
start=time.monotonic()
r=subprocess.run([str(a.binary.resolve()),'--input='+str(fi.resolve()),'--out='+str((a.out/'huge-native').resolve()),'--payloadBudgetBytes=8589934592','--weightTaskLimit=1000000'],capture_output=True,text=True,timeout=10)
assert r.returncode!=0 and 'weight task count bound' in r.stderr,(r.returncode,r.stderr)
rows.append({'name':'native-huge-edge-rejection-before-allocation','status':'PASS','wall_seconds':time.monotonic()-start,'returncode':r.returncode,'diagnostic':r.stderr.strip()})
# Adapter rejects before invoking an external graph generator.
import shutil
source=a.out/'huge-adapter-source';shutil.copytree(a.relay_input.parent,source)
c=json.loads((source/'config.json').read_text());c['runtime'].update(weight_bytes=64*1024**2,weight_size_kind='synthetic',weight_task_limit=1000000)
(source/'config.json').write_text(json.dumps(c))
spec=importlib.util.spec_from_file_location('relay_adapter',H.parent/'multi-npu-relay/adapter.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
original=adapter.subprocess.check_output
called=[]
def forbidden(*args,**kwargs):
 called.append(True);raise AssertionError('graph tool invoked before capacity rejection')
adapter.subprocess.check_output=forbidden
try:
 try:adapter.emit(source,dict(chunk_bytes=1,force_relay=True),'chunk-streaming',a.out/'huge-adapter-output')
 except ValueError as e:assert str(e)=='weight task count bound',str(e)
 else:raise AssertionError('missing adapter capacity rejection')
finally:adapter.subprocess.check_output=original
assert not called
rows.append({'name':'adapter-huge-edge-rejection-before-graph-invocation','status':'PASS'})
(a.out/'results.json').write_text(json.dumps({'status':'PASS','tests':rows},indent=2)+'\n');print('PASS',len(rows))
