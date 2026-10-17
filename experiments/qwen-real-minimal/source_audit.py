#!/usr/bin/env python3
"""Read private sources; write only aggregate audit outputs. No simulator runs."""
import argparse,csv,gzip,hashlib,json,os
from pathlib import Path
def unique(pairs):
 d={}
 for k,v in pairs:
  assert k not in d, 'duplicate JSON key'
  d[k]=v
 return d

def audit(manifest_path, frozen_counts_path, output_dir, private_routing_dir=None):
 if not __debug__:raise RuntimeError('Run without Python -O: validation assertions must be enabled')
 manifest_path=Path(manifest_path).resolve();OUT=Path(output_dir).resolve();OUT.mkdir(parents=True,exist_ok=True)
 manifest_bytes=manifest_path.read_bytes()
 manifest=json.loads(manifest_bytes,object_pairs_hook=unique)
 for request in manifest['requests']:
  file_path=Path(request['file_path'])
  if not file_path.is_absolute():request['file_path']=str(manifest_path.parent/file_path)
 requests=manifest['requests'];assert len(requests)==8
 assert len({r['request_id'] for r in requests})==8
 assert len({(r['dataset_path'],r['revision']) for r in requests})==8
 assert len({r['expected_blob_sha'] for r in requests})==8
 assert len({str(Path(r['file_path']).resolve()) for r in requests})==8
 rows={l:[] for l in range(94)};identities=[];token_ids=[];sizes=[];boundary=[];raw_shas=[]
 for ri,r in enumerate(requests):
  raw=Path(r['file_path']).read_bytes();sha=hashlib.sha256(raw).hexdigest();raw_shas.append(sha)
  blob=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
  pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{sha}\nsize {len(raw)}\n'.encode()
  assert r['expected_blob_sha'] in (blob,hashlib.sha1(f'blob {len(pointer)}\0'.encode()+pointer).hexdigest())
  source=json.loads(raw,object_pairs_hook=unique);assert isinstance(source,list) and source
  for record_i,record in enumerate(source):
   assert list(record)==list(map(str,range(94)))
   n=len(record['0']);assert n>1 if record_i==0 else n==1
   for layer in record.values():
    assert len(layer)==n
    for es in layer:
     assert len(es)==8 and len(set(es))==8 and all(type(e)is int and 0<=e<128 for e in es)
  n=len(source[0]['0']);sizes.append(n);take=min(n,256-len(identities))
  if take:
   boundary.append({'manifest_request_index':ri,'source_ordinal_start':0,'selected_tokens':take})
   identities.extend((r['dataset_path'],r['revision'],t) for t in range(take))
   token_ids.extend((r['request_id'],t) for t in range(take))
   for l in range(94):rows[l].extend(source[0][str(l)][:take])
 assert sum(sizes)==4275 and len(identities)==len(set(identities))==256
 old={}
 with gzip.open(frozen_counts_path,'rt') as f:
  for r in csv.DictReader(f):
   if r['selection']=='batch_prefix_256' and r['dataset']=='real':
    key=(int(r['layer']),int(r['expert']));assert key not in old;old[key]=int(r['count'])
 assert len(old)==94*128
 metrics=[];loads=[]
 for l in range(94):
  assert len(rows[l])==256
  ex=[0]*128;np=[0]*64
  for es in rows[l]:
   for e in es:ex[e]+=1;np[e//2]+=1
  assert sum(ex)==sum(np)==2048 and all(ex[e]==old[l,e] for e in range(128))
  assert np==[sum(ex[2*r:2*r+2]) for r in range(64)]
  metrics.append(dict(layer=l,tokens=256,assignments=2048,expert_max=max(ex),expert_mean=16,expert_max_mean=max(ex)/16,npu_max=max(np),npu_mean=32,npu_max_mean=max(np)/32,active_experts=sum(v>0 for v in ex),active_npus=sum(v>0 for v in np)))
  loads.append(dict(layer=l,expert_loads=ex,npu_loads=np))
 ranked=sorted(metrics,key=lambda r:(r['npu_max'],r['layer']))
 for i,r in enumerate(ranked):r['rank_1based']=i+1
 selection={label:ranked[i] for label,i in [('low',0),('mid',46),('high',93)]}
 summary=dict(status='PASS',source_requests=8,source_prefill_tokens=4275,batch_tokens=256,layers=94,top_k=8,assignments_per_layer=2048,unique_source_token_pairs=256,source_request_lengths=sizes,batch_boundaries=boundary,placement='main_placement[e] = e // 2; 64 NPUs, 128 experts',source_placement='source_npu = batch_token_ordinal % 64',ranking_rule='Sort all 94 serialized layers ascending by (NoBalancing NPU max/mean, numeric serialized layer ID). Select ranks 1, 47, 94 (1-based); rank 47 is lower median, zero-based floor((94-1)/2).',selection=selection,validation=['All 8 raw source identities checked against manifest Git blob or canonical LFS pointer blob','All raw records validated: exactly serialized layers 0..93, equal row count, top-k 8 distinct integer experts 0..127','First 256 tokens in existing manifest request order and within-request ordinal order, identical source selection at every layer','No repeated (dataset path, revision, ordinal); no padding or token repetition','All 94 expert count vectors exactly match frozen published batch_prefix_256 aggregate','NPU load counted independently per assignment and checked against adjacent expert-pair sums'],limitations=['Offline concatenation of distinct requests; not an observed joint-forward batch','Record 0 phase interpretation follows existing dataset-card convention, without embedded phase proof','Serialized layer indices and token ordinals are not independently proven model-layer or tokenizer IDs'],raw_source_sha256=raw_shas)
 summary['source_manifest_sha256']=hashlib.sha256(manifest_bytes).hexdigest()
 summary['frozen_expert_counts_sha256']=hashlib.sha256(Path(frozen_counts_path).read_bytes()).hexdigest()
 if private_routing_dir is not None:
  private=Path(private_routing_dir).resolve()
  assert private!=OUT and not private.is_relative_to(OUT), 'Private routing must be separate from aggregate output'
  assert not private.exists(), 'Refusing to overwrite private routing output'
  private.mkdir(parents=True,mode=0o700)
  private.chmod(0o700)
  export_proofs=[]
  for label,selection_row in selection.items():
   layer=selection_row['layer']
   tokens=[dict(request_id=rid,token_ordinal=ordinal,experts=es) for (rid,ordinal),es in zip(token_ids,rows[layer])]
   payload=dict(serialized_layer=layer,tokens=tokens,source_manifest_sha256=summary['source_manifest_sha256'])
   target=private/f'layer_{layer}.json'
   with target.open('x') as f:json.dump(payload,f,separators=(',',':'));f.write('\n')
   target.chmod(0o600)
   readback=json.loads(target.read_text(),object_pairs_hook=unique)
   assert readback==payload and len(readback['tokens'])==256
   assert len({(t['request_id'],t['token_ordinal']) for t in readback['tokens']})==256
   for t,expected,identity in zip(readback['tokens'],rows[layer],token_ids):
    assert (t['request_id'],t['token_ordinal'])==identity and t['experts']==expected
   export_proofs.append(dict(serialized_layer=layer,tokens=256,assignments=2048,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,exact_readback=True))
  summary['private_routing_export_verification']=export_proofs
 for name,data in [('summary.json',summary),('aggregate-loads.json',loads)]: (OUT/name).write_text(json.dumps(data,indent=2)+'\n')
 with (OUT/'layer-ranking.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(ranked[0]));w.writeheader();w.writerows(ranked)
 print(json.dumps({k:summary[k] for k in ('status','batch_boundaries','source_request_lengths','ranking_rule','selection')},indent=2))
 return summary,rows
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--manifest',required=True,type=Path,help='Private source manifest; relative input file paths resolve against its directory')
 p.add_argument('--frozen-counts',required=True,type=Path,help='Frozen aggregate expert-counts.csv.gz')
 p.add_argument('--output',required=True,type=Path,help='Aggregate-only audit output directory')
 p.add_argument('--private-routing',type=Path,help='Optional NEW private output directory for selected three per-token JSON files; never commit')
 a=p.parse_args();audit(a.manifest,a.frozen_counts,a.output,a.private_routing)
