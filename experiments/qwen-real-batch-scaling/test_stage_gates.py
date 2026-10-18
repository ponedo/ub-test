#!/usr/bin/env python3
"""Execute the orchestration driver with fake stage results; no simulated metrics."""
import json,runpy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
X=Path(__file__).resolve().parent
sys.path.insert(0,str(X.parent/'wqe-completion-fix'))
import guard
class Gates(unittest.TestCase):
 def exercise(self,kind):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'runs';calls=[]
   def fake_stage(cmd,*args,**kwargs):
    return {'status':'FAIL' if kind=='extraction_fail' else 'PASS'}
   def fake_child(cmd,**kwargs):
    out=Path(cmd[cmd.index('--private')+1]);n=int(cmd[cmd.index('--tokens')+1]);calls.append(n)
    rows=[dict(layer=l,strategy=s,status='PASS',routing_sha256=f'L{l}',validation={'status':'PASS'},**{k:{'status':'PASS'} for k in ['preparation_host','preflight_host','simulator_host','postflight_host']}) for l in [0,37,52] for s in ['no-balancing','direct','chunk-streaming']]
    if kind=='missing_case':rows.pop()
    if kind=='duplicate_case':rows[-1]=rows[0]
    if kind=='online_fail':rows[-1]['validation']['status']='FAIL'
    if kind=='postflight_fail':rows[-1]['postflight_host']['status']='FAIL'
    if kind=='wrong_trace':rows[1]['routing_sha256']='wrong'
    (out/'runs.json').write_text(json.dumps(rows))
    if kind=='terminal_scope' and n==2048:(out/'scope-boundary.json').write_text(json.dumps({'reason':'USER_SCOPE_LIMIT_REACHED'}))
    return type('R',(),{'returncode':2 if kind=='child_fail' else (3 if kind=='terminal_scope' and n==2048 else 0)})()
   argv=['run.py','--private',str(root),'--binary','unused','--lib','unused','--graph-tool','unused','--source-manifest','unused','--frozen-counts','unused']
   error=None
   with patch.object(sys,'argv',argv),patch.object(guard,'run',fake_stage),patch('subprocess.run',fake_child):
    try:runpy.run_path(str(X/'run.py'),run_name='__main__')
    except Exception as e:error=e
   status=json.loads((root/'scaling-status.json').read_text())
   if kind in ('ok','terminal_scope'):
    self.assertIsNone(error);self.assertEqual(calls,[512,1024,2048]);self.assertEqual(status['status'],'PASS');self.assertEqual(status['completed_sizes'],calls)
   else:
    self.assertIsNotNone(error);self.assertEqual(status['status'],'STOPPED');self.assertEqual(status['completed_sizes'],[]);self.assertTrue(all(n==512 for n in calls))
 def test_terminal_scope_accepted(self):self.exercise('terminal_scope')
 def test_all_pass_advances(self):self.exercise('ok')
 def test_missing_case_stops(self):self.exercise('missing_case')
 def test_duplicate_case_stops(self):self.exercise('duplicate_case')
 def test_online_fail_stops(self):self.exercise('online_fail')
 def test_postflight_fail_stops(self):self.exercise('postflight_fail')
 def test_wrong_trace_stops(self):self.exercise('wrong_trace')
 def test_child_fail_stops(self):self.exercise('child_fail')
 def test_extraction_fail_stops(self):self.exercise('extraction_fail')
if __name__=='__main__':unittest.main()
