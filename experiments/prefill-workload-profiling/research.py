#!/usr/bin/env python3
"""Archive hashes and evidence locations, not third-party corpus contents."""
import argparse,hashlib,json,platform,subprocess
from pathlib import Path
from net import Fetcher
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cache',default='/workspace/prefill-profile-cache/run');p.add_argument('--out',default=str(ROOT/'evidence'));a=p.parse_args()
f=Fetcher(a.cache);lock=json.loads((ROOT/'sources.lock.json').read_text());rev=lock['ultraep_reference'];base=f'https://raw.githubusercontent.com/Dots-Infra/UltraEP/{rev}/'
items={}
for path in ['README.md','examples/README.md']:
 data=f.full(base+path).read_text()
 items[path]={'sha256':hashlib.sha256(data.encode()).hexdigest(),'relevant_line_numbers':[i for i,line in enumerate(data.splitlines(),1) if any(k in line for k in ['SGLang inference','RedPajama','MOCK_DATA'])]}
tree=f.json(f'https://api.github.com/repos/Dots-Infra/UltraEP/git/trees/{rev}?recursive=1')
assert not tree.get('truncated')
paper=f.full('https://arxiv.org/html/2606.04101v3')
config=json.loads((Path(a.cache)/'tokenizer/config.json').read_text())
result={'paper':{'url':'https://arxiv.org/html/2606.04101v3','sha256':hashlib.sha256(paper.read_bytes()).hexdigest(),'sections':['8.1','8.2','Table 2'],'missing_recipe':['dataset revisions','split and sample counts','prompt assembly','mixture weights','filter/truncation policy','random seed','published routing trace']},'ultraep':{'revision':rev,'files':items,'tracked_paths':[x['path'] for x in tree['tree'] if x['type']=='blob'],'finding':'README says SGLang integration experimental and not yet released; examples use RedPajama training data, not a released six-source serving recipe.'},'model_config':{k:config.get(k) for k in ['hidden_size','moe_intermediate_size','num_experts','num_experts_per_tok','max_position_embeddings','rope_scaling','torch_dtype']},'runtime':{'python':platform.python_version(),'platform':platform.platform(),'packages':subprocess.check_output([__import__('sys').executable,'-m','pip','freeze'],text=True).splitlines()}}
out=Path(a.out);(out/'research-audit.json').write_text(json.dumps(result,indent=2)+'\n');(out/'research-downloads.json').write_text(json.dumps(f.records,indent=2)+'\n')
print('paper, public source and model config research hashes recorded')
