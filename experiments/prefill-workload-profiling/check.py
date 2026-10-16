#!/usr/bin/env python3
"""Independent artifact integrity, prompt exclusions and deterministic replay checks."""
import argparse,csv,hashlib,io,json,math,re,unittest,zipfile
from pathlib import Path
import numpy as np
from transformers import AutoTokenizer
from profile import codeforces_prompt,dapo_prompt,gpqa_prompt,longbench_prompt
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cache',default='/workspace/prefill-profile-cache/run');p.add_argument('--out',default=str(ROOT/'evidence'));args=p.parse_args()
OUT=Path(args.out);CACHE=Path(args.cache);LOCK=json.loads((ROOT/'sources.lock.json').read_text());LEDGER=json.loads((OUT/'profile-ledger.json').read_text());MEASURED=[x for x in LEDGER if x['status']=='measured']
def csvrows(path):
 with path.open() as f:return list(csv.DictReader(f))
def cached(url):return CACHE/'files'/hashlib.sha256(url.encode()).hexdigest()
class Checks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tok=AutoTokenizer.from_pretrained(CACHE/'tokenizer',local_files_only=True,trust_remote_code=False)
 def test_prompt_target_exclusion(self):
  cf={'title':'T','description':'question','examples':[{'input':'1','output':'2'}]};a=codeforces_prompt(cf)
  self.assertEqual(a,codeforces_prompt(dict(cf,editorial='SECRET',official_tests=['SECRET'],solution='SECRET')));self.assertIn('Example output:\n2',a)
  lb={'context':'context','input':'question','answers':['SECRET'],'length':999};self.assertEqual(longbench_prompt(lb,'{context}\n{input}'),'context\nquestion')
  d={'prompt':[{'role':'user','content':'problem'}],'reward_model':{'ground_truth':'SECRET'}};self.assertEqual(dapo_prompt(d)[0],'problem');self.assertEqual(dapo_prompt(d),dapo_prompt(dict(d,reward_model={})))
  with self.assertRaises(ValueError):dapo_prompt({'prompt':[{'role':'assistant','content':'SECRET'}]})
  gp={'Question':'question','Correct Answer':'choice0',**{f'Incorrect Answer {i}':f'choice{i}' for i in range(1,4)},'Explanation':'SECRET'}
  built=gpqa_prompt(gp,0,20261016);self.assertNotIn('SECRET',built);self.assertNotIn('Correct Answer',built)
  for i in range(4):self.assertEqual(built.count('choice'+str(i)),1)
  self.assertEqual(built,gpqa_prompt(gp,0,20261016))
 def test_chat_template_no_truncation(self):
  for text in ['synthetic task','word '*50000]:
   messages=[{'role':'user','content':text}];render=self.tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
   ids=self.tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False,truncation=False)
   self.assertEqual(ids,self.tok.encode(render,add_special_tokens=False,truncation=False));self.assertIn('<think>\n\n</think>',render)
   if len(text)>10000:self.assertGreater(len(ids),40960)
 def test_lengths_and_summaries(self):
  summary={(x['series'],x['mode']):x for x in csvrows(OUT/'length-statistics.csv')}
  for item in MEASURED:
   path=OUT/'lengths'/f"{item['series']}.csv";rows=csvrows(path)
   self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),item['lengths_sha256']);self.assertEqual(len(rows),item['N'])
   self.assertEqual(set(rows[0]),{'sample_index','source_file','source_row','prompt_sha256','characters','raw_tokens','chat_tokens'})
   self.assertEqual([int(x['sample_index']) for x in rows],list(range(len(rows))))
   for mode in ['raw','chat']:
    x=np.array([int(r[mode+'_tokens']) for r in rows]);s=summary[item['series'],mode]
    self.assertTrue(np.all(x>0));self.assertAlmostEqual(float(s['mean']),float(x.mean()));self.assertEqual(int(s['min']),int(x.min()));self.assertEqual(int(s['max']),int(x.max()))
    for q in [50,90,95,99]:self.assertAlmostEqual(float(s['P'+str(q)]),float(np.quantile(x,q/100,method='linear')))
    for limit in [12500,32768,40960,131072]:self.assertAlmostEqual(float(s[f'fraction_above_{limit}']),float(np.mean(x>limit)))
   for suffix in ['lengths','batches']:self.assertTrue((OUT/'plots'/f"{item['series']}-{suffix}.png").read_bytes().startswith(b'\x89PNG'))
 def test_source_coverage(self):
  by={x['series']:x for x in MEASURED}
  if 'dapo_unique' in by:
   d=by['dapo_unique'];self.assertEqual(d['N']+d['duplicate_rows'],d['raw_rows']);self.assertEqual(d['raw_rows'],1791700);self.assertEqual(d['N'],17398)
  lb=[x for x in MEASURED if x['series'].startswith('longbench_')]
  if lb:self.assertEqual(len(lb),21);self.assertEqual(sum(x['N'] for x in lb),4750)
  for x in MEASURED:
   if x['series'].startswith('openscience_'):
    rows=csvrows(OUT/'lengths'/f"{x['series']}.csv");self.assertEqual(len(rows),5000);self.assertEqual(len(set((r['source_file'],r['source_row']) for r in rows)),5000)
    self.assertFalse(x['replacement']);self.assertEqual(x['partial_conversion'],x['config'].endswith('-10'))
  missing=[x for x in LEDGER if x['series']=='swe_bench_full_agent_prompt'];
  if missing:self.assertEqual(missing[0]['status'],'not_available')
 def test_actual_gpqa_retokenize(self):

  if not any(x['series']=='gpqa_main' for x in MEASURED):self.skipTest('GPQA unavailable; recorded in ledger')
  x=LOCK['gpqa'];base=f"https://raw.githubusercontent.com/{x['repo']}/{x['revision']}/"
  password=re.search(r'password: `([^`]+)`',cached(base+'README.md').read_text()).group(1).encode()
  saved=csvrows(OUT/'lengths/gpqa_main.csv')
  with zipfile.ZipFile(cached(base+'dataset.zip')) as z:
   name=next(n for n in z.namelist() if n.endswith('gpqa_main.csv') and not n.startswith('__MACOSX'));rows=list(csv.DictReader(io.StringIO(z.read(name,pwd=password).decode('utf-8-sig'))))
  for index in [0,1,17,100,447]:
   prompt=gpqa_prompt(rows[index],index,20261016);self.assertEqual(hashlib.sha256(prompt.encode()).hexdigest(),saved[index]['prompt_sha256'])
   self.assertEqual(len(self.tok.encode(prompt,add_special_tokens=False)),int(saved[index]['raw_tokens']))
   self.assertEqual(len(self.tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,enable_thinking=False)),int(saved[index]['chat_tokens']))
 def test_batch_expectation_and_replay(self):
  batches=csvrows(OUT/'batch-statistics.csv');summary={(x['series'],x['mode']):x for x in csvrows(OUT/'length-statistics.csv')}
  self.assertEqual(len(batches),len(MEASURED)*2*6)
  for r in batches:
   b=int(r['request_count']);n=int(r['repetitions']);expected=b*float(summary[r['series'],r['mode']]['mean']);self.assertEqual(n,100000);self.assertEqual(r['replacement'],'True')
   self.assertAlmostEqual(float(r['expected_mean_from_lengths']),expected);self.assertLessEqual(abs(float(r['mean'])-expected),6*float(r['mean_mc_standard_error'])+1e-8)
   if r['series'] in ['gpqa_main','longbench_narrativeqa'] and b in [1,32]:
    rows=csvrows(OUT/'lengths'/f"{r['series']}.csv");lengths=np.array([int(x[r['mode']+'_tokens']) for x in rows]);rng=np.random.default_rng(int(r['seed']));ids=rng.integers(0,len(rows),size=(n,b));sums=lengths[ids].sum(axis=1)
    self.assertEqual(float(r['mean']),float(sums.mean()))
    for q in [50,90,99]:self.assertEqual(float(r['P'+str(q)]),float(np.quantile(sums,q/100)))
    self.assertEqual(float(r['fraction_sum_above_diagnostic_budget_12500']),float(np.mean(sums>12500)))
    self.assertEqual(float(r['fraction_any_request_above_context_32768']),float(np.mean(lengths[ids].max(axis=1)>32768)))
 def test_download_hashes_and_source_preservation(self):
  tok=json.loads((OUT/'tokenizer-manifest.json').read_text())
  for name,record in tok['files'].items():self.assertEqual(hashlib.sha256((CACHE/'tokenizer'/name).read_bytes()).hexdigest(),record['sha256'])
  for filename in ['download-manifest.json','range-manifest.json','research-downloads.json']:
   for url,item in json.loads((OUT/filename).read_text()).items():
    key=hashlib.sha256(url.encode()).hexdigest()
    if item['access']=='full':self.assertEqual(hashlib.sha256((CACHE/'files'/key).read_bytes()).hexdigest(),item['sha256'])
    else:
     for tag,r in item['ranges'].items():
      data=(CACHE/'ranges'/key/tag).read_bytes();self.assertEqual(len(data),r['end']-r['start']+1);self.assertEqual(hashlib.sha256(data).hexdigest(),r['sha256'])
  audit=json.loads((OUT/'executor-audit.json').read_text());self.assertTrue(all(x['matches_base'] for x in audit['sources'].values()));self.assertIsNone(audit['runtime_estimate'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 (OUT/'check-summary.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful()),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
