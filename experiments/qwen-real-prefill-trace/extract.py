#!/usr/bin/env python3
"""Extract one user-supplied request; never fetch data or infer tokenizer IDs."""
import argparse,csv,hashlib,json,math,subprocess,sys
from collections import Counter
from pathlib import Path

E,K,LAYERS=128,8,94
REV='27febb7b2d24169560a9f6f83d38eb53f94916cf'
SOURCE='Qwen/Qwen3-235B-A22B-FP8/Chinese-SimpleQA/中华文化/206.json'
BLOB='2cda327aa5570890e14971e1df0694218438c61f'

def unique_object(pairs):
    d={}
    for k,v in pairs:
        if k in d: raise ValueError('duplicate JSON key')
        d[k]=v
    return d

def parse(raw):
    data=json.loads(raw,object_pairs_hook=unique_object)
    if not isinstance(data,list) or len(data)<2: raise ValueError('expected multiple records')
    keys=[str(i) for i in range(LAYERS)]
    for step,record in enumerate(data):
        if not isinstance(record,dict) or list(record)!=keys: raise ValueError('missing/reordered/unexpected layers')
        lengths=[]
        for matrix in record.values():
            if not isinstance(matrix,list) or not matrix: raise ValueError('empty/non-list matrix')
            lengths.append(len(matrix))
            for row in matrix:
                if not isinstance(row,list) or len(row)!=K: raise ValueError('top-k mismatch')
                if any(type(e) is not int or not 0<=e<E for e in row): raise ValueError('expert type/range')
                if len(set(row))!=K: raise ValueError('duplicate expert')
        if len(set(lengths))!=1: raise ValueError('inconsistent layer token counts')
        if (step==0 and lengths[0]<=1) or (step>0 and lengths[0]!=1): raise ValueError('record shape inconsistent with documented phase convention')
    return data

def metrics(counts):
    total=sum(counts); mean=total/E
    if total==0: raise ValueError('zero assignments')
    variance=sum((x-mean)**2 for x in counts)/E
    gini=sum((2*i-E-1)*value for i,value in enumerate(sorted(counts),1))/(E*total)
    return dict(assignments=total,mean=mean,max=max(counts),max_mean=max(counts)/mean,
                jain=total**2/(E*sum(x*x for x in counts)),gini=gini,cv=math.sqrt(variance)/mean,
                hot1_share=max(counts)/total,hot8_share=sum(sorted(counts,reverse=True)[:8])/total,
                active_experts=sum(x>0 for x in counts))

def write_csv(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--private-output',type=Path,required=True);p.add_argument('--stats-output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[2]
    if a.private_output.resolve().is_relative_to(repo):
        raise ValueError('private route exports must be outside the repository')
    raw=a.input.read_bytes();data=parse(raw)
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if blob!=BLOB: raise ValueError('source Git blob mismatch; this PoC is pinned to one request')
    a.private_output.mkdir(parents=True,exist_ok=True);a.stats_output.mkdir(parents=True,exist_ok=True)
    n=len(data[0]['0']);fields=['token_id']+[f'expert_{i}' for i in range(K)];exports=[]
    for layer,matrix in data[0].items():
        dest=a.private_output/f'layer_{layer}.csv'
        write_csv(dest,fields,[dict(zip(fields,[t]+row)) for t,row in enumerate(matrix)])
        with dest.open(newline='') as f:
            reader=csv.reader(f);assert next(reader)==fields
            assert [[int(v) for v in row] for row in reader]==[[t]+row for t,row in enumerate(matrix)]
        exports.append(dict(layer_key=layer,file=dest.name,rows=n,assignments=n*K,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    generator=Path(__file__).resolve().parents[1]/'prefill-capacity/stage.py'
    synthetic_dir=a.private_output/'synthetic-control'
    subprocess.run([sys.executable,str(generator),'generate','--case',str(synthetic_dir),'--assignments',str(n*K)],check=True)
    synthetic=json.loads((synthetic_dir/'planner-input.json').read_text())
    assert synthetic['main_placement']==[e//2 for e in range(E)]
    control=[r['experts'] for r in synthetic['mapping']]
    assert len(control)==n
    statrows=[];countrows=[];histrows=[]
    for layer,matrix in data[0].items():
        for label,rows in [('real',matrix),('zipf',control)]:
            c=Counter(e for row in rows for e in row);counts=[c[e] for e in range(E)]
            assert sum(counts)==n*K
            statrows.append(dict(dataset=label,layer=int(layer),tokens=n,**metrics(counts)))
            countrows.extend(dict(dataset=label,layer=int(layer),expert=e,count=counts[e]) for e in range(E))
            hist=Counter(counts)
            histrows.extend(dict(dataset=label,layer=int(layer),assignment_count=k,expert_count=v) for k,v in sorted(hist.items()))
    for name,rows in [('layer-statistics.csv',statrows),('expert-counts.csv',countrows),('count-histograms.csv',histrows)]:
        write_csv(a.stats_output/name,list(rows[0]),rows)
    manifest=dict(source_path=SOURCE,revision=REV,source_git_blob=blob,source_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw),request_id='206 (filename-derived only)',request_identity_status='embedded request ID UNVERIFIABLE',phase_status='record 0 interpreted as prefill using dataset card; no embedded phase labels',token_id_semantics='zero-based source row ordinal, NOT original tokenizer ID',token_identity='UNVERIFIABLE',layer_id_semantics='exact source JSON keys 0..93; original model-layer correspondence UNVERIFIABLE',record_count=len(data),prefill_candidate_record=0,prefill_candidate_tokens=n,subsequent_single_token_records=len(data)-1,layers=LAYERS,experts=E,top_k=K,exports=exports,synthetic=dict(generator='experiments/prefill-capacity/stage.py',generator_sha256=hashlib.sha256(generator.read_bytes()).hexdigest(),seed=20261016,alpha=1.1,tokens=n,control_reused_for_all_layers=True,algorithm='existing generator: weighted draws, reject duplicate experts, preserve draw order'),original_token_order_status='serialized row order preserved exactly; original tokenizer order UNVERIFIABLE',published_data='aggregate statistics only; per-token CSV remains private')
    (a.private_output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    (a.stats_output/'provenance.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(status='STRUCTURAL_PASS_SEMANTICS_QUALIFIED',tokens=n,layers=LAYERS,exports=len(exports),prefill_assignments=n*LAYERS*K,all_record_assignments=sum(len(m)*K for s in data for m in s.values()))))
if __name__=='__main__':main()
