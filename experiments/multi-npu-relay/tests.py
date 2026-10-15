#!/usr/bin/env python3
import argparse,csv,hashlib,io,json,os,random,shutil,subprocess,sys,tempfile
from pathlib import Path
from verify import verify,require
from cases import HERE,MODES
p=argparse.ArgumentParser();p.add_argument('--ns3',default='/workspace/ns-3-ub');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out).resolve()
graph=os.environ.get('RELAY_GRAPH_TOOL','/tmp/ub-relay-build/graph-tool');oracle=str(Path(graph).with_name('reference-oracle'))
records=[]
old=(HERE.parent/'direct-weight-forward/direct-weight-forward.cc').read_text();new=(HERE/'multi-npu-relay.cc').read_text()
def compute(s):return s[s.index('    uint64_t Duration('):s.index('    void Ready(')]
require(compute(old)==compute(new),'accepted compute implementation changed')
require((HERE.parent/'no-balancing-layer/nb-tracker.h').read_bytes()==(HERE.parents[1]/'poc/chunk-relay/tracker.h').read_bytes(),'original tracker drift')

def run_graph(text):
 rows=csv.DictReader(io.StringIO(subprocess.check_output([graph],input=text,text=True)))
 return {(int(r['source_physical']),int(r['physical'])) for r in rows}
def ref_graph(text):
 return {tuple(map(int,line.split(','))) for line in subprocess.check_output([oracle],input=text,text=True).splitlines()}
# Deterministic multi-expert l2p permutations: direct vs force/adaptive, all supported EP sizes.
rng=random.Random(20261015);order_differences=0;load_differences=0
for trial in range(120):
 n=[4,8,64][trial%3];m=2;stride=m+2;ps=[]
 for e in range(n*m):ps.append([e//m*stride+e%m,e,e//m,0,1,e//m*stride+e%m,e//m])
 mains=ps.copy();nextid=n*stride
 # Graph oracle inputs can represent arbitrary pre-existing replicas, not planner outputs.
 for e in range(min(6,n*m)):
  ranks=rng.sample([r for r in range(n) if r!=e//m],rng.randint(1,n-1));rng.shuffle(ranks)
  for r in ranks:ps.append([nextid,e,r,1,1,mains[e][0],e//m]);nextid+=1
 def encode(rows,kind=2):return ' '.join(map(str,[kind,49152,n,4096,4,8,2,trial%2,32768,len(rows)]))+'\n'+'\n'.join(' '.join(map(str,row)) for row in rows)+'\n'
 text=encode(ps);actual=run_graph(text);expected=ref_graph(text);require(actual==expected,'public topology mismatch')
 sortedps=sorted(ps,key=lambda row:(row[2],row[0]));order_differences+=int(run_graph(encode(sortedps))!=actual)
 reset=set()
 for main in mains:
  selected=[x for x in ps if x[1]==main[1]]
  if len(selected)>1:reset|=run_graph(encode(selected))
 load_differences+=int(reset!=actual)
 require(run_graph(encode(ps,1))==actual,'whole/chunk grouping differs')
 records.append(dict(trial=trial,npus=n,edges=len(actual),status='PASS'))
require(order_differences>0 and load_differences>0,'missing l2p/load-sensitive tests')
for name in [d for d in out.iterdir() if d.is_dir() and (d/'chunk-streaming').exists()]:
 for mode in MODES:
  case=name/mode
  require(run_graph((case/'graph-input.txt').read_text())==ref_graph((case/'graph-input.txt').read_text()),'case public grouping')
# Integration invariants and specific coverage.
comparison=json.loads((out/'comparison.json').read_text())
require(len(comparison)==12,'full matrix coverage')
for name,block in comparison.items():
 require(len({v['combine_sha256'] for v in block.values()})==1,'result equivalence')
 require(all(block[m]['per_npu_load']==block['direct']['per_npu_load'] for m in MODES[1:]),'load equivalence')
 plans=[(out/name/m/'plan.json').read_bytes() for m in MODES[1:]];require(all(v==plans[0] for v in plans),'exact shared Planner bytes')
 require(not block['two-stage']['pipeline_overlaps'],'whole expert must not pipeline chunks')
require(comparison['multi4_force']['chunk-streaming']['native_pipeline_overlaps'],'native admitted chunk pipeline absent')
require(comparison['fixed64']['chunk-streaming']['native_pipeline_overlaps'],'EP64 native pipeline absent')
require(comparison['fixed64']['chunk-streaming']['replicas']==31,'EP64 replicas')
# Native same-model Direct path remains identical to accepted milestone.
for name,oldname in [('single4','single_replica4'),('multi4_force','multi_replica4'),('fixed64','fixed64')]:
 for mode,oldmode in [('no-balancing','no-balancing'),('direct','ultraep')]:
  old=json.loads((HERE.parent/'direct-weight-forward/evidence'/oldname/oldmode/'summary.json').read_text())
  now=comparison[name][mode];require(now['layer_latency_ps']==old['layer_latency_ps'] and now['per_npu_load']==old['per_npu_load'],'accepted Direct parity')
case=out/'out_of_order4/chunk-streaming';c=json.loads((case/'config.json').read_text())
with (case/'events.csv').open() as f:events=list(csv.DictReader(f))
ready={int(x['task']):int(x['time_ps']) for x in events if x['event']=='edge_ready'}
weights=[x for x in c['transfers'] if x['stage']==2 and not x['dependencies']]
require(any(x['physical']==y['physical'] and x['offset']<y['offset'] and ready[x['task']]>ready[y['task']] for x in weights for y in weights),'out-of-order target completion not exercised')
# Slow-relay evidence: fast relay has local coverage but waits for the entire fan-out group.
slow=comparison['slow_relay8']['chunk-streaming']
require(slow['readiness']=='upstream-group-chunk' and slow['group_chunk_count']>0,'missing upstream groups')
slow_config=json.loads((out/'slow_relay8/chunk-streaming/config.json').read_text())
fast_waits=[w for w in slow['group_waits'] if slow_config['transfers'][w['task']]['source']==2]
require(fast_waits and max(w['wait_ps'] for w in fast_waits)>10000000,'slow relay failed to hold fast relay')
# Live adversarial execution, never fabricate successful logs.
canary=out/'multi4_force/chunk-streaming';faults=[]
expected={'weight-byte':'payload byte mismatch','relay-byte':'payload byte mismatch','relay-buffer-byte':'payload byte mismatch','early-relay':'relay before target chunk ready','early-final-ready':'final ready before full weight coverage','premature-ready':'ready before target completion coverage','duplicate-weight':'duplicate forwarding','early-group':'relay before target chunk ready'}
for fault,error in expected.items():
 dest=out/'negative'/fault;dest.mkdir(parents=True,exist_ok=True)
 fault_case=out/'slow_relay8/chunk-streaming' if fault=='early-group' else canary
 cmd=[sys.executable,'./ns3','run','--no-build',f'multi-npu-relay --input={fault_case}/input.txt --out={dest} --fault={fault}']
 with (dest/'console.txt').open('w') as f:r=subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT)
 require(r.returncode!=0 and error in (dest/'console.txt').read_text(),'fault not rejected '+fault)
 if fault=='early-group':
  fc=json.loads((fault_case/'config.json').read_text())
  with (dest/'events.csv').open() as f:fe=list(csv.DictReader(f))
  attempts=[x for x in fe if x['event']=='early_group_attempt'];require(len(attempts)==1,'missing fast-relay group fault')
  child=fc['transfers'][int(attempts[0]['task'])]
  completed={int(x['task']) for x in fe if x['event']=='edge_ready'}
  own=[j for j in child['dependencies'] if fc['transfers'][j]['physical']==child['source_physical']]
  require(all(j in completed for j in own) and any(j not in completed for j in child['dependencies']),'fault must distinguish own-ready from group-ready')
 faults.append(dict(fault=fault,returncode=r.returncode,expected=error,command=cmd))
dest=out/'duplicate-notify';dest.mkdir(exist_ok=True)
for name in ['input.txt','plan.json','config.json']:shutil.copyfile(canary/name,dest/name)
cmd=[sys.executable,'./ns3','run','--no-build',f'multi-npu-relay --input={dest}/input.txt --out={dest} --fault=duplicate-notify']
with (dest/'console.txt').open('w') as f:subprocess.run(cmd,cwd=a.ns3,stdout=f,stderr=subprocess.STDOUT,check=True)
summary=verify(dest);require(summary==comparison['multi4_force']['chunk-streaming'],'duplicate notification changed execution')
require('duplicate_ignored' in (dest/'events.csv').read_text(),'duplicate notifications absent')
# Independent verifier rejects payload tampering and final-ready timestamps.
with tempfile.TemporaryDirectory(prefix='relay-audit-') as tmp:
 d=Path(tmp)
 for file in canary.iterdir():
  if file.is_file():shutil.copyfile(file,d/file.name)
 raw=bytearray((d/'received-payloads.bin').read_bytes());raw[-1]^=1;(d/'received-payloads.bin').write_bytes(raw)
 try:verify(d)
 except ValueError:pass
 else:raise ValueError('payload tamper not rejected')
 shutil.copyfile(canary/'received-payloads.bin',d/'received-payloads.bin')
 with (d/'events.csv').open() as f:rows=list(csv.DictReader(f))
 for row in rows:
  if row['event']=='weight_ready':row['time_ps']='1000';break
 with (d/'events.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 try:verify(d)
 except ValueError:pass
 else:raise ValueError('premature final log not rejected')
report=dict(status='PASS',public_oracle_cases=120,order_sensitive_cases=order_differences,cross_expert_load_sensitive_cases=load_differences,live_faults=faults,duplicate_notifications='idempotent, same final timing/payloads',event_payload_tamper_rejections=2,slow_relay_max_fast_wait_ps=max(w['wait_ps'] for w in fast_waits),coverage='48 runs, EP4/8/64, partial chunks/TAs, actual target completion reordering, pipeline overlap, legacy Direct parity',oracle_records=records)
(out/('tests-optimized.json' if not __debug__ else 'tests.json')).write_text(json.dumps(report,indent=2)+'\n')
print('PASS:',report['public_oracle_cases'],'oracle cases;',order_differences,'order-sensitive;',load_differences,'cross-expert sensitive; 8 live faults and duplicate/tamper checks')
