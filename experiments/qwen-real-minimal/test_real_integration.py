#!/usr/bin/env python3
"""Bounded source/precision regression tests. No simulation; no raw exports retained.

Requires private source manifest and frozen aggregate counts. Repeated source
checks cache the result of one complete independent audit, not source contents.
"""
import argparse,contextlib,copy,csv,importlib.util,io,json,os,subprocess,sys,tempfile,types
from collections import defaultdict
from pathlib import Path

def module(name,path,source=None):
 m=types.ModuleType(name);m.__file__=str(path)
 exec(compile(path.read_text() if source is None else source,str(path),'exec'),m.__dict__)
 return m

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True)
 ap.add_argument('--frozen-counts',type=Path,required=True);ap.add_argument('--graph-tool',type=Path,required=True)
 ap.add_argument('--routing-dir',type=Path,help='Optional original private three-layer256 export for exact-byte comparison')
 ap.add_argument('--legacy-ref',help='Optional git ref without weight_dtype_bytes support for exact backwards-compatibility tests')
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if not __debug__:raise RuntimeError('Run without -O')
 repo=a.repo.resolve();h=repo/'experiments/qwen-real-minimal';sys.path.insert(0,str(h));checks=[]
 def passed(name):checks.append(dict(test=name,status='PASS'))
 def rejects(name,fn):
  try:fn()
  except (ValueError,AssertionError,KeyError):passed(name);return
  raise AssertionError('unexpected acceptance: '+name)
 audit=module('source_audit',h/'source_audit.py');sys.modules['source_audit']=audit
 prep=module('prepare',h/'prepare.py');extract=module('extract_routing',h/'extract_routing.py')
 with tempfile.TemporaryDirectory(prefix='qwen-source-review-') as tmp:
  tmp=Path(tmp)
  with contextlib.redirect_stdout(io.StringIO()):summary,rows=audit.audit(a.manifest,a.frozen_counts,tmp/'valid-audit')
  passed('complete raw94-layer/frozen aggregate audit')
  actual_audit=audit.audit;audit.audit=lambda *args:(summary,rows);prep.module=lambda *args:audit
  data=extract.extract(a.manifest,a.frozen_counts,0,256,tmp/'unused')
  for name,mutate in [('wrong layer',lambda d:d.update(serialized_layer=37)),('wrong request',lambda d:d['tokens'][0].update(request_id='invalid')),('wrong ordinal',lambda d:d['tokens'][0].update(token_ordinal=999)),('wrong top-k order',lambda d:d['tokens'][0]['experts'].reverse()),('wrong manifest hash',lambda d:d.update(source_manifest_sha256='0'*64)),('cross-request boundary order',lambda d:d['tokens'].reverse())]:
   bad=copy.deepcopy(data);mutate(bad);rejects(name,lambda:prep.verify_source(bad,0,a.manifest,a.frozen_counts,tmp/'unused'))
  for name,mutate in [('duplicate identity',lambda d:d['tokens'].__setitem__(1,d['tokens'][0])),('255 tokens',lambda d:d['tokens'].pop()),('duplicate expert',lambda d:d['tokens'][0]['experts'].__setitem__(1,d['tokens'][0]['experts'][0])),('expert boundary128',lambda d:d['tokens'][0]['experts'].__setitem__(0,128)),('boolean expert',lambda d:d['tokens'][0]['experts'].__setitem__(0,True))]:
   bad=copy.deepcopy(data);mutate(bad);p=tmp/'bad-routing.json';p.write_text(json.dumps(bad));rejects(name,lambda:prep.load_routing(p))
  for name,mutate in [('unknown root field',lambda d:d.update(unknown=1)),('unknown token field',lambda d:d['tokens'][0].update(unknown=1)),('empty request',lambda d:d['tokens'][0].update(request_id='')),('numeric request',lambda d:d['tokens'][0].update(request_id=1)),('negative ordinal',lambda d:d['tokens'][0].update(token_ordinal=-1)),('boolean ordinal',lambda d:d['tokens'][0].update(token_ordinal=False)),('float ordinal',lambda d:d['tokens'][0].update(token_ordinal=0.0))]:
   bad=copy.deepcopy(data);mutate(bad);p=tmp/'bad-routing.json';p.write_text(json.dumps(bad));rejects(name,lambda:prep.load_routing(p))
  p=tmp/'duplicate-key.json';p.write_text(json.dumps(data).replace('"serialized_layer": 0','"serialized_layer": 0, "serialized_layer": 0',1));rejects('duplicate JSON root key',lambda:prep.load_routing(p))
  for value in (False,0.0):
   bad=copy.deepcopy(data);bad['serialized_layer']=value;rejects('noninteger serialized layer '+repr(value),lambda:prep.verify_source(bad,0,a.manifest,a.frozen_counts,tmp/'unused'))
  man=json.loads(a.manifest.read_text())
  for r in man['requests']:
   p=Path(r['file_path']);r['file_path']=str(p if p.is_absolute() else a.manifest.resolve().parent/p)
  for name,mutate in [('wrong raw identity',lambda m:m['requests'][0].update(expected_blob_sha='0'*40)),('changed manifest selection boundary',lambda m:m['requests'].reverse())]:
   bad=copy.deepcopy(man);mutate(bad);p=tmp/'bad-manifest.json';p.write_text(json.dumps(bad))
   with contextlib.redirect_stdout(io.StringIO()):rejects(name,lambda:actual_audit(p,a.frozen_counts,tmp/'bad-audit'))
  for l,n in [(0,n) for n in (1,256,512,4096,4275)]+[(93,1),(93,4096),(37,256),(52,256)]:
   result=extract.extract(a.manifest,a.frozen_counts,l,n,tmp/'unused');p=tmp/'routing.json';p.write_text(json.dumps(result));d,mapping=prep.load_routing(p,tokens=n);prep.verify_source(d,l,a.manifest,a.frozen_counts,tmp/'unused');assert [r['source'] for r in mapping]==[i%64 for i in range(n)]
   if a.routing_dir and n==256:assert (a.routing_dir/f'layer_{l}.json').read_bytes()==(json.dumps(result,separators=(',',':'))+'\n').encode()
   passed(f'exact source prefix layer{l} tokens{n}')
  for l,n in [(0,4276),(0,0),(0,True),(-1,256),(94,256),(True,256)]:rejects(f'extraction rejects layer{l} tokens{n}',lambda:extract.extract(a.manifest,a.frozen_counts,l,n,tmp/'unused'))
  # Real native graph compiler only: tiny graphs, no network simulation.
  for weight,cut,chunk in [(120,80,17),(18874368,12582912,4096)]:
   physical=['0 0 0 0 1 0 0']+[f'{i} 0 {i} 1 1 0 0' for i in range(1,5)]
   graph=f'2 {weight} 8 {chunk} 4 8 2 1 {cut} 5\n'+'\n'.join(physical)+'\n';output=subprocess.check_output([str(a.graph_tool)],input=graph,text=True);groups=defaultdict(list)
   for row in csv.DictReader(io.StringIO(output)):groups[int(row['physical'])].append((int(row['offset']),int(row['bytes'])))
   assert set(groups)=={1,2,3,4}
   for ranges in groups.values():
    end=0
    for off,size in sorted(ranges):assert off==end and 0<size<=chunk;end=off+size
    assert end==weight and any(off==cut for off,size in ranges)
   passed(f'FP8 complete disjoint native chunk coverage{weight} bytes')
  if a.legacy_ref:
   def load(rel,old=False):
    src=subprocess.check_output(['git','-C',str(repo),'show',a.legacy_ref+':'+rel]) if old else None
    return module(rel,repo/rel,src)
   old=load('experiments/direct-weight-forward/adapter.py',True);new=load('experiments/direct-weight-forward/adapter.py')
   c=dict(schema_version=1,npus=8,experts=8,top_k=1,main_placement=list(range(8)),slots=[2]*8,mapping=[dict(source=i%8,experts=[0]) for i in range(128)],beta='1.01',min_replica_quota=1)
   plan=old.solve(c);old.solve=lambda _:plan;new.solve=lambda _:plan
   def files(p):return {f.name:f.read_bytes() for f in p.iterdir() if f.is_file()}
   for i,params in enumerate(({},dict(dtype_bytes=1),dict(dtype_bytes=4),dict(weight_bytes=12345),dict(matrices=2),dict(model_dim=128,ff_dim=256))):
    for mode in ('no-balancing','ultraep'):
     x,y=tmp/f'old-{i}-{mode}',tmp/f'new-{i}-{mode}';assert old.emit(c,params,mode,x)==new.emit(c,params,mode,y);assert files(x)==files(y);passed(f'legacy byte equality case{i} {mode}')
   new.emit(c,{},'ultraep',tmp/'source');os.environ['RELAY_GRAPH_TOOL']=str(a.graph_tool.resolve())
   ro,rn=load('experiments/multi-npu-relay/adapter.py',True),load('experiments/multi-npu-relay/adapter.py')
   po,pn=load('experiments/tiered-logging/preflight.py',True),load('experiments/tiered-logging/preflight.py')
   for strategy in ('direct','two-stage','chunk-streaming'):
    x,y=tmp/('old-'+strategy),tmp/('new-'+strategy);ro.emit(tmp/'source',{},strategy,x);rn.emit(tmp/'source',{},strategy,y);assert files(x)==files(y);assert po.check(x,a.graph_tool)==pn.check(y,a.graph_tool);passed('legacy relay/preflight exact '+strategy)
 result=dict(status='PASS',checks=checks,total=len(checks),no_simulation=True,raw_outputs_retained=False)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status='PASS',checks=len(checks))))
if __name__=='__main__':main()
