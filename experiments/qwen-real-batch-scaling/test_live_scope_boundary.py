"""Regression for the old, already-loaded four-size outer loop and new exit 3."""
import json,runpy,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
X=Path(__file__).resolve().parent;sys.path.insert(0,str(X.parent/'wqe-completion-fix'));import guard
class Boundary(unittest.TestCase):
 def test_old_outer_never_starts_4096(self):
  # Preserve old loop/control behavior while supplying the actual new scope exit code.
  old=(X/'run.py').read_text().replace('[512,1024,2048]','[512,1024,2048,4096]').replace("if r.returncode and not (r.returncode==3 and n==2048 and (out/'scope-boundary.json').exists()):","if r.returncode:")
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'runs';sizes=[];extracts=[]
   def stage(cmd,*a,**kw):extracts.append(int(cmd[cmd.index('--tokens')+1]));return {'status':'PASS'}
   def child(cmd,**kw):
    n=int(cmd[cmd.index('--tokens')+1]);sizes.append(n);out=Path(cmd[cmd.index('--private')+1])
    rows=[dict(layer=l,strategy=s,status='PASS',routing_sha256=f'L{l}',validation={'status':'PASS'},**{k:{'status':'PASS'} for k in ['preparation_host','preflight_host','simulator_host','postflight_host']}) for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming']]
    (out/'runs.json').write_text(json.dumps(rows));return type('R',(),{'returncode':3 if n==2048 else 0})()
   argv=['run.py','--private',str(root),'--binary','unused','--lib','unused','--graph-tool','unused','--source-manifest','unused','--frozen-counts','unused']
   with patch.object(sys,'argv',argv),patch.object(guard,'run',stage),patch('subprocess.run',child):
    with self.assertRaises(RuntimeError):exec(compile(old,str(X/'run.py'),'exec'),{'__name__':'__main__','__file__':str(X/'run.py')})
   self.assertEqual(sizes,[512,1024,2048]);self.assertNotIn(4096,extracts);self.assertFalse((root/'tokens-4096').exists())
 def test_4096_child_rejected_before_work(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'not-created';args=[sys.executable,str(X/'run_size.py'),'--private',str(root),'--tokens','4096','--binary','unused','--lib','unused','--graph-tool','unused','--source-manifest','unused','--frozen-counts','unused']
   r=subprocess.run(args,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('scope ends at 2048',r.stderr);self.assertFalse(root.exists())
if __name__=='__main__':unittest.main()
