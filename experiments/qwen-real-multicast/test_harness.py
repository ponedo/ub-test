#!/usr/bin/env python3
"""Small harness tests; no simulator or private routing data required."""
import ast,hashlib,json,tempfile,unittest,subprocess,sys,csv
from pathlib import Path
X=Path(__file__).resolve().parent
class HarnessTests(unittest.TestCase):
 def test_plan_semantics_only_excludes_host_timing(self):
  tree=ast.parse((X/'run.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='semantic_plan');ns={'json':json,'hashlib':hashlib};exec(compile(ast.Module(body=[node],type_ignores=[]),str(X/'run.py'),'exec'),ns)
  with tempfile.TemporaryDirectory() as t:
   a=Path(t)/'a';b=Path(t)/'b';a.write_text(json.dumps({'physical':[{'quota':3}],'cpu_wall_ns':1}));b.write_text(json.dumps({'physical':[{'quota':3}],'cpu_wall_ns':2}));self.assertEqual(ns['semantic_plan'](a),ns['semantic_plan'](b));b.write_text(json.dumps({'physical':[{'quota':4}],'cpu_wall_ns':2}));self.assertNotEqual(ns['semantic_plan'](a),ns['semantic_plan'](b))
 def test_stopped_run_cannot_retain_old_performance(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)/'private';o=Path(t)/'out';r.mkdir();o.mkdir();(r/'run-ledger.json').write_text(json.dumps([{'layer':37,'strategy':'multicast','status':'STOPPED','failure':'test guard'}]));(o/'performance.csv').write_text('layer,tokens,strategy,layer_latency_ms\n37,2048,multicast,0.01\n');subprocess.run([sys.executable,X/'collect.py','--private',r,'--out',o],check=True,stdout=subprocess.PIPE);self.assertEqual(list(csv.DictReader((o/'performance.csv').read_text().splitlines())),[]);self.assertEqual(json.loads((o/'coverage.json').read_text())['completed'],0)
 def test_missing_required_evidence_rejected(self):
  tree=ast.parse((X/'collect.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='readcsv');ns={'csv':csv};exec(compile(ast.Module(body=[node],type_ignores=[]),'collect','exec'),ns)
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):ns['readcsv'](Path(t)/'missing',True)
if __name__=='__main__':unittest.main()
