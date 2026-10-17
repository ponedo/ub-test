from pathlib import Path
import json,hashlib,tarfile,io,time,csv,math
root=Path('/workspace/scratch/c6ba02920254/ep64-token-scaling/experiments/ep64-token-scaling');start=time.monotonic();m=json.loads((root/'DELIVERY-MANIFEST.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
for name,v in m['files'].items():
 p=root/name;assert p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],name
print('DELIVERY_FILES',len(m['files']),flush=True)
d=root/'data';runs=json.loads((d/'runs.json').read_text());rows=json.loads((d/'analysis/scaling.json').read_text());by={(r['tokens'],r['strategy']):r for r in rows};expected={(t,s) for t in [256,1024,2048,4096,6250,8192,12500] for s in ['no-balancing','direct','chunk-streaming']};assert len(runs)==len(rows)==21 and set(by)==expected;assert all(r['status']=='PASS' for r in runs)
for r in runs:
 s=r['summary'];v=r['validation'];mt=r['metrics'];row=by[(r['tokens'],r['strategy'])];a=r['tokens']*8
 assert sum(r['plan_load'])==r['physical_quota_sum']==a
 assert s['verified_bytes'][:2]==[a*128]*2
 assert v['checked_sender_completions']==mt['remote_WQEs']==mt['sender_completions']
 assert v['checked_TAs']==mt['TA_count']
 assert row['layer_latency_us']==s['layer_latency_ps']/1e6
 assert math.isclose(row['speedup'],by[(r['tokens'],'no-balancing')]['layer_latency_us']/row['layer_latency_us'],rel_tol=1e-14)
for t in [256,1024,2048,4096,6250,8192,12500]:
 rs=[r for r in runs if r['tokens']==t];assert len({r['routing_sha256'] for r in rs})==1
 u=[r for r in rs if r['strategy']!='no-balancing'];assert u[0]['input_hashes']['plan.json']==u[1]['input_hashes']['plan.json'] and u[0]['input_hashes']['assignments.csv']==u[1]['input_hashes']['assignments.csv']
prev=[]
for p in sorted(d.glob('tokens-*/routing.csv'),key=lambda p:int(p.parent.name[7:])):
 data=list(csv.DictReader(p.open()));assert data[:len(prev)]==prev;prev=data;toks={}
 for x in data:toks.setdefault(x['token'],[]).append(x)
 assert len(toks)==int(p.parent.name[7:]);assert all(len(v)==8 and len(set(x['expert'] for x in v))==8 and sorted(int(x['topk_index']) for x in v)==list(range(8)) and all(int(x['source_npu'])==int(t)%64 for x in v) for t,v in toks.items())
 assert all(r['routing_sha256']==sha(p) for r in runs if r['tokens']==int(p.parent.name[7:]))
initial=json.loads((d/'attempts/initial/runs.json').read_text());old=[r for r in initial if r['tokens']==6250][0];new=[r for r in runs if r['tokens']==6250 and r['strategy']=='no-balancing'][0];assert old['status']=='FAIL' and old['failure_reason']=='disk_free_guard';assert old['input_hashes']==new['input_hashes'] and old['routing_sha256']==new['routing_sha256']
print('MEASUREMENT_AND_ROUTING_AUDIT_PASS',flush=True)
files=total=0;packs=[]
for mf in sorted(d.rglob('manifest.json')):
 x=json.loads(mf.read_text())
 if x.get('format')!='verified-tar-xz-parts-v1':continue
 class Reader(io.RawIOBase):
  def __init__(self):self.i=0;self.f=None;self.h=hashlib.sha256();self.n=0
  def read(self,n=-1):
   assert n>=0;b=bytearray()
   while len(b)<n:
    if self.f is None:
     if self.i==len(x['parts']):break
     r=x['parts'][self.i];p=mf.parent/r['name'];assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'];self.f=p.open('rb');self.i+=1
    c=self.f.read(n-len(b))
    if not c:self.f.close();self.f=None;continue
    b.extend(c);self.h.update(c);self.n+=len(c)
   return bytes(b)
 reader=Reader();seen=set();bs=0
 with tarfile.open(fileobj=reader,mode='r|xz') as tar:
  for item in tar:
   assert item.isfile() and item.name not in seen
   v=x['files'][item.name];assert item.size==v['bytes'];h=hashlib.sha256()
   with tar.extractfile(item) as f:
    while b:=f.read(1048576):h.update(b)
   assert h.hexdigest()==v['sha256'];seen.add(item.name);bs+=item.size
 while reader.read(1048576):pass
 assert seen==x['files'].keys() and reader.n==x['archive_bytes'] and reader.h.hexdigest()==x['archive_sha256']
 files+=len(seen);total+=bs;packs.append({'package':str(mf.parent.relative_to(root)),'files':len(seen),'bytes':bs});print('PACKAGE_OK',mf.parent, len(seen),bs,flush=True)
r={'status':'PASS','delivery_files':len(m['files']),'measurement_rows':len(rows),'routing_points':7,'historical_failure_retained':True,'retry_inputs_identical':True,'packages':packs,'raw_members':files,'raw_bytes':total,'wall_seconds':time.monotonic()-start};Path('/tmp/ep64-final-independent-review.json').write_text(json.dumps(r,indent=2));print('FINAL_AUDIT_PASS',files,total,flush=True)
