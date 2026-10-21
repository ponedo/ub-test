"""Execute only accepted observer/native-boundary and pure roofline model units."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'token-screen-work';B=ROOT/'token-screen-private/build';O=ROOT/'token-screen-private/unit-gate'
s=importlib.util.spec_from_file_location('unit_guard',W/'experiments/cloudmatrix-bandwidth/guard.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
identity=json.loads((B/'build-identity.json').read_text())
def check():
 for p,d in identity.items():assert sha(p)==d,'Identity changed '+p
check();assert json.loads((B/'status.json').read_text())['status']=='PASS';O.mkdir(exist_ok=False)
(O/'identity-before.json').write_text(json.dumps(identity,indent=2)+'\n')
commands=[(n,[B/n]) for n in ['observer-fifo-test','jetty-window-test','jetty-observer-test']]
commands.append(('model-unit',[sys.executable,W/'experiments/qwen-roofline-compute/test-model.py',B/'model-probe',O/'model-unit-data']))
rows=[]
for name,cmd in commands:
 check();r=g.run(cmd,O/(name+'-host'),1800,cwd=O,case=O);check();assert r['status']=='PASS',name
 rows.append(dict(name=name,status='PASS',command=list(map(str,cmd)),resource=str(O/(name+'-host/resource.json'))))
(O/'identity-after.json').write_text(json.dumps(identity,indent=2)+'\n')
(O/'status.json').write_text(json.dumps(dict(status='PASS',tests=rows,scope='Three existing observer/native boundary units plus existing pure roofline model oracle. No formal/real simulations. Native window unit covers 512/1024/2048 capacity and ACK boundary assertions, not a parameter-sweep experiment.',source_and_binary_identities_unchanged=True),indent=2)+'\n')
print('PASS four accepted unit gates; no formal simulations',flush=True)
