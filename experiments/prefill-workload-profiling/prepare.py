#!/usr/bin/env python3
import argparse,json,shutil,hashlib
from pathlib import Path
from net import Fetcher
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cache',default='/workspace/prefill-profile-cache/run');p.add_argument('--out',default=str(ROOT/'evidence'));a=p.parse_args()
cache=Path(a.cache);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);f=Fetcher(cache);lock=json.loads((ROOT/'sources.lock.json').read_text());meta={};status={}
def hf(repo,rev,name,kind='datasets'):return f'https://huggingface.co/{kind+"/" if kind else ""}{repo}/resolve/{rev}/{name}'
for key in ['tokenizer','codeforces','swe_bench','dapo','longbench','openscience']:
 try:
  x=lock[key];kind='models' if key=='tokenizer' else 'datasets'
  m=f.json(f'https://huggingface.co/api/{kind}/{x["repo"]}/revision/{x["revision"]}');meta[key]=m
  assert m['sha']==x['revision']
  f.full(hf(x['repo'],x['revision'],'README.md','' if key=='tokenizer' else 'datasets'))
  status[key]={'status':'metadata_verified','revision':x['revision'],'gated':m.get('gated'),'license_metadata':m.get('cardData',{}).get('license')}
  if key=='tokenizer':
   d=cache/'tokenizer';d.mkdir(exist_ok=True)
   for name in x['files']:shutil.copyfile(f.full(hf(x['repo'],x['revision'],name,'')),d/name)
  elif key=='longbench':
   f.full(hf(x['repo'],x['revision'],'data.zip'))
   u=f'https://raw.githubusercontent.com/{x["prompt_repo"]}/{x["prompt_revision"]}/{x["prompt_path"]}';f.full(u)
  elif key=='openscience':
   conv=f.json(f'https://huggingface.co/api/datasets/{x["repo"]}/revision/{x["parquet_revision"]}');meta['openscience_converted']=conv
  print(key,'metadata/download OK',flush=True)
 except Exception as e:status[key]={'status':'failed','error':str(e)};print(key,'FAILED',str(e),flush=True)
x=lock['gpqa'];u=f'https://raw.githubusercontent.com/{x["repo"]}/{x["revision"]}/'
try:
 f.full(u+'README.md');f.full(u+'dataset.zip');status['gpqa']={'status':'official_archive_downloaded','revision':x['revision'],'HF_gated':True,'HF_acceptance':False};print('gpqa official archive OK',flush=True)
except Exception as e:status['gpqa']={'status':'unavailable','error':str(e)};print('gpqa FAILED',e,flush=True)
(cache/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n');(out/'source-status.json').write_text(json.dumps(status,indent=2)+'\n');(out/'download-manifest.json').write_text(json.dumps(f.records,indent=2)+'\n')
if status['tokenizer']['status']=='failed':raise SystemExit('tokenizer required')
