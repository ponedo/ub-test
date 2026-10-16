#!/usr/bin/env python3
"""Measure real public prompts; never save question/answer text in deliverables."""
import argparse,csv,hashlib,json,random,re,sys,time,zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from transformers import AutoTokenizer
from net import Fetcher,RemoteParquet
ROOT=Path(__file__).resolve().parent

def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def codeforces_prompt(row):
 parts=[]
 for key in ['title','description','input_format','output_format','interaction_format']:
  value=row.get(key)
  if isinstance(value,str) and value.strip():parts.append(key.replace('_',' ').title()+':\n'+value)
 for example in row.get('examples') or []:
  parts.append('Example input:\n'+example['input']+'\nExample output:\n'+example['output'])
 if row.get('note'):parts.append('Note:\n'+row['note'])
 return '\n\n'.join(parts)
def gpqa_prompt(row,index,seed):
 options=[row['Correct Answer']]+[row[f'Incorrect Answer {j}'] for j in range(1,4)]
 random.Random(seed+index).shuffle(options)
 return row['Question']+'\n\n'+'\n'.join(f'{chr(65+j)}. {option}' for j,option in enumerate(options))
def dapo_prompt(row):
 messages=row['prompt']
 if not isinstance(messages,list) or len(messages)!=1 or messages[0].get('role')!='user':raise ValueError('unexpected DAPO prompt roles')
 return messages[0]['content'],json.dumps(messages,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def longbench_prompt(row,template):return template.format(context=row['context'],input=row['input'])
def hf(repo,rev,name):return f'https://huggingface.co/datasets/{repo}/resolve/{rev}/{name}'

def run(args):
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);(out/'lengths').mkdir(exist_ok=True)
 cache=Path(args.cache);fetch=Fetcher(cache);lock=json.loads((ROOT/'sources.lock.json').read_text());meta=json.loads((cache/'metadata.json').read_text())
 tokenizer=AutoTokenizer.from_pretrained(cache/'tokenizer',local_files_only=True,trust_remote_code=False)
 tokenizer.apply_chat_template([{'role':'user','content':'preflight'}],tokenize=True,add_generation_prompt=True,enable_thinking=False)
 tokfiles={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((cache/'tokenizer').iterdir()) if p.is_file()}
 (out/'tokenizer-manifest.json').write_text(json.dumps(dict(lock['tokenizer'],files=tokfiles,chat_template_sha256=digest(tokenizer.chat_template),special_tokens_map=tokenizer.special_tokens_map,tokenizer_class=type(tokenizer).__name__,model_max_length=tokenizer.model_max_length),indent=2)+'\n')
 ledger=[];schemas={}
 def parquet(url):
  pf=pq.ParquetFile(RemoteParquet(fetch,url),pre_buffer=False,buffer_size=0)
  schemas[url]=dict(rows=pf.metadata.num_rows,row_groups=pf.num_row_groups,columns=pf.schema.names)
  return pf
 def measure(name,rows,info):
  start=time.monotonic();count=0;rejected=0;path=out/'lengths'/f'{name}.csv'
  with path.open('w') as f:
   w=csv.DictWriter(f,fieldnames=['sample_index','source_file','source_row','prompt_sha256','characters','raw_tokens','chat_tokens'],lineterminator='\n');w.writeheader()
   batch=[]
   def flush():
    nonlocal count
    if not batch:return
    prompts=[x[2] for x in batch]
    raw=tokenizer(prompts,add_special_tokens=False,truncation=False,return_attention_mask=False)['input_ids']
    chats=tokenizer.apply_chat_template([[{'role':'user','content':s}] for s in prompts],tokenize=True,add_generation_prompt=True,enable_thinking=False,truncation=False)
    for (file,row,text),rt,ct in zip(batch,raw,chats):
     w.writerow(dict(sample_index=count,source_file=file,source_row=row,prompt_sha256=digest(text),characters=len(text),raw_tokens=len(rt),chat_tokens=len(ct)));count+=1
    batch.clear()
   for file,index,text in rows:
    if not isinstance(text,str) or not text.strip():rejected+=1;continue
    batch.append((file,index,text))
    if len(batch)>=32:flush()
   flush()
  info.update(series=name,status='measured',N=count,rejected_empty_or_invalid=rejected,wall_seconds=time.monotonic()-start,lengths_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
  ledger.append(info);save();print(name,'N',count,'seconds',round(info['wall_seconds'],2),flush=True)
 def save():
  (out/'profile-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
  (out/'parquet-schemas.json').write_text(json.dumps(schemas,indent=2)+'\n')
  (out/'range-manifest.json').write_text(json.dumps(fetch.records,indent=2)+'\n')
 def guarded(name,fn):
  try:fn()
  except Exception as e:
   ledger.append(dict(series=name,status='failed',error=type(e).__name__+': '+str(e)));save();print(name,'FAILED',type(e).__name__,str(e),flush=True)
 selected=set(args.only.split(',')) if args.only else None
 def wants(name):return not selected or name in selected
 if wants('codeforces'):
  def codeforces():
   x=lock['codeforces'];files=[y['rfilename'] for y in meta['codeforces']['siblings'] if re.fullmatch(r'data/(train|test)-.*\.parquet',y['rfilename'])]
   columns=['title','description','input_format','output_format','interaction_format','note','examples']
   for split in ['train','test']:
    paths=sorted(p for p in files if p.startswith('data/'+split+'-'))
    def rows():
     for path in paths:
      pf=parquet(hf(x['repo'],x['revision'],path));index=0
      for batch in pf.iter_batches(batch_size=128,columns=columns,use_threads=False):
       for row in batch.to_pylist():yield path,index,codeforces_prompt(row);index+=1
    measure('codeforces_'+split,rows(),dict(source=x['repo'],revision=x['revision'],split=split,coverage='full selected default split',recipe='statement sections + public example I/O + note; no editorial, hidden/generated tests or checker'))
  guarded('codeforces',codeforces)
 if wants('swe_bench'):
  def swe():
   x=lock['swe_bench'];file=x['files'][0];pf=parquet(hf(x['repo'],x['revision'],file))
   def rows():
    i=0
    for b in pf.iter_batches(batch_size=128,columns=['problem_statement'],use_threads=False):
     for row in b.to_pylist():yield file,i,row['problem_statement'];i+=1
   measure('swe_bench_test_issue_only',rows(),dict(source=x['repo'],revision=x['revision'],split='test',coverage='full 2294 benchmark issues',recipe='problem_statement only; no repository context, hints, patch/test_patch or labels'))
   ledger.append(dict(series='swe_bench_full_agent_prompt',status='not_available',reason='Repository checkout/retrieval/tool/system context policy used by UltraEP is unknown; issue-only lengths cannot estimate a complete agent prompt.'));save()
  guarded('swe_bench',swe)
 if wants('dapo'):
  def dapo():
   x=lock['dapo'];file=x['files'][0];pf=parquet(hf(x['repo'],x['revision'],file));seen={};info=dict(source=x['repo'],revision=x['revision'],split='train',coverage='full canonical parquet, exact prompt deduplication',raw_rows=pf.metadata.num_rows,dedup_key=x['dedup'],duplicate_rows=0)
   def rows():
    index=0
    for b in pf.iter_batches(batch_size=4096,columns=['prompt'],use_threads=False):
     for row in b.to_pylist():
      text,key=dapo_prompt(row);h=digest(key)
      if h in seen:
       if seen[h]!=key:raise ValueError('SHA256 collision')
       info['duplicate_rows']+=1
      else:seen[h]=key;yield file,index,text
      index+=1
   measure('dapo_unique',rows(),info)
  guarded('dapo',dapo)
 if wants('gpqa'):
  def gpqa():
   x=lock['gpqa'];base=f'https://raw.githubusercontent.com/{x["repo"]}/{x["revision"]}/'
   readme=fetch.full(base+'README.md').read_text();password=re.search(r'password: `([^`]+)`',readme).group(1).encode()
   with zipfile.ZipFile(fetch.full(base+'dataset.zip')) as z:
    for subset in ['main','diamond','extended']:
     members=[n for n in z.namelist() if n.endswith('gpqa_'+subset+'.csv') and not n.startswith('__MACOSX')]
     if len(members)!=1:raise ValueError('GPQA member ambiguity')
     file=members[0];import io
     data=list(csv.DictReader(io.StringIO(z.read(file,pwd=password).decode('utf-8-sig'))))
     measure('gpqa_'+subset,((file,i,gpqa_prompt(row,i,20261016)) for i,row in enumerate(data)),dict(source=x['repo'],revision=x['revision'],split=subset,coverage='full official author archive subset; subsets overlap',recipe='question plus four shuffled choices; correct choice included only as an unlabelled option, no answer key/explanation appended',choice_shuffle_seed=20261016))
  guarded('gpqa',gpqa)
 if wants('longbench'):
  def lb():
   x=lock['longbench'];templates=json.loads(fetch.full(f'https://raw.githubusercontent.com/{x["prompt_repo"]}/{x["prompt_revision"]}/{x["prompt_path"]}').read_text())
   with zipfile.ZipFile(fetch.full(hf(x['repo'],x['revision'],'data.zip'))) as z:
    for subtask,template in templates.items():
     members=[n for n in z.namelist() if n.endswith('/'+subtask+'.jsonl') or n==subtask+'.jsonl']
     if len(members)!=1:raise ValueError('LongBench subtask ambiguity '+subtask)
     file=members[0]
     def rows():
      with z.open(file) as f:
       for i,line in enumerate(f):yield file,i,longbench_prompt(json.loads(line),template)
     measure('longbench_'+subtask,rows(),dict(source=x['repo'],revision=x['revision'],split='test',subtask=subtask,coverage='full original v1 subtask; _e variants excluded',recipe='official dataset2prompt(context,input), untruncated; ignore answers and existing length',template_sha256=digest(template),prompt_revision=x['prompt_revision']))
  guarded('longbench',lb)
 if wants('openscience'):
  def science():
   x=lock['openscience'];files=sorted(y['rfilename'] for y in meta['openscience_converted']['siblings'] if y['rfilename'].endswith('.parquet'))
   byconfig=defaultdict(list)
   for path in files:byconfig[path.split('/')[0]].append(path)
   for config,paths in sorted(byconfig.items()):
    tables=[];total=0
    for path in paths:
     pf=parquet(hf(x['repo'],x['parquet_revision'],path));tables.append((path,pf,total));total+=pf.metadata.num_rows
    seed=x['seed']+int(digest(config)[:8],16);rng=random.Random(seed);sample=sorted(rng.sample(range(total),min(total,x['sample_per_config'])));sample_set=set(sample)
    def rows():
     for path,pf,base in tables:
      position=base
      for group in range(pf.num_row_groups):
       n=pf.metadata.row_group(group).num_rows
       chosen=[i-position for i in sample if position<=i<position+n]
       if chosen:
        inputs=pf.read_row_group(group,columns=['input'],use_threads=False).column('input')
        for i in chosen:yield path,position-base+i,inputs[i].as_py()
       position+=n
    partial=any('/partial-' in path for path in paths)
    measure('openscience_'+config,rows(),dict(source=x['repo'],revision=x['revision'],parquet_revision=x['parquet_revision'],config=config,split='train',available_rows=total,sample_size=len(sample),seed=seed,replacement=False,coverage='uniform sample of converted PREFIX only; not representative of entire source config' if partial else 'uniform sample of complete converted config',partial_conversion=partial,recipe='input only; excludes output reasoning/answer',selection_global_indices_sha256=digest(json.dumps(sample))))
  guarded('openscience',science)
 save()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cache',default='/workspace/prefill-profile-cache/run');p.add_argument('--out',default=str(ROOT/'evidence'));p.add_argument('--only');run(p.parse_args())
